from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import ROOT, ExperimentConfig
from .validation import validate_water_data

API_ROOT = "https://helsinki-openapi.nuuka.cloud/api/v1.0"
HRI_DATASET_URL = (
    "https://hri.fi/data/en_GB/dataset/"
    "helsingin-kaupungin-palvelukiinteistojen-energiankulutustietoja"
)
LICENSE = "Creative Commons Attribution 4.0"


def _get_json(path: str, params: dict[str, str]) -> tuple[list[dict[str, Any]], bytes]:
    url = f"{API_ROOT}/{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "helsinki-water-portfolio/1.0"})
    with urlopen(request, timeout=180) as response:  # noqa: S310 - fixed official host
        payload = response.read()
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError(f"Nuuka response for {path} was not a list")
    return parsed, payload


def acquire(config: ExperimentConfig) -> tuple[Path, Path, Path]:
    raw_dir = ROOT / "data" / "raw"
    processed_dir = ROOT / "data" / "processed"
    artifacts_dir = ROOT / "artifacts" / config.version
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    consumption, consumption_bytes = _get_json(
        "EnergyData/Monthly/ListByProperty",
        {
            "Customer": "Helsinki",
            "Record": "LocationName",
            "SearchString": "koulu",
            "ReportingGroup": "Water",
            "StartTime": f"{config.start_month}-01",
            # Nuuka currently omits some older calendar years for otherwise identical
            # narrowly bounded queries. A fixed wider extraction window is therefore
            # downloaded and the versioned study period is filtered locally.
            "EndTime": "2025-12-31",
        },
    )
    properties, properties_bytes = _get_json(
        "Property/Search",
        {
            "Customer": "Helsinki",
            "SearchFromRecord": "LocationName",
            "SearchString": "koulu",
        },
    )
    (raw_dir / "nuuka-water-monthly.json").write_bytes(consumption_bytes)
    (raw_dir / "nuuka-school-properties.json").write_bytes(properties_bytes)

    frame = pd.DataFrame(consumption)
    frame = frame.loc[frame["locationName"].isin(config.properties)].copy()
    frame["month"] = pd.to_datetime(frame["timestamp"]).dt.to_period("M").astype(str)
    frame = frame.loc[
        (frame["month"] >= config.start_month) & (frame["month"] <= config.end_month)
    ].copy()
    frame = frame.rename(columns={"locationName": "property_name", "value": "water_m3"})[
        ["property_name", "month", "water_m3", "unit"]
    ]
    frame["water_m3"] = pd.to_numeric(frame["water_m3"], errors="raise")
    frame = frame.sort_values(["property_name", "month"]).reset_index(drop=True)

    property_lookup = {
        str(item["locationName"]): item
        for item in properties
        if str(item.get("locationName", "")) in config.properties
    }
    metadata_rows: list[dict[str, Any]] = []
    for name in config.properties:
        item = property_lookup.get(name)
        if item is None:
            raise ValueError(f"Missing Nuuka property metadata for {name}")
        longitude = float(item["longitude"])
        zone = "west" if longitude < 24.93 else "east" if longitude > 25.02 else "central"
        metadata_rows.append(
            {
                "property_name": name,
                "property_code": item["propertyCode"],
                "purpose_of_use": item.get("purposeOfUse"),
                "building_type": item.get("buildingType"),
                "total_area_m2": float(item["totalArea"]),
                "latitude": float(item["latitude"]),
                "longitude": longitude,
                "inspection_zone": zone,
            }
        )
    metadata = pd.DataFrame(metadata_rows).sort_values("property_name")

    # Gate source refreshes before replacing the reproducible curated snapshot.
    validate_water_data(frame, config)

    data_path = processed_dir / "water_monthly_v1.csv"
    metadata_path = processed_dir / "properties_v1.csv"
    frame.to_csv(data_path, index=False, lineterminator="\n")
    metadata.to_csv(metadata_path, index=False, lineterminator="\n")
    manifest = {
        "datasetVersion": "nuuka-helsinki-school-water-monthly-v1",
        "acquiredAt": datetime.now(UTC).isoformat(),
        "source": "City of Helsinki Nuuka Open API via Helsinki Region Infoshare",
        "sourceDatasetUrl": HRI_DATASET_URL,
        "apiRoot": API_ROOT,
        "license": LICENSE,
        "sourcePeriod": {"start": config.start_month, "end": config.end_month},
        "selection": {
            "search": "koulu",
            "reportingGroup": "Water",
            "frequency": "Monthly",
            "properties": list(config.properties),
        },
        "rawSha256": {
            "consumption": hashlib.sha256(consumption_bytes).hexdigest(),
            "properties": hashlib.sha256(properties_bytes).hexdigest(),
        },
        "processedSha256": {
            "waterMonthly": hashlib.sha256(data_path.read_bytes()).hexdigest(),
            "properties": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        },
        "rows": int(len(frame)),
        "propertyCount": int(frame["property_name"].nunique()),
    }
    manifest_path = artifacts_dir / "data-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return data_path, metadata_path, manifest_path


def load_processed(config: ExperimentConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(ROOT / "data" / "processed" / "water_monthly_v1.csv")
    metadata = pd.read_csv(ROOT / "data" / "processed" / "properties_v1.csv")
    data["month"] = pd.PeriodIndex(data["month"], freq="M")
    return data, metadata

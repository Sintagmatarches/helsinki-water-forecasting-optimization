from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_validation import config

from helsinki_water import data
from helsinki_water.validation import DataValidationError


@pytest.mark.parametrize("invalid", [True, False])
def test_acquisition_validates_before_replacing_curated_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: bool
) -> None:
    monkeypatch.setattr(data, "ROOT", tmp_path)
    output_paths = [
        tmp_path / "data/processed/water_monthly_v1.csv",
        tmp_path / "data/processed/properties_v1.csv",
        tmp_path / "artifacts/test/data-manifest.json",
    ]
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"existing verified evidence\n")
    consumption = [
        {"locationName": "A", "timestamp": f"2020-{month:02d}-01", "value": 2, "unit": "M3"}
        for month in ([1, 3] if invalid else [1, 2, 3])
    ]
    properties = [{
        "locationName": "A", "propertyCode": "A", "longitude": 25,
        "latitude": 60, "totalArea": 100,
    }]

    def source(path: str, params: dict[str, str]) -> tuple[list[dict[str, Any]], bytes]:
        rows = consumption if path.startswith("EnergyData/") else properties
        return rows, json.dumps(rows).encode()

    monkeypatch.setattr(data, "_get_json", source)
    if invalid:
        with pytest.raises(DataValidationError, match="missing or extra"):
            data.acquire(config())
        for path in output_paths:
            assert path.read_bytes() == b"existing verified evidence\n"
    else:
        assert data.acquire(config()) == tuple(output_paths)
        manifest = json.loads(output_paths[-1].read_text())
        assert manifest["rows"] == 3

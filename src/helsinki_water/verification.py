from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CSV_ARTIFACTS = (
    "final-intervals.csv",
    "forecast-predictions.csv",
    "monitoring-predictions.csv",
    "optimization-sensitivity.csv",
    "statistical-anomalies.csv",
)
IDENTITY_COLUMNS = {
    "split",
    "model",
    "site",
    "origin",
    "target_month",
    "horizon",
    "scenario",
    "candidate_id",
    "property_name",
    "property_code",
    "inspection_zone",
}


def _compare_json(reference: Any, current: Any, path: str = "root") -> None:
    if isinstance(reference, bool) or isinstance(current, bool):
        if reference is not current:
            raise AssertionError(f"Boolean changed at {path}: {reference!r} != {current!r}")
        return
    if isinstance(reference, (int, float)) and isinstance(current, (int, float)):
        if not math.isclose(float(reference), float(current), rel_tol=0.02, abs_tol=0.25):
            raise AssertionError(f"Numeric evidence changed at {path}: {reference} != {current}")
        return
    if isinstance(reference, dict) and isinstance(current, dict):
        if reference.keys() != current.keys():
            raise AssertionError(f"JSON keys changed at {path}")
        for key in reference:
            _compare_json(reference[key], current[key], f"{path}.{key}")
        return
    if isinstance(reference, list) and isinstance(current, list):
        if len(reference) != len(current):
            raise AssertionError(f"JSON list length changed at {path}")
        for index, (left, right) in enumerate(zip(reference, current, strict=True)):
            _compare_json(left, right, f"{path}[{index}]")
        return
    if reference != current:
        raise AssertionError(f"Evidence changed at {path}: {reference!r} != {current!r}")


def _compare_csv(reference_path: Path, current_path: Path) -> None:
    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)
    if reference.columns.tolist() != current.columns.tolist():
        raise AssertionError(f"CSV schema changed: {current_path.name}")
    if reference.shape != current.shape:
        raise AssertionError(f"CSV shape changed: {current_path.name}")
    for column in reference.columns:
        if column == "model_details":
            continue
        left = reference[column]
        right = current[column]
        if column in IDENTITY_COLUMNS or not pd.api.types.is_numeric_dtype(left):
            if not left.fillna("<NA>").astype(str).equals(right.fillna("<NA>").astype(str)):
                raise AssertionError(f"Identity column changed: {current_path.name}:{column}")
            continue
        if not np.allclose(
            left.to_numpy(dtype=float),
            right.to_numpy(dtype=float),
            rtol=0.02,
            atol=0.25,
            equal_nan=True,
        ):
            raise AssertionError(f"Numeric column changed: {current_path.name}:{column}")


def verify(reference_dir: Path, current_dir: Path) -> None:
    reference_metrics = json.loads((reference_dir / "metrics.json").read_text(encoding="utf-8"))
    current_metrics = json.loads((current_dir / "metrics.json").read_text(encoding="utf-8"))
    _compare_json(reference_metrics, current_metrics)
    for filename in CSV_ARTIFACTS:
        _compare_csv(reference_dir / filename, current_dir / filename)
    for figure in (current_dir / "figures").glob("*.png"):
        if figure.stat().st_size < 10_000:
            raise AssertionError(f"Figure missing or implausibly small: {figure.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare evidence across numerical platforms")
    parser.add_argument("reference", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args(argv)
    verify(args.reference, args.current)
    print("Artifact schemas, identities and numeric evidence remain within tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

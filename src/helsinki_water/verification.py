from __future__ import annotations

import argparse
import ast
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
NUMERIC_RTOL = 1e-9
NUMERIC_ATOL = 1e-9
INTERVAL_COLUMNS = {"interval_q", "lower_m3", "upper_m3", "interval_width_m3"}
INTERVAL_RTOL = 1e-12
INTERVAL_ATOL = 1e-9
SARIMA_FORECAST_RTOL = 5e-5
SARIMA_FORECAST_ATOL = 1e-6
SARIMA_METRIC_RTOL = 1e-6
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


def _compare_json(
    reference: Any,
    current: Any,
    path: str = "root",
    sarima_context: bool = False,
) -> None:
    if isinstance(reference, bool) or isinstance(current, bool):
        if reference is not current:
            raise AssertionError(f"Boolean changed at {path}: {reference!r} != {current!r}")
        return
    if isinstance(reference, int) and isinstance(current, int):
        if reference != current:
            raise AssertionError(f"Integer evidence changed at {path}: {reference} != {current}")
        return
    if isinstance(reference, (int, float)) and isinstance(current, (int, float)):
        relative_tolerance = SARIMA_METRIC_RTOL if sarima_context else NUMERIC_RTOL
        if not math.isclose(
            float(reference),
            float(current),
            rel_tol=relative_tolerance,
            abs_tol=NUMERIC_ATOL,
        ):
            raise AssertionError(f"Numeric evidence changed at {path}: {reference} != {current}")
        return
    if isinstance(reference, dict) and isinstance(current, dict):
        if reference.keys() != current.keys():
            raise AssertionError(f"JSON keys changed at {path}")
        model_is_sarima = (
            reference.get("model") == "sarima_paper"
            and current.get("model") == "sarima_paper"
        )
        for key in reference:
            child_sarima_context = (
                sarima_context or model_is_sarima or "sarima" in str(key).casefold()
            )
            _compare_json(
                reference[key],
                current[key],
                f"{path}.{key}",
                child_sarima_context,
            )
        return
    if isinstance(reference, list) and isinstance(current, list):
        if len(reference) != len(current):
            raise AssertionError(f"JSON list length changed at {path}")
        for index, (left, right) in enumerate(zip(reference, current, strict=True)):
            _compare_json(left, right, f"{path}[{index}]", sarima_context)
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
        left = reference[column]
        right = current[column]
        if column == "model_details":
            sarima_rows = reference["model"].eq("sarima_paper")
            if not left.loc[~sarima_rows].fillna("<NA>").astype(str).equals(
                right.loc[~sarima_rows].fillna("<NA>").astype(str)
            ):
                raise AssertionError(f"Model details changed: {current_path.name}:{column}")
            for index in reference.index[sarima_rows]:
                reference_details = ast.literal_eval(str(left.loc[index]))
                current_details = ast.literal_eval(str(right.loc[index]))
                _compare_json(
                    reference_details,
                    current_details,
                    f"{current_path.name}.{column}[{index}]",
                )
            continue
        if column in IDENTITY_COLUMNS or not pd.api.types.is_numeric_dtype(left):
            if not left.fillna("<NA>").astype(str).equals(right.fillna("<NA>").astype(str)):
                raise AssertionError(f"Identity column changed: {current_path.name}:{column}")
            continue
        relative_tolerance = INTERVAL_RTOL if column in INTERVAL_COLUMNS else NUMERIC_RTOL
        absolute_tolerance = INTERVAL_ATOL if column in INTERVAL_COLUMNS else NUMERIC_ATOL
        strict_rows = np.ones(len(reference), dtype=bool)
        if column == "forecast_m3" and "model" in reference:
            sarima_mask = reference["model"].eq("sarima_paper").to_numpy()
            strict_rows &= ~sarima_mask
            if not np.allclose(
                left.to_numpy(dtype=float)[sarima_mask],
                right.to_numpy(dtype=float)[sarima_mask],
                rtol=SARIMA_FORECAST_RTOL,
                atol=SARIMA_FORECAST_ATOL,
                equal_nan=True,
            ):
                raise AssertionError(
                    f"SARIMA forecast column changed: {current_path.name}:{column}"
                )
        if not np.allclose(
            left.to_numpy(dtype=float)[strict_rows],
            right.to_numpy(dtype=float)[strict_rows],
            rtol=relative_tolerance,
            atol=absolute_tolerance,
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

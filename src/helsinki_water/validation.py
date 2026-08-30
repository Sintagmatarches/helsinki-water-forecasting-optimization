from __future__ import annotations

import pandas as pd

from .config import ExperimentConfig


class DataValidationError(ValueError):
    """Raised when source data violate the declared experiment contract."""


def validate_water_data(data: pd.DataFrame, config: ExperimentConfig) -> dict[str, int | str]:
    required = {"property_name", "month", "water_m3", "unit"}
    missing = required.difference(data.columns)
    if missing:
        raise DataValidationError(f"Missing columns: {sorted(missing)}")
    if set(data["property_name"].unique()) != set(config.properties):
        raise DataValidationError("Processed properties do not match the versioned selection")
    expected = pd.period_range(config.start_month, config.end_month, freq="M")
    duplicate_count = int(data.duplicated(["property_name", "month"]).sum())
    if duplicate_count:
        raise DataValidationError(f"Found {duplicate_count} duplicate property-month rows")
    for name, group in data.groupby("property_name", sort=True):
        actual = pd.PeriodIndex(group["month"], freq="M").sort_values()
        if not actual.equals(expected):
            absent = expected.difference(actual)
            raise DataValidationError(f"{name} has missing or extra months: {list(absent)}")
    if (
        data["water_m3"].isna().any()
        or (~pd.to_numeric(data["water_m3"], errors="coerce").notna()).any()
    ):
        raise DataValidationError("Water values must be finite numeric values")
    if (data["water_m3"] <= 0).any():
        raise DataValidationError(
            "Selected study panel requires strictly positive monthly water use"
        )
    if set(data["unit"].unique()) != {"M3"}:
        raise DataValidationError("Unexpected water unit")
    return {
        "rows": int(len(data)),
        "properties": int(data["property_name"].nunique()),
        "monthsPerProperty": int(len(expected)),
        "startMonth": str(expected[0]),
        "endMonth": str(expected[-1]),
    }

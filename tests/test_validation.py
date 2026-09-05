from __future__ import annotations

import pandas as pd
import pytest

from helsinki_water.config import ExperimentConfig
from helsinki_water.validation import DataValidationError, validate_water_data


def config() -> ExperimentConfig:
    return ExperimentConfig(
        version="test",
        seed=1,
        start_month="2020-01",
        end_month="2020-03",
        development_first_origin="2020-01",
        development_last_origin="2020-01",
        development_step_months=1,
        development_horizon=1,
        final_origin="2020-02",
        final_horizon=1,
        interval_alpha=0.1,
        properties=("A",),
        optimization={},
    )


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_name": ["A", "A", "A"],
            "month": pd.period_range("2020-01", "2020-03", freq="M"),
            "water_m3": [1.0, 2.0, 3.0],
            "unit": ["M3", "M3", "M3"],
        }
    )


def test_complete_panel_passes() -> None:
    result = validate_water_data(frame(), config())
    assert result["rows"] == 3
    assert result["monthsPerProperty"] == 3


def test_missing_month_and_nonpositive_value_fail() -> None:
    with pytest.raises(DataValidationError, match="missing or extra"):
        validate_water_data(frame().iloc[:2], config())
    invalid = frame()
    invalid.loc[1, "water_m3"] = 0.0
    with pytest.raises(DataValidationError, match="strictly positive"):
        validate_water_data(invalid, config())


@pytest.mark.parametrize("value", [float("inf"), -float("inf"), float("nan")])
def test_nonfinite_water_is_rejected(value: float) -> None:
    invalid = frame()
    invalid.loc[1, "water_m3"] = value
    with pytest.raises(DataValidationError, match="finite numeric"):
        validate_water_data(invalid, config())


@pytest.mark.parametrize("value", ["2.0", "invalid", True, 1 + 2j])
def test_nonnumeric_water_dtype_is_rejected(value: object) -> None:
    invalid = frame().astype({"water_m3": object})
    invalid.loc[1, "water_m3"] = value
    with pytest.raises(DataValidationError, match="finite numeric"):
        validate_water_data(invalid, config())

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from helsinki_water.verification import _compare_csv, _compare_json


def test_sarima_metric_tolerance_is_scoped() -> None:
    reference = {"model": "sarima_paper", "mae_m3": 37.092832425902614}
    linux = {"model": "sarima_paper", "mae_m3": 37.092844275184156}
    _compare_json(reference, linux)
    with pytest.raises(AssertionError, match="Numeric evidence changed"):
        _compare_json({"model": "ets", "mae_m3": 37.0}, {"model": "ets", "mae_m3": 37.00001})


def _write_forecast(path: Path, model: str, forecast: float, aic: float = 400.0) -> None:
    pd.DataFrame(
        {
            "split": ["development"],
            "model": [model],
            "site": ["test-site"],
            "origin": ["2017-01"],
            "target_month": ["2017-02"],
            "horizon": [1],
            "forecast_m3": [forecast],
            "model_details": [
                str(
                    {
                        "aic": aic,
                        "order": "(0, 1, 2)",
                        "seasonalOrder": "(0, 1, 1, 12)",
                    }
                )
            ],
        }
    ).to_csv(path, index=False)


def test_sarima_forecast_tolerance_does_not_weaken_ets(tmp_path: Path) -> None:
    reference = tmp_path / "reference.csv"
    current = tmp_path / "current.csv"
    _write_forecast(reference, "sarima_paper", 4.865506540307413, 416.2981237762416)
    _write_forecast(current, "sarima_paper", 4.865359991322471, 416.29812377618344)
    _compare_csv(reference, current)

    _write_forecast(reference, "ets", 100.0)
    _write_forecast(current, "ets", 100.00001)
    with pytest.raises(AssertionError, match="Numeric column changed"):
        _compare_csv(reference, current)

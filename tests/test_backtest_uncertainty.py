from __future__ import annotations

import numpy as np
import pandas as pd

from helsinki_water.backtest import BacktestDesign, run_backtest
from helsinki_water.uncertainty import apply_intervals, conformal_quantile


def test_backtest_targets_strictly_follow_origin() -> None:
    index = pd.period_range("2010-01", periods=60, freq="M")
    series = {"A": pd.Series(np.arange(60, dtype=float) + 10.0, index=index)}
    result = run_backtest(
        series,
        BacktestDesign((pd.Period("2013-12", freq="M"),), 3, "test"),
        models=("seasonal_naive",),
    )
    assert result["target_month"].tolist() == ["2014-01", "2014-02", "2014-03"]
    assert (pd.PeriodIndex(result["target_month"], freq="M") > pd.Period("2013-12")).all()


def test_finite_sample_conformal_quantile_and_intervals() -> None:
    assert conformal_quantile(np.arange(1.0, 10.0), alpha=0.1) == 9.0
    predictions = pd.DataFrame(
        {
            "horizon": [1],
            "forecast_m3": [10.0],
            "actual_m3": [12.0],
            "scale_m3": [2.0],
        }
    )
    result = apply_intervals(predictions, {"h1": 1.0})
    assert result.loc[0, "lower_m3"] == 8.0
    assert result.loc[0, "upper_m3"] == 12.0
    assert bool(result.loc[0, "covered"])

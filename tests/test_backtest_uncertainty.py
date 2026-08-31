from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from helsinki_water.backtest import BacktestDesign, panel_series, period_steps, run_backtest
from helsinki_water.config import load_config
from helsinki_water.data import load_processed
from helsinki_water.uncertainty import (
    apply_intervals,
    calibrate,
    conformal_quantile,
    interval_summary,
)


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


def test_calibration_and_intervals_ignore_input_row_order() -> None:
    predictions = pd.DataFrame(
        {
            "model": ["ets"] * 12,
            "horizon": [1, 2, 3, 4, 5, 6] * 2,
            "forecast_m3": np.arange(12, dtype=float) + 20.0,
            "actual_m3": np.asarray([22, 20, 25, 19, 31, 22, 29, 24, 33, 25, 38, 27]),
            "scale_m3": np.asarray([2.0, 3.0, 4.0, 2.0, 3.0, 4.0] * 2),
        }
    )
    original = calibrate(predictions, "ets", 0.1)
    shuffled = calibrate(predictions.sample(frac=1.0, random_state=20260830), "ets", 0.1)
    assert original == shuffled
    first = apply_intervals(predictions, original)
    second = apply_intervals(predictions.copy(), original)
    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_conformal_order_statistic_is_stable_without_interpolation() -> None:
    residuals = np.asarray([2.0, 1.0, 4.0, 4.0, 3.0, np.nan])
    expected = conformal_quantile(residuals, alpha=0.2)
    for seed in (1, 7, 42):
        shuffled = np.random.default_rng(seed).permutation(residuals)
        assert conformal_quantile(shuffled, alpha=0.2) == expected == 4.0


def test_versioned_uncertainty_contract() -> None:
    config = load_config()
    data, _ = load_processed(config)
    series = panel_series(data)
    development = run_backtest(
        series,
        BacktestDesign(
            origins=period_steps(
                config.development_first_origin,
                config.development_last_origin,
                config.development_step_months,
            ),
            horizon=config.development_horizon,
            split="development",
        ),
        models=("ets",),
    )
    quantiles = calibrate(
        development.loc[development["site"] != "PORTFOLIO_TOTAL"],
        "ets",
        config.interval_alpha,
    )
    assert quantiles == pytest.approx(
        {
            "h1": 1.7684269214810409,
            "h2-3": 2.5925197633047894,
            "h4-6": 2.8534829568933566,
            "h7-12": 2.8534829568933566,
        },
        rel=1e-12,
        abs=1e-12,
    )
    final = run_backtest(
        series,
        BacktestDesign(
            origins=(pd.Period(config.final_origin, freq="M"),),
            horizon=config.final_horizon,
            split="final",
        ),
        models=("ets",),
    )
    intervals = apply_intervals(final, quantiles)
    summary = interval_summary(intervals.loc[intervals["site"] != "PORTFOLIO_TOTAL"])
    assert summary["coverage"] == pytest.approx(94 / 96)
    assert summary["meanWidthM3"] == pytest.approx(162.7377436315916, rel=1e-12)

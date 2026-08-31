from __future__ import annotations

import math

import numpy as np
import pandas as pd


def horizon_bucket(horizon: int) -> str:
    if horizon == 1:
        return "h1"
    if horizon <= 3:
        return "h2-3"
    if horizon <= 6:
        return "h4-6"
    return "h7-12"


def conformal_quantile(values: np.ndarray, alpha: float) -> float:
    raw = np.asarray(values, dtype=float)
    clean = np.sort(raw[np.isfinite(raw)], kind="stable")
    if len(clean) == 0:
        raise ValueError("Conformal calibration requires residuals")
    rank = min(len(clean), math.ceil((len(clean) + 1) * (1.0 - alpha)))
    # A finite-sample conformal order statistic: no interpolation is performed.
    return float(clean[rank - 1])


def calibrate(dev: pd.DataFrame, model: str, alpha: float) -> dict[str, float]:
    chosen = dev.loc[dev["model"] == model].copy()
    chosen["bucket"] = chosen["horizon"].map(horizon_bucket)
    chosen["standardized_error"] = (chosen["actual_m3"] - chosen["forecast_m3"]).abs() / chosen[
        "scale_m3"
    ].clip(lower=1e-9)
    quantiles: dict[str, float] = {}
    for bucket, group in chosen.groupby("bucket"):
        quantiles[str(bucket)] = conformal_quantile(group["standardized_error"].to_numpy(), alpha)
    if "h7-12" not in quantiles:
        quantiles["h7-12"] = max(quantiles.values())
    return quantiles


def apply_intervals(
    predictions: pd.DataFrame,
    quantiles: dict[str, float],
    multiplier: float = 1.0,
) -> pd.DataFrame:
    result = predictions.copy()
    result["horizon_bucket"] = result["horizon"].map(horizon_bucket)
    result["interval_q"] = result["horizon_bucket"].map(quantiles).astype(float)
    radius = result["interval_q"] * result["scale_m3"] * multiplier
    result["lower_m3"] = (result["forecast_m3"] - radius).clip(lower=0.0)
    result["upper_m3"] = result["forecast_m3"] + radius
    result["covered"] = (result["actual_m3"] >= result["lower_m3"]) & (
        result["actual_m3"] <= result["upper_m3"]
    )
    result["interval_width_m3"] = result["upper_m3"] - result["lower_m3"]
    return result


def interval_summary(predictions: pd.DataFrame) -> dict[str, object]:
    work = predictions.copy()
    work["month_number"] = pd.PeriodIndex(work["target_month"], freq="M").month
    work["season"] = np.select(
        [work["month_number"].isin([12, 1, 2]), work["month_number"].isin([6, 7, 8])],
        ["winter", "summer"],
        default="shoulder",
    )
    by_horizon = (
        work.groupby("horizon_bucket")
        .agg(
            coverage=("covered", "mean"),
            mean_width_m3=("interval_width_m3", "mean"),
            observations=("covered", "size"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    by_season = (
        work.groupby("season")
        .agg(
            coverage=("covered", "mean"),
            mean_width_m3=("interval_width_m3", "mean"),
            observations=("covered", "size"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    return {
        "coverage": float(work["covered"].mean()),
        "meanWidthM3": float(work["interval_width_m3"].mean()),
        "byHorizon": by_horizon,
        "bySeason": by_season,
    }

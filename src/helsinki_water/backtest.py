from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import MODEL_NAMES, forecast


@dataclass(frozen=True)
class BacktestDesign:
    origins: tuple[pd.Period, ...]
    horizon: int
    split: str


def panel_series(data: pd.DataFrame) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    for name, group in data.groupby("property_name", sort=True):
        result[str(name)] = pd.Series(
            group["water_m3"].to_numpy(dtype=float),
            index=pd.PeriodIndex(group["month"], freq="M"),
            dtype=float,
        ).sort_index()
    aggregate = data.groupby("month", sort=True)["water_m3"].sum()
    aggregate.index = pd.PeriodIndex(aggregate.index, freq="M")
    result["PORTFOLIO_TOTAL"] = aggregate.astype(float)
    return result


def period_steps(first: str, last: str, step: int) -> tuple[pd.Period, ...]:
    periods = pd.period_range(first, last, freq="M")
    return tuple(periods[::step])


def seasonal_scale(train: np.ndarray) -> float:
    if len(train) <= 12:
        return float(np.mean(np.abs(np.diff(train)))) or 1.0
    scale = float(np.mean(np.abs(train[12:] - train[:-12])))
    return scale if scale > 1e-9 else max(float(np.mean(np.abs(train))), 1.0)


def run_backtest(
    series: dict[str, pd.Series],
    design: BacktestDesign,
    models: Iterable[str] = MODEL_NAMES,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for site, values in series.items():
        for origin in design.origins:
            train = values.loc[values.index <= origin].dropna()
            target_index = pd.period_range(origin + 1, periods=design.horizon, freq="M")
            target = values.reindex(target_index)
            available = int(target.notna().sum())
            if available == 0:
                continue
            scale = seasonal_scale(train.to_numpy(dtype=float))
            for model_name in models:
                result = forecast(model_name, train.to_numpy(dtype=float), design.horizon)
                for step, (month, actual) in enumerate(target.items(), start=1):
                    if pd.isna(actual):
                        continue
                    rows.append(
                        {
                            "split": design.split,
                            "model": model_name,
                            "site": site,
                            "origin": str(origin),
                            "target_month": str(month),
                            "horizon": step,
                            "actual_m3": float(actual),
                            "forecast_m3": float(result.values[step - 1]),
                            "scale_m3": scale,
                            "model_details": str(result.details),
                        }
                    )
    return pd.DataFrame(rows)


def metric_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    work = predictions.copy()
    error = work["actual_m3"] - work["forecast_m3"]
    work["absolute_error"] = error.abs()
    work["squared_error"] = error.pow(2)
    denominator = (work["actual_m3"].abs() + work["forecast_m3"].abs()).clip(lower=1e-9)
    work["smape_component"] = 2.0 * work["absolute_error"] / denominator
    work["mase_component"] = work["absolute_error"] / work["scale_m3"].clip(lower=1e-9)
    grouped = work.groupby(["split", "model"], sort=True)
    result = grouped.agg(
        observations=("actual_m3", "size"),
        mae_m3=("absolute_error", "mean"),
        mse=("squared_error", "mean"),
        smape=("smape_component", "mean"),
        mase=("mase_component", "mean"),
    ).reset_index()
    result["rmse_m3"] = np.sqrt(result.pop("mse"))
    return result[["split", "model", "observations", "mae_m3", "rmse_m3", "smape", "mase"]]

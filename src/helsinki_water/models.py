from __future__ import annotations

import warnings
from dataclasses import dataclass
from itertools import product
from math import fsum
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX

FloatArray = NDArray[np.float64]
MODEL_NAMES = ("seasonal_naive", "ets", "sarima_paper", "harmonic_ridge")


@dataclass(frozen=True)
class ForecastResult:
    values: FloatArray
    details: dict[str, str | float | int]


def seasonal_naive(values: FloatArray, horizon: int) -> ForecastResult:
    if len(values) < 12:
        raise ValueError("Seasonal naive requires at least 12 months")
    forecast = np.asarray([values[-12 + (step % 12)] for step in range(horizon)], dtype=float)
    return ForecastResult(np.clip(forecast, 0.0, None), {"seasonalPeriod": 12})


def ets(values: FloatArray, horizon: int) -> ForecastResult:
    """Deterministic grid-fitted ETS(A,Ad,A) without platform optimizers."""
    seasonal_period = 12
    if len(values) < 2 * seasonal_period:
        raise ValueError("ETS requires at least 24 months")
    initial_level = fsum(float(item) for item in values[:seasonal_period]) / seasonal_period
    initial_trend = (
        fsum(
            (float(values[index + seasonal_period]) - float(values[index])) / seasonal_period
            for index in range(seasonal_period)
        )
        / seasonal_period
    )
    initial_season = [float(values[index]) - initial_level for index in range(seasonal_period)]
    grid = product(
        (0.10, 0.25, 0.50, 0.75),
        (0.01, 0.05, 0.15),
        (0.05, 0.20, 0.40),
        (0.90, 0.95, 0.98),
    )
    best: tuple[float, float, float, float, float, float, float, list[float]] | None = None
    for alpha, beta, gamma, phi in grid:
        level = initial_level
        trend = initial_trend
        season = initial_season.copy()
        squared_errors: list[float] = []
        for index in range(seasonal_period, len(values)):
            previous_level = level
            previous_trend = trend
            previous_season = season[index % seasonal_period]
            prediction = previous_level + phi * previous_trend + previous_season
            error = float(values[index]) - prediction
            squared_errors.append(error * error)
            level = alpha * (float(values[index]) - previous_season) + (1.0 - alpha) * (
                previous_level + phi * previous_trend
            )
            trend = beta * (level - previous_level) + (1.0 - beta) * phi * previous_trend
            season[index % seasonal_period] = (
                gamma * (float(values[index]) - level) + (1.0 - gamma) * previous_season
            )
        sse = fsum(squared_errors)
        candidate = (sse, alpha, beta, gamma, phi, level, trend, season)
        if best is None or candidate[:5] < best[:5]:
            best = candidate
    if best is None:
        raise RuntimeError("Deterministic ETS grid is empty")
    sse, alpha, beta, gamma, phi, level, trend, season = best
    damped_sum = 0.0
    forecast_values: list[float] = []
    for step in range(1, horizon + 1):
        damped_sum += phi**step
        seasonal = season[(len(values) + step - 1) % seasonal_period]
        forecast_values.append(max(0.0, level + damped_sum * trend + seasonal))
    return ForecastResult(
        np.asarray(forecast_values, dtype=float),
        {
            "specification": "ETS(A,Ad,A), deterministic grid",
            "sse": sse,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "phi": phi,
        },
    )


SARIMA_CANDIDATES = (
    ((0, 1, 1), (0, 1, 1, 12)),
    ((1, 0, 0), (0, 1, 1, 12)),
    ((1, 1, 0), (1, 0, 0, 12)),
    ((1, 1, 1), (0, 1, 1, 12)),
    ((2, 0, 0), (1, 0, 0, 12)),
    ((0, 1, 2), (0, 1, 1, 12)),
)


def sarima_paper(values: FloatArray, horizon: int) -> ForecastResult:
    """Independent AIC-selected SARIMA reproduction of Ristow et al. (2021)."""
    best: tuple[float, Any, tuple[int, int, int], tuple[int, int, int, int]] | None = None
    for order, seasonal_order in SARIMA_CANDIDATES:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = SARIMAX(
                    values,
                    order=order,
                    seasonal_order=seasonal_order,
                    trend="n",
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(disp=False, maxiter=150)
            if np.isfinite(fitted.aic) and (best is None or fitted.aic < best[0]):
                best = (float(fitted.aic), fitted, order, seasonal_order)
        except (ValueError, np.linalg.LinAlgError):
            continue
    if best is None:
        fallback = seasonal_naive(values, horizon)
        return ForecastResult(fallback.values, {"fallback": "seasonal_naive"})
    aic, fitted, order, seasonal_order = best
    forecast = np.asarray(fitted.forecast(horizon), dtype=float)
    return ForecastResult(
        np.clip(forecast, 0.0, None),
        {"aic": aic, "order": str(order), "seasonalOrder": str(seasonal_order)},
    )


def _ridge_row(history: FloatArray, month_number: int) -> FloatArray:
    angle = 2.0 * np.pi * ((month_number - 1) % 12) / 12.0
    return np.asarray(
        [
            history[-1],
            history[-2],
            history[-12],
            float(np.mean(history[-3:])),
            float(np.mean(history[-12:])),
            np.sin(angle),
            np.cos(angle),
            len(history) / 12.0,
        ],
        dtype=float,
    )


def harmonic_ridge(values: FloatArray, horizon: int) -> ForecastResult:
    if len(values) < 24:
        raise ValueError("Harmonic ridge requires at least 24 months")
    features: list[FloatArray] = []
    targets: list[float] = []
    for index in range(12, len(values)):
        features.append(_ridge_row(values[:index], index + 1))
        targets.append(float(values[index]))
    model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    model.fit(np.vstack(features), np.asarray(targets))
    history = values.astype(float).copy()
    forecast: list[float] = []
    for _ in range(horizon):
        prediction = float(model.predict(_ridge_row(history, len(history) + 1)[None, :])[0])
        prediction = max(0.0, prediction)
        forecast.append(prediction)
        history = np.append(history, prediction)
    return ForecastResult(np.asarray(forecast), {"alpha": 10.0, "features": 8})


def forecast(name: str, values: FloatArray, horizon: int) -> ForecastResult:
    functions = {
        "seasonal_naive": seasonal_naive,
        "ets": ets,
        "sarima_paper": sarima_paper,
        "harmonic_ridge": harmonic_ridge,
    }
    if name not in functions:
        raise ValueError(f"Unknown model: {name}")
    return functions[name](values, horizon)

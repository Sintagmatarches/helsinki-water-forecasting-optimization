from __future__ import annotations

import numpy as np

from helsinki_water.models import MODEL_NAMES, forecast


def seasonal_values() -> np.ndarray:
    months = np.arange(72)
    return 100.0 + 15.0 * np.sin(2.0 * np.pi * months / 12.0) + 0.2 * months


def test_every_model_returns_finite_nonnegative_forecast() -> None:
    values = seasonal_values()
    for model in MODEL_NAMES:
        result = forecast(model, values, 6)
        assert result.values.shape == (6,)
        assert np.isfinite(result.values).all()
        assert (result.values >= 0).all()


def test_forecast_uses_only_training_values() -> None:
    train = seasonal_values()
    first = forecast("harmonic_ridge", train, 3).values
    future_a = np.append(train, [1.0, 1.0, 1.0])
    future_b = np.append(train, [9999.0, 9999.0, 9999.0])
    second = forecast("harmonic_ridge", future_a[:-3], 3).values
    third = forecast("harmonic_ridge", future_b[:-3], 3).values
    np.testing.assert_allclose(first, second)
    np.testing.assert_allclose(first, third)


def test_deterministic_ets_is_exactly_repeatable() -> None:
    values = seasonal_values()
    first = forecast("ets", values, 12)
    second = forecast("ets", values.copy(), 12)
    np.testing.assert_array_equal(first.values, second.values)
    assert first.details == second.details
    assert first.details["specification"] == "ETS(A,Ad,A), deterministic grid"

"""
Tests for the interactive short-series predictor (predict_series).

Key guarantees: the tree models must actually learn — continue a trend instead
of flatlining, and reproduce a seasonal cycle — after the detrend step.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.forecasting.simple import MODELS, predict_series

TREND = [100, 120, 110, 130, 125, 140, 135, 150, 145, 160, 155, 170]
SEASONAL = [100, 80, 60] * 4


@pytest.mark.parametrize("model", MODELS)
def test_returns_requested_length(model):
    out = predict_series(TREND, steps=6, model=model)
    assert len(out) == 6
    assert all(v >= 0 for v in out)


@pytest.mark.parametrize("model", ["xgboost", "random_forest", "arima"])
def test_trending_series_keeps_rising_not_flat(model):
    out = predict_series(TREND, steps=6, model=model)
    # Must not flatline at the last observed value...
    assert len(set(out)) > 1, f"{model} produced a flat forecast"
    # ...and should extend upward beyond the last point (~170).
    assert out[-1] > TREND[-1] * 0.98
    assert out[-1] > out[0]


@pytest.mark.parametrize("model", ["xgboost", "random_forest"])
def test_seasonal_cycle_is_reproduced(model):
    out = predict_series(SEASONAL, steps=6, model=model)
    # A wide spread means the model captured the 100/80/60 swing, not a mean line.
    assert (max(out) - min(out)) > 20


def test_moving_average_is_smoother_than_trees():
    ma = predict_series(TREND, steps=6, model="moving_average")
    assert np.std(np.diff(ma)) < np.std(np.diff(TREND))


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        predict_series(TREND, steps=3, model="prophet")


def test_too_short_raises():
    with pytest.raises(ValueError):
        predict_series([5], steps=3, model="xgboost")


@pytest.mark.parametrize("model", ["xgboost", "random_forest"])
def test_configurable_lags_nonflat_on_trend(model):
    # A longer trending series so lags=10 has enough history to use.
    long_trend = [100 + 5 * i + (10 if i % 3 == 0 else 0) for i in range(30)]
    out = predict_series(long_trend, steps=6, model=model, lags=10)
    assert len(out) == 6
    assert all(v >= 0 for v in out)
    assert len(set(out)) > 1, f"{model} produced a flat forecast with lags=10"


@pytest.mark.parametrize("model", MODELS)
def test_lags_larger_than_series_is_graceful(model):
    # lags far exceeding the series length must not crash.
    out = predict_series(TREND, steps=4, model=model, lags=500)
    assert len(out) == 4
    assert all(v >= 0 for v in out)


@pytest.mark.parametrize("model", MODELS)
def test_default_lags_none_still_works(model):
    out = predict_series(TREND, steps=6, model=model, lags=None)
    assert len(out) == 6
    assert all(v >= 0 for v in out)


def test_moving_average_respects_lag_window():
    # lags controls the MA window; a window of 1 makes it a naive last-value carry.
    out = predict_series(TREND, steps=3, model="moving_average", lags=1)
    assert out == [TREND[-1]] * 3

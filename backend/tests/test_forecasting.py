"""
Tests for the demand forecasting module.

Uses a deterministic synthetic series that mirrors the seed data's planted
patterns: weekly seasonality (higher Mon-Fri, lower Sat-Sun) plus mild noise,
and an optional stockout window that must be excluded from training.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from app.forecasting import MODEL_TYPES, forecast_demand
from app.forecasting.features import build_daily_series, make_supervised
from app.forecasting.service import MIN_TRAINING_DAYS


def make_series(days: int, base: float = 100.0, noise: float = 0.0, seed: int = 42):
    """Weekly-seasonal synthetic consumption, deterministic."""
    rng = np.random.default_rng(seed)
    start = date(2024, 1, 1)  # a Monday
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        weekday = d.weekday()
        seasonal = base if weekday < 5 else base * 0.55  # weekend dip
        val = seasonal + (rng.normal(0, noise) if noise else 0.0)
        out.append((d, max(0.0, val)))
    return out


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def test_build_daily_series_is_gapfree():
    history = make_series(30)
    # Punch a hole in the middle.
    history = [hd for i, hd in enumerate(history) if i != 15]
    s = build_daily_series(history)
    # Continuous daily index, no NaNs.
    assert (s.index.to_series().diff().dropna() == np.timedelta64(1, "D")).all()
    assert not s.isna().any()


def test_stockout_dates_excluded_and_interpolated():
    history = make_series(30)
    stockout = {history[10][0], history[11][0]}
    s = build_daily_series(history, stockout_dates=stockout)
    # Interpolated values should not be the artificial zero of a stockout.
    assert s.loc[str(list(stockout)[0])] > 0


def test_make_supervised_shapes():
    s = build_daily_series(make_series(40))
    X, y = make_supervised(s)
    assert len(X) == len(y) > 0
    assert not X.isna().any().any()


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model_type", MODEL_TYPES)
def test_forecast_shape_and_bounds(model_type):
    result = forecast_demand(make_series(90, noise=4.0), horizon_days=14, model_type=model_type)
    assert result.model_type == model_type
    assert len(result.points) == 14
    for p in result.points:
        assert p.p10 <= p.p50 <= p.p90          # monotone quantiles
        assert p.p10 >= 0                         # non-negative demand
    assert 0.0 <= result.confidence_score <= 1.0
    assert 0.0 <= result.data_sufficiency_score <= 1.0
    assert 0.0 <= result.series_stability_score <= 1.0


@pytest.mark.parametrize("model_type", MODEL_TYPES)
def test_forecast_learns_weekly_seasonality(model_type):
    # Clean seasonal series -> weekday p50 should clearly exceed weekend p50.
    result = forecast_demand(make_series(120, noise=2.0), horizon_days=14, model_type=model_type)
    weekday = [p.p50 for p in result.points if date.fromisoformat(p.forecast_date.isoformat()).weekday() < 5]
    weekend = [p.p50 for p in result.points if date.fromisoformat(p.forecast_date.isoformat()).weekday() >= 5]
    assert np.mean(weekday) > np.mean(weekend) * 1.2


def test_short_series_falls_back_to_seasonal_naive():
    result = forecast_demand(make_series(MIN_TRAINING_DAYS - 5), horizon_days=7)
    assert result.model_type == "seasonal_naive"
    assert result.holdout_mape is None
    assert len(result.points) == 7


def test_backtest_mape_present_for_long_series():
    result = forecast_demand(make_series(120, noise=3.0), horizon_days=14, model_type="random_forest")
    assert result.holdout_mape is not None
    assert result.holdout_mape >= 0.0


def test_stable_series_scores_higher_confidence_than_volatile():
    stable = forecast_demand(make_series(120, noise=1.0), horizon_days=14)
    volatile = forecast_demand(make_series(120, noise=40.0), horizon_days=14)
    assert stable.series_stability_score > volatile.series_stability_score


def test_as_dict_is_json_shaped():
    result = forecast_demand(make_series(90, noise=3.0), horizon_days=7)
    d = result.as_dict()
    assert d["horizon_days"] == 7
    assert len(d["points"]) == 7
    assert set(d["points"][0]) == {"forecast_date", "p10", "p50", "p90"}


def test_unknown_model_type_raises():
    from app.forecasting.models import QuantileForecaster

    with pytest.raises(ValueError):
        QuantileForecaster(model_type="prophet")

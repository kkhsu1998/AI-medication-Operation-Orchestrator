"""
Tests for the multivariate feature-lattice forecaster (encoders, normalization,
derived formula columns).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from app.forecasting.lattice import train_and_forecast


def make_rows(n_locations=2, days=120, seed=1):
    rng = np.random.default_rng(seed)
    start = date(2025, 1, 1)
    rows = []
    for loc in range(n_locations):
        base = 50 + 40 * loc
        for i in range(days):
            d = start + timedelta(days=i)
            weekly = 1.0 if d.weekday() < 5 else 0.6
            rows.append((f"Loc{loc}", d, max(0.0, base * weekly + rng.normal(0, 4))))
    return rows


BASE_FEATURES = [
    {"type": "lag", "lag": 1},
    {"type": "lag", "lag": 7},
    {"type": "calendar", "kind": "dow"},
]


@pytest.mark.parametrize("model", ["xgboost", "random_forest"])
@pytest.mark.parametrize("norm", ["none", "standard", "minmax"])
def test_train_and_forecast_shapes(model, norm):
    out = train_and_forecast(make_rows(), BASE_FEATURES, model=model, normalization=norm, steps=10)
    assert len(out["predictions"]) == 10
    assert all(p["value"] >= 0 for p in out["predictions"])
    assert out["n_train_rows"] > 0
    assert out["features_used"]


def test_onehot_encoder_adds_location_columns():
    feats = BASE_FEATURES + [{"type": "categorical", "column": "location", "encoder": "onehot"}]
    out = train_and_forecast(make_rows(n_locations=3), feats, model="xgboost", steps=5)
    loc_cols = [f for f in out["features_used"] if f.startswith("loc_")]
    assert len(loc_cols) == 3  # one column per location


def test_ordinal_encoder_adds_single_column():
    feats = BASE_FEATURES + [{"type": "categorical", "column": "location", "encoder": "ordinal"}]
    out = train_and_forecast(make_rows(n_locations=3), feats, model="xgboost", steps=5)
    assert "loc_ord" in out["features_used"]


def test_derived_formula_column_is_used():
    feats = BASE_FEATURES + [{"type": "derived", "name": "blend", "formula": "lag_1 * 0.5 + lag_7 * 0.5"}]
    out = train_and_forecast(make_rows(), feats, model="xgboost", steps=5)
    assert "blend" in out["features_used"]


def test_invalid_formula_is_skipped_not_fatal():
    feats = BASE_FEATURES + [{"type": "derived", "name": "bad", "formula": "this is not valid $$"}]
    out = train_and_forecast(make_rows(), feats, model="xgboost", steps=5)
    assert "bad" not in out["features_used"]  # skipped
    assert len(out["predictions"]) == 5


def test_too_short_history_raises():
    with pytest.raises(ValueError):
        train_and_forecast(make_rows(n_locations=1, days=10), BASE_FEATURES, steps=5)

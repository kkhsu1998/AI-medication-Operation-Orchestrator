"""
Feature engineering for demand forecasting.

Tree models (RandomForest / XGBoost) do not model time directly, so we turn a
univariate daily consumption series into a supervised tabular problem using:

  * lag features       -- consumption `n` days ago (captures recent level)
  * rolling statistics -- 7/14-day mean & std (captures smoothed level + volatility)
  * calendar features  -- day-of-week and weekend flag (captures the planted
                          weekly seasonality: higher Mon-Fri, lower Sat-Sun)

The same row-builder is used both for training and for recursive multi-step
forecasting, so features are always computed identically.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

# Lags (in days) used as features. 1/2 capture recent momentum, 7/14 capture
# same-weekday-last-week(s) which is where the weekly seasonality lives.
LAGS: tuple[int, ...] = (1, 2, 7, 14)
ROLL_WINDOWS: tuple[int, ...] = (7, 14)

FEATURE_NAMES: list[str] = (
    [f"lag_{l}" for l in LAGS]
    + [f"rollmean_{w}" for w in ROLL_WINDOWS]
    + [f"rollstd_{w}" for w in ROLL_WINDOWS]
    + ["dow", "is_weekend"]
)


def build_daily_series(
    history: Iterable[Tuple[date, float]],
    stockout_dates: Optional[set[date]] = None,
) -> pd.Series:
    """
    Turn raw (date, quantity) pairs into a continuous, gap-free daily series.

    Stockout dates are treated as missing (the schema marks them
    ``is_stockout_period`` and says to exclude them from training) and are
    interpolated over so they don't teach the model an artificial zero.
    """
    stockout_dates = stockout_dates or set()
    if not history:
        raise ValueError("history is empty")

    s = pd.Series(
        {pd.Timestamp(d): float(q) for d, q in history if d not in stockout_dates}
    ).sort_index()
    if s.empty:
        raise ValueError("history is empty after removing stockout dates")

    # Reindex onto every calendar day between first and last observation so the
    # lag arithmetic is exact, then fill the holes.
    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(full_idx)
    s = s.interpolate(method="linear").ffill().bfill()
    s.name = "quantity"
    return s


def row_features(series: pd.Series, target_date: pd.Timestamp) -> dict[str, float]:
    """
    Compute the feature row for `target_date` using only values strictly before
    it. Returns NaN for lags that reach past the start of the series.
    """
    feats: dict[str, float] = {}
    for lag in LAGS:
        d = target_date - pd.Timedelta(days=lag)
        feats[f"lag_{lag}"] = float(series.get(d, np.nan))

    prior = series.loc[series.index < target_date]
    for w in ROLL_WINDOWS:
        window = prior.tail(w)
        feats[f"rollmean_{w}"] = float(window.mean()) if len(window) else np.nan
        feats[f"rollstd_{w}"] = float(window.std(ddof=0)) if len(window) else 0.0

    dow = int(target_date.dayofweek)
    feats["dow"] = float(dow)
    feats["is_weekend"] = 1.0 if dow >= 5 else 0.0
    return feats


def make_supervised(series: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build the (X, y) training matrix: one row per date that has all lags
    available, features from the past, target = that day's consumption.
    """
    rows, targets, index = [], [], []
    max_lag = max(LAGS)
    for ts in series.index[max_lag:]:
        feats = row_features(series, ts)
        if any(np.isnan(v) for v in feats.values()):
            continue
        rows.append(feats)
        targets.append(float(series.loc[ts]))
        index.append(ts)

    X = pd.DataFrame(rows, index=index, columns=FEATURE_NAMES)
    y = pd.Series(targets, index=index, name="quantity")
    return X, y

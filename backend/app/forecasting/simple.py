"""
Generic short-series forecasters for the interactive "Predict N steps" button.

Operates directly on the numeric series shown in the Forecast table (monthly
values), so it suits short series (~12 points) — unlike the daily lag-14
forecaster in service.py. Four selectable models:

  moving_average -- recursive rolling mean of the last window
  random_forest  -- sklearn RandomForest on lag features, recursive
  xgboost        -- XGBoost on lag features, recursive
  arima          -- lightweight ARIMA(p,1,0): difference, AR(p) via least
                    squares, then integrate (no statsmodels dependency)

All return a list of `steps` forecasts, clamped to non-negative.
"""

from __future__ import annotations

import numpy as np

MODELS = ("moving_average", "random_forest", "xgboost", "arima")


# Daily-appropriate lags: 1/2/3 for momentum, 7/14 for weekly seasonality.
CANDIDATE_LAGS = (1, 2, 3, 7, 14)


def _lags_for(n: int) -> list[int]:
    return [l for l in CANDIDATE_LAGS if l < n - 1] or [1]


def _resolve_lags(n: int, lags: int | None) -> list[int]:
    """Pick the lag set for the tree models.

    When `lags` is a positive int L, use contiguous lags [1, 2, ..., min(L, n-2)]
    ("all lags up to L"), always keeping at least lag [1]. When `lags` is None or
    0, fall back to the adaptive candidate set.
    """
    if lags and lags > 0:
        maxlag = min(int(lags), n - 2)
        maxlag = max(1, maxlag)
        return list(range(1, maxlag + 1))
    return _lags_for(n)


def _moving_average(y: np.ndarray, steps: int, lags: int | None = None) -> list[float]:
    n = len(y)
    if lags and lags > 0:
        window = max(1, min(int(lags), n))
    else:
        window = min(7, n)  # a 7-day window suits daily data
    hist = list(y)
    out = []
    for _ in range(steps):
        val = float(np.mean(hist[-window:]))
        out.append(val)
        hist.append(val)
    return out


def _tree(y: np.ndarray, steps: int, kind: str, lags: int | None = None) -> list[float]:
    """
    Tree models can't extrapolate beyond their training range, so on a trending
    series a naive lag model flattens at the last seen value. We detrend first:
    fit a linear trend, model the *residuals* (seasonality/curvature) with the
    tree via lag features, then add the extrapolated trend back on forecast — so
    the prediction actually continues instead of going flat.

    When `lags` is a positive int L, use contiguous lags [1..min(L, n-2)];
    otherwise fall back to the adaptive candidate set.
    """
    n = len(y)
    lag_set = _resolve_lags(n, lags)
    maxlag = max(lag_set)
    if n < maxlag + 2:
        return _moving_average(y, steps, lags)

    t = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(t, y, 1)  # linear trend
    resid = y - (slope * t + intercept)

    X = np.array([[resid[i - l] for l in lag_set] for i in range(maxlag, n)])
    target = np.array([resid[i] for i in range(maxlag, n)])

    if kind == "random_forest":
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(n_estimators=300, min_samples_leaf=1, random_state=42)
    else:
        from xgboost import XGBRegressor

        model = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.08, random_state=42)
    model.fit(X, target)

    hist = list(resid)
    out = []
    for k in range(steps):
        feat = np.array([[hist[-l] for l in lag_set]])
        r = float(model.predict(feat)[0])
        hist.append(r)
        trend = slope * (n + k) + intercept
        out.append(max(0.0, trend + r))
    return out


def _arima(y: np.ndarray, steps: int, lags: int | None = None) -> list[float]:
    """ARIMA(p,1,0): difference once, AR(p) by least squares, integrate back.

    When `lags` is a positive int L, use it as the AR order p, capped at
    min(L, len(diffs)//2) with a floor of 1; otherwise default to p <= 2.
    """
    d = np.diff(y)
    if len(d) < 3:
        return _moving_average(y, steps, lags)
    if lags and lags > 0:
        p = max(1, min(int(lags), len(d) // 2, len(d) - 1))
    else:
        p = max(1, min(2, len(d) - 1))
    X = np.array([d[i - p:i] for i in range(p, len(d))])
    t = np.array([d[i] for i in range(p, len(d))])
    coef, *_ = np.linalg.lstsq(X, t, rcond=None)

    diffs = list(d)
    last = float(y[-1])
    out = []
    for _ in range(steps):
        nd = float(np.array(diffs[-p:]) @ coef)
        last = max(0.0, last + nd)
        out.append(last)
        diffs.append(nd)
    return out


def predict_series(
    series: list[float], steps: int, model: str, lags: int | None = None
) -> list[float]:
    y = np.array([float(v) for v in series], dtype=float)
    if len(y) < 2:
        raise ValueError("need at least 2 points to forecast")
    if model == "moving_average":
        out = _moving_average(y, steps, lags)
    elif model in ("random_forest", "xgboost"):
        out = _tree(y, steps, model, lags)
    elif model == "arima":
        out = _arima(y, steps, lags)
    else:
        raise ValueError(f"unknown model {model!r}; expected one of {MODELS}")
    return [round(v, 1) for v in out]

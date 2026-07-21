"""
Multivariate feature-lattice forecaster.

Turns the daily consumption panel for one drug — rows of (location, day,
quantity) — into a configurable feature matrix and trains a tree model on it:

  * lag features       -- quantity k days ago (per location)
  * calendar features  -- day-of-week / month / day-of-month
  * categorical encoders for `location` -- one-hot or ordinal
  * normalization      -- standard (z-score) or min-max, over numeric features
  * derived columns    -- Excel-like formulas over the other feature columns
                          (e.g. "lag_1 * 0.5 + lag_7"), the "feature lattice"

Forecasting is recursive per location (predicted values feed the next day's
lags), then summed to a daily total to match the chart.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

NORMALIZERS = ("none", "standard", "minmax")


def _scaler(kind: str):
    if kind == "standard":
        from sklearn.preprocessing import StandardScaler

        return StandardScaler()
    if kind == "minmax":
        from sklearn.preprocessing import MinMaxScaler

        return MinMaxScaler()
    return None


class FeatureSpec:
    """One feature request from the workbench."""

    def __init__(self, d: dict):
        self.type = d.get("type")
        self.lag = int(d.get("lag") or 1)
        self.kind = d.get("kind") or "dow"            # calendar
        self.column = d.get("column") or "location"   # categorical
        self.encoder = d.get("encoder") or "onehot"
        self.name = d.get("name") or ""               # derived
        self.formula = d.get("formula") or ""


def _base_frame(rows: list[tuple[str, date, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["location", "day", "quantity"])
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values(["location", "day"]).reset_index(drop=True)


def _add_calendar(df: pd.DataFrame, kind: str) -> str:
    col = f"cal_{kind}"
    if kind == "dow":
        df[col] = df["day"].dt.dayofweek
    elif kind == "month":
        df[col] = df["day"].dt.month
    else:
        df[col] = df["day"].dt.day
    return col


def build_matrix(df: pd.DataFrame, specs: list[FeatureSpec]):
    """Return (X, y, numeric_cols, onehot_cols, derived_specs, meta)."""
    numeric_cols: list[str] = []
    onehot_cols: list[str] = []
    ordinal_map: dict[str, int] = {}
    derived: list[FeatureSpec] = []
    lag_ints: list[int] = []
    cal_kinds: list[str] = []

    for s in specs:
        if s.type == "lag":
            col = f"lag_{s.lag}"
            df[col] = df.groupby("location")["quantity"].shift(s.lag)
            if col not in numeric_cols:
                numeric_cols.append(col)
                lag_ints.append(s.lag)
        elif s.type == "calendar":
            col = _add_calendar(df, s.kind)
            if col not in numeric_cols:
                numeric_cols.append(col)
                cal_kinds.append(s.kind)
        elif s.type == "categorical":
            if s.encoder == "ordinal":
                cats = sorted(df["location"].unique())
                ordinal_map = {c: i for i, c in enumerate(cats)}
                df["loc_ord"] = df["location"].map(ordinal_map)
                if "loc_ord" not in numeric_cols:
                    numeric_cols.append("loc_ord")
            else:  # onehot
                dummies = pd.get_dummies(df["location"], prefix="loc")
                for c in dummies.columns:
                    df[c] = dummies[c].astype(float)
                onehot_cols = list(dummies.columns)
        elif s.type == "derived":
            derived.append(s)

    # Ensure at least a lag_1 so the model has signal.
    if not lag_ints:
        df["lag_1"] = df.groupby("location")["quantity"].shift(1)
        numeric_cols.insert(0, "lag_1")
        lag_ints.append(1)

    # Derived / formula columns evaluate over the already-built feature columns.
    derived_cols: list[str] = []
    for s in derived:
        name = s.name or f"derived_{len(derived_cols)}"
        try:
            df[name] = df.eval(s.formula)
            numeric_cols.append(name)
            derived_cols.append(name)
        except Exception:
            pass  # skip invalid formulas rather than failing the whole train

    df = df.dropna(subset=numeric_cols).reset_index(drop=True)
    meta = {
        "ordinal_map": ordinal_map,
        "derived": [(c.name, c.formula) for c in derived],
        "onehot_cols": onehot_cols,
        "lags": sorted(lag_ints),
        "cal_kinds": cal_kinds,
    }
    return df, numeric_cols, onehot_cols, meta


def _fit_model(kind: str, X: np.ndarray, y: np.ndarray):
    if kind == "random_forest":
        from sklearn.ensemble import RandomForestRegressor

        m = RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=42, n_jobs=-1)
    else:
        from xgboost import XGBRegressor

        m = XGBRegressor(n_estimators=250, max_depth=4, learning_rate=0.08, random_state=42, n_jobs=-1)
    m.fit(X, y)
    return m


def train_and_forecast(
    rows: list[tuple[str, date, float]],
    specs: list[dict],
    model: str = "xgboost",
    normalization: str = "standard",
    steps: int = 14,
) -> dict:
    if len(rows) < 30:
        raise ValueError("not enough history for a multivariate model")
    feature_specs = [FeatureSpec(s) for s in specs]
    df = _base_frame(rows)
    df, numeric_cols, onehot_cols, meta = build_matrix(df, feature_specs)
    if df.empty:
        raise ValueError("no rows left after feature construction")

    scaler = _scaler(normalization)
    Xnum = df[numeric_cols].to_numpy(dtype=float)
    if scaler is not None and Xnum.shape[1]:
        Xnum = scaler.fit_transform(Xnum)
    Xoh = df[onehot_cols].to_numpy(dtype=float) if onehot_cols else np.empty((len(df), 0))
    X = np.hstack([Xnum, Xoh])
    y = df["quantity"].to_numpy(dtype=float)

    fitted = _fit_model(model, X, y)

    # Recursive per-location forecast, then aggregate to a daily total.
    lag_list = meta["lags"]
    cal_kinds = meta["cal_kinds"]
    last_day = df["day"].max()
    locations = sorted(df["location"].unique())

    history_by_loc = {loc: list(df[df["location"] == loc].sort_values("day")["quantity"]) for loc in locations}
    ordinal_map = meta["ordinal_map"]
    future_totals: dict[str, float] = {}

    for loc in locations:
        hist = history_by_loc[loc][:]
        for k in range(1, steps + 1):
            fday = last_day + pd.Timedelta(days=k)
            feats: dict[str, float] = {}
            for lag in lag_list:
                feats[f"lag_{lag}"] = hist[-lag] if len(hist) >= lag else hist[-1]
            for kind in cal_kinds:
                feats[f"cal_{kind}"] = (fday.dayofweek if kind == "dow" else fday.month if kind == "month" else fday.day)
            if "loc_ord" in numeric_cols:
                feats["loc_ord"] = ordinal_map.get(loc, 0)
            row = pd.DataFrame([feats])
            for name, formula in meta["derived"]:
                try:
                    row[name] = row.eval(formula)
                except Exception:
                    row[name] = 0.0
            xnum = row[numeric_cols].to_numpy(dtype=float)
            if scaler is not None and xnum.shape[1]:
                xnum = scaler.transform(xnum)
            xoh = np.array([[1.0 if c == f"loc_{loc}" else 0.0 for c in onehot_cols]]) if onehot_cols else np.empty((1, 0))
            pred = max(0.0, float(fitted.predict(np.hstack([xnum, xoh]))[0]))
            hist.append(pred)
            key = fday.date().isoformat()
            future_totals[key] = future_totals.get(key, 0.0) + pred

    hist_daily = df.groupby(df["day"].dt.date)["quantity"].sum()
    history = [{"date": d.isoformat(), "value": round(float(v), 1)} for d, v in hist_daily.tail(120).items()]
    predictions = [{"date": d, "value": round(v, 1)} for d, v in sorted(future_totals.items())]

    feature_names = numeric_cols + onehot_cols
    return {
        "model": model,
        "normalization": normalization,
        "steps": steps,
        "n_train_rows": int(len(df)),
        "features_used": feature_names,
        "history": history,
        "predictions": predictions,
    }

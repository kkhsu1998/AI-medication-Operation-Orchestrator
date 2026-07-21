"""
Demand forecasting service.

Public entry point: ``forecast_demand(history, ...)`` — takes a raw daily
consumption series for one (medication, location) and returns a multi-step
p10/p50/p90 forecast plus confidence scoring that mirrors the
``forecast_models`` schema (holdout_mape, data_sufficiency_score,
series_stability_score, confidence_score).

Multi-step forecasting is recursive: each predicted p50 is appended to the
working series so the next day's lag/rolling features stay consistent. Weekly
seasonality is carried by the day-of-week feature, not by feeding it a trend it
can't extrapolate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .features import build_daily_series, make_supervised, row_features
from .models import QUANTILES, QuantileForecaster

# Below this many usable days we refuse to model and fall back to a
# seasonal-naive average, because tree features (14-day lag) need history.
MIN_TRAINING_DAYS = 21
# Data-sufficiency saturates at this many days of history.
SUFFICIENCY_SATURATION_DAYS = 90
# Days held out at the tail for the backtest / MAPE.
DEFAULT_HOLDOUT_DAYS = 14


@dataclass
class ForecastPoint:
    forecast_date: date
    p10: float
    p50: float
    p90: float


@dataclass
class ForecastResult:
    model_type: str
    horizon_days: int
    training_data_days: int
    holdout_mape: Optional[float]
    data_sufficiency_score: float
    series_stability_score: float
    confidence_score: float
    points: List[ForecastPoint] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "model_type": self.model_type,
            "horizon_days": self.horizon_days,
            "training_data_days": self.training_data_days,
            "holdout_mape": self.holdout_mape,
            "data_sufficiency_score": self.data_sufficiency_score,
            "series_stability_score": self.series_stability_score,
            "confidence_score": self.confidence_score,
            "points": [
                {
                    "forecast_date": p.forecast_date.isoformat(),
                    "p10": round(p.p10, 2),
                    "p50": round(p.p50, 2),
                    "p90": round(p.p90, 2),
                }
                for p in self.points
            ],
        }


def _recursive_forecast(
    model: QuantileForecaster, series: pd.Series, horizon_days: int
) -> List[ForecastPoint]:
    """Predict `horizon_days` ahead, feeding p50 back in as the realized value."""
    working = series.copy()
    points: List[ForecastPoint] = []
    last = working.index.max()

    for step in range(1, horizon_days + 1):
        target = last + pd.Timedelta(days=step)
        feats = row_features(working, target)
        X = pd.DataFrame([feats])
        q = model.predict_quantiles(X)
        p10, p50, p90 = float(q[0.10][0]), float(q[0.50][0]), float(q[0.90][0])
        points.append(
            ForecastPoint(forecast_date=target.date(), p10=p10, p50=p50, p90=p90)
        )
        # Extend the working series with the central estimate for the next step.
        working.loc[target] = p50

    return points


def _seasonal_naive(series: pd.Series, horizon_days: int) -> List[ForecastPoint]:
    """Fallback for short series: repeat the day-of-week average with a spread."""
    by_dow = series.groupby(series.index.dayofweek)
    dow_mean = by_dow.mean()
    dow_std = by_dow.std(ddof=0).fillna(0.0)
    overall_std = float(series.std(ddof=0) or 0.0)
    last = series.index.max()

    points: List[ForecastPoint] = []
    for step in range(1, horizon_days + 1):
        target = last + pd.Timedelta(days=step)
        dow = target.dayofweek
        mean = float(dow_mean.get(dow, series.mean()))
        std = float(dow_std.get(dow, overall_std)) or overall_std
        points.append(
            ForecastPoint(
                forecast_date=target.date(),
                p10=max(0.0, mean - 1.2816 * std),
                p50=max(0.0, mean),
                p90=max(0.0, mean + 1.2816 * std),
            )
        )
    return points


def _backtest_mape(
    model_type: str, series: pd.Series, holdout_days: int
) -> Optional[float]:
    """Train on all-but-last-`holdout_days`, forecast that tail, return MAPE."""
    if len(series) <= MIN_TRAINING_DAYS + holdout_days:
        return None

    train = series.iloc[:-holdout_days]
    actual = series.iloc[-holdout_days:]
    X, y = make_supervised(train)
    if len(X) == 0:
        return None

    model = QuantileForecaster(model_type=model_type).fit(X, y)
    preds = _recursive_forecast(model, train, holdout_days)
    pred_p50 = np.array([p.p50 for p in preds])
    actual_vals = actual.values.astype(float)

    # Symmetric MAPE-ish: guard against divide-by-zero on zero-demand days.
    denom = np.where(actual_vals == 0, 1.0, np.abs(actual_vals))
    mape = float(np.mean(np.abs(pred_p50 - actual_vals) / denom))
    return round(mape, 4)


def _data_sufficiency(training_days: int) -> float:
    return round(min(1.0, training_days / SUFFICIENCY_SATURATION_DAYS), 3)


def _series_stability(series: pd.Series) -> float:
    """Higher when demand is steadier. Based on coefficient of variation."""
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    if mean <= 0:
        return 0.0
    cv = std / mean
    return round(float(1.0 / (1.0 + cv)), 3)


def _confidence(
    sufficiency: float, stability: float, mape: Optional[float]
) -> float:
    """Composite 0..1. MAPE (when available) discounts an otherwise good score."""
    base = 0.5 * sufficiency + 0.5 * stability
    if mape is None:
        # No backtest possible (short series) -> haircut for uncertainty.
        return round(base * 0.7, 3)
    accuracy = max(0.0, 1.0 - min(mape, 1.0))
    return round(0.6 * base + 0.4 * accuracy, 3)


def forecast_demand(
    history: Iterable[Tuple[date, float]],
    horizon_days: int = 14,
    model_type: str = "random_forest",
    stockout_dates: Optional[set[date]] = None,
    holdout_days: int = DEFAULT_HOLDOUT_DAYS,
) -> ForecastResult:
    """
    Forecast daily demand for one (medication, location) series.

    Args:
        history: iterable of (consumption_date, quantity).
        horizon_days: how many days ahead to forecast.
        model_type: "random_forest" or "xgboost".
        stockout_dates: dates to exclude from training (schema:
            ``is_stockout_period``).
        holdout_days: tail length used for the backtest/MAPE.

    Returns:
        ForecastResult with p10/p50/p90 points and confidence scoring.
    """
    history = list(history)
    series = build_daily_series(history, stockout_dates)
    training_days = int(len(series))

    sufficiency = _data_sufficiency(training_days)
    stability = _series_stability(series)

    if training_days < MIN_TRAINING_DAYS:
        # Not enough history to train the tree model — fall back gracefully.
        points = _seasonal_naive(series, horizon_days)
        confidence = _confidence(sufficiency, stability, None)
        return ForecastResult(
            model_type="seasonal_naive",
            horizon_days=horizon_days,
            training_data_days=training_days,
            holdout_mape=None,
            data_sufficiency_score=sufficiency,
            series_stability_score=stability,
            confidence_score=confidence,
            points=points,
        )

    mape = _backtest_mape(model_type, series, holdout_days)

    X, y = make_supervised(series)
    model = QuantileForecaster(model_type=model_type).fit(X, y)
    points = _recursive_forecast(model, series, horizon_days)

    confidence = _confidence(sufficiency, stability, mape)
    return ForecastResult(
        model_type=model_type,
        horizon_days=horizon_days,
        training_data_days=training_days,
        holdout_mape=mape,
        data_sufficiency_score=sufficiency,
        series_stability_score=stability,
        confidence_score=confidence,
        points=points,
    )

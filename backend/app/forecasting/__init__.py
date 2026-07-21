"""
Demand forecasting module.

Turns a daily consumption series for one (medication, location) into a
multi-step p10/p50/p90 forecast using tree-ensemble quantile regression
(RandomForest by default, XGBoost optional), with confidence scoring that
mirrors the ``forecast_models`` schema.

Example:
    from app.forecasting import forecast_demand
    result = forecast_demand(history, horizon_days=14, model_type="xgboost")
    print(result.points[0].p50, result.confidence_score)
"""

from .models import MODEL_TYPES, QUANTILES, QuantileForecaster
from .service import (
    ForecastPoint,
    ForecastResult,
    forecast_demand,
)

__all__ = [
    "forecast_demand",
    "ForecastResult",
    "ForecastPoint",
    "QuantileForecaster",
    "MODEL_TYPES",
    "QUANTILES",
]

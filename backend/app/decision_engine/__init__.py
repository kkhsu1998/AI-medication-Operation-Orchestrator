"""
Decision Engine — the 19 required pure, deterministic decision functions.

Per steering constraints and ADR-001 (D7):
  - No LLM is ever used inside these functions.
  - All functions are pure: primitives/dataclasses in, primitives/dataclasses
    out. No network calls, no DB access, no hidden state.
  - Negative or otherwise invalid inputs raise a typed DecisionInputError
    rather than returning a wrong numeric value.

Functions 1-15 are the deterministic engine.
Functions 16-19 integrate the demand signal (DemandSignal / ForecastPoint)
produced by the forecasting module, but the arithmetic itself remains
deterministic Python — the ML layer only supplies input values.
"""

from .errors import DecisionInputError
from .functions import (
    # 1-15 deterministic engine
    available_quantity,
    average_daily_demand,
    days_of_supply,
    projected_stockout_date,
    safety_stock,
    excess_quantity,
    expiration_risk_quantity,
    transferable_quantity,
    supplier_arrival_date,
    transfer_arrival_date,
    source_location_safety_check,
    transfer_cost,
    procurement_cost,
    option_feasibility,
    recommendation_score,
    # 16-19 demand signal integration
    effective_daily_demand,
    forecast_horizon_stockout_scan,
    demand_adjusted_safety_stock,
    expiration_risk_adjusted_horizon,
)

__all__ = [
    "DecisionInputError",
    "available_quantity",
    "average_daily_demand",
    "days_of_supply",
    "projected_stockout_date",
    "safety_stock",
    "excess_quantity",
    "expiration_risk_quantity",
    "transferable_quantity",
    "supplier_arrival_date",
    "transfer_arrival_date",
    "source_location_safety_check",
    "transfer_cost",
    "procurement_cost",
    "option_feasibility",
    "recommendation_score",
    "effective_daily_demand",
    "forecast_horizon_stockout_scan",
    "demand_adjusted_safety_stock",
    "expiration_risk_adjusted_horizon",
]

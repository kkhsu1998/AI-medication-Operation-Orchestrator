"""
Configuration data models.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass(frozen=True)
class ConfigEntry:
    """
    A configuration entry in the operational_config table.

    Each entry is a key-value pair with metadata.
    Values are stored as JSONB and converted to their expected types
    (Decimal, int, bool, dict, etc.) at access time.
    """

    config_id: uuid.UUID
    key: str
    value: Any  # JSONB, converted to expected type on access
    description: Optional[str]
    updated_by: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# Standard Configuration Keys and Defaults
# ---------------------------------------------------------------------------
# These are the minimum keys required by the platform.
# Keys are organized by module.
# Values are provided as defaults if the database is empty.

STANDARD_CONFIG_KEYS = {
    # Decision Engine thresholds
    "safety_stock_multiplier": {"default": 1.5, "type": "float", "description": "Multiplier on lead-time demand for safety stock buffer"},
    "days_supply_minimum": {"default": 7, "type": "int", "description": "Minimum days of supply before low-stock alert"},
    "expiration_risk_horizon_days": {"default": 30, "type": "int", "description": "Horizon (days) for expiration-risk detection"},
    "lead_time_buffer_days": {"default": 2, "type": "int", "description": "Extra buffer days on top of supplier lead time"},
    "min_feasibility_score_threshold": {"default": 0.5, "type": "float", "description": "Minimum feasibility score (0-1) for an option to be viable"},

    # Scoring weights (JSON)
    "scoring_weight_availability": {"default": 0.40, "type": "float", "description": "Weight for availability in recommendation scoring"},
    "scoring_weight_lead_time": {"default": 0.25, "type": "float", "description": "Weight for lead time in recommendation scoring"},
    "scoring_weight_cost": {"default": 0.20, "type": "float", "description": "Weight for cost in recommendation scoring"},
    "scoring_weight_waste_reduction": {"default": 0.15, "type": "float", "description": "Weight for waste reduction in recommendation scoring"},

    # Task management
    "delivery_retry_limit": {"default": 3, "type": "int", "description": "Maximum retry attempts for a failed delivery task"},
    "avg_minutes_per_manual_step": {"default": 30, "type": "int", "description": "Average time (minutes) for a manual operational step"},

    # Forecasting module
    "forecast_min_confidence_threshold": {"default": 0.65, "type": "float", "description": "Minimum confidence (0-1) to use ML forecast; below = deterministic baseline"},
    "forecast_divergence_alert_threshold": {"default": 0.25, "type": "float", "description": "Alert if forecast diverges >threshold from baseline"},
    "forecast_staleness_limit_hours": {"default": 48, "type": "int", "description": "Cache staleness limit (hours); beyond = recompute"},
    "cold_start_multiplier": {"default": 1.2, "type": "float", "description": "Demand multiplier during cold-start (< 14 days history)"},
    "drift_retrain_threshold_mape": {"default": 0.25, "type": "float", "description": "Trigger retrain if holdout MAPE > threshold"},
}


def get_config_schema() -> dict:
    """Return the standard configuration schema (keys, types, defaults)."""
    return STANDARD_CONFIG_KEYS.copy()

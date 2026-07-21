"""Config key/value store for operational settings."""

from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Default operational configuration with human-readable metadata for the UI.
DEFAULTS: dict[str, dict] = {
    "safety_stock_multiplier": {"value": 1.5, "label": "Safety stock multiplier", "group": "Stock"},
    "days_of_supply_minimum": {"value": 7, "label": "Min days of supply", "group": "Stock"},
    "expiration_risk_horizon_days": {"value": 60, "label": "Expiry risk horizon (days)", "group": "Stock"},
    "lead_time_buffer_days": {"value": 3, "label": "Lead-time buffer (days)", "group": "Procurement"},
    "minimum_feasibility_score": {"value": 0.5, "label": "Min feasibility score", "group": "Scoring"},
    "scoring_weight_availability": {"value": 0.4, "label": "Weight: availability", "group": "Scoring"},
    "scoring_weight_lead_time": {"value": 0.2, "label": "Weight: lead time", "group": "Scoring"},
    "scoring_weight_cost": {"value": 0.2, "label": "Weight: cost", "group": "Scoring"},
    "scoring_weight_waste_reduction": {"value": 0.2, "label": "Weight: waste reduction", "group": "Scoring"},
}


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[float] = mapped_column(Float)

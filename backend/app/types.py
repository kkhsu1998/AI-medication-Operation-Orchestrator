"""
Shared domain types used across all modules.

This file defines the type contracts only — no application logic.
All modules import from here for cross-module type safety.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enum Types (mirrors PostgreSQL enums)
# ---------------------------------------------------------------------------

class DemandSignalSource(str, Enum):
    ML_FORECAST = "ml_forecast"
    DETERMINISTIC_BASELINE = "deterministic_baseline"


class OrchestratorState(str, Enum):
    DETECTED = "detected"
    AGENTS_CONSULTED = "agents_consulted"
    OPTIONS_RANKED = "options_ranked"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    TASK_CREATED = "task_created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class DeliveryTaskState(str, Enum):
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DetectionType(str, Enum):
    LOW_DAYS_OF_SUPPLY = "low_days_of_supply"
    PROJECTED_STOCKOUT = "projected_stockout"
    EXCESS_INVENTORY = "excess_inventory"
    EXPIRATION_RISK = "expiration_risk"
    SUPPLIER_SHORTAGE = "supplier_shortage"
    DELAYED_REPLENISHMENT = "delayed_replenishment"
    FAILED_DELIVERY = "failed_delivery"


class OptionType(str, Enum):
    INTERNAL_TRANSFER = "internal_transfer"
    PROCUREMENT = "procurement"
    ESCALATION = "escalation"


class ForecastModel(str, Enum):
    HOLT_WINTERS = "holt_winters"
    ARIMA = "arima"
    NPTS = "npts"
    LIGHTGBM = "lightgbm"


class EventType(str, Enum):
    STATE_TRANSITION = "state_transition"
    ALERT = "alert"
    ERROR = "error"
    LLM_VALIDATION_FAILURE = "llm_validation_failure"


# ---------------------------------------------------------------------------
# Value Objects / Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


@dataclass(frozen=True)
class ScoringWeights:
    """Configurable weights for recommendation scoring (must sum to 1.0)."""
    availability: Decimal      # default 0.40
    lead_time: Decimal         # default 0.25
    cost: Decimal              # default 0.20
    waste_reduction: Decimal   # default 0.15


@dataclass(frozen=True)
class ForecastPoint:
    """Single day forecast with prediction intervals."""
    forecast_date: date
    p10: Decimal
    p50: Decimal
    p90: Decimal


@dataclass(frozen=True)
class DemandSignal:
    """
    Return type of get_demand_signal().
    This is the ONLY export of the forecasting module consumed by detection.
    """
    effective_daily_demand: Decimal
    demand_signal_source: DemandSignalSource
    forecast_confidence: Optional[Decimal]  # None when source is deterministic_baseline
    forecast_id: Optional[uuid.UUID]        # None when source is deterministic_baseline
    fallback_reason: Optional[str]          # None when ML forecast is used successfully


@dataclass(frozen=True)
class DetectionEvent:
    detection_event_id: uuid.UUID
    detection_type: DetectionType
    medication_id: uuid.UUID
    location_id: uuid.UUID
    detected_at: datetime
    demand_signal_source: DemandSignalSource
    correlation_id: uuid.UUID
    details: dict


@dataclass(frozen=True)
class ScoringBreakdown:
    availability_score: Decimal
    lead_time_score: Decimal
    cost_score: Decimal
    waste_reduction_score: Decimal
    weighted_total: Decimal


@dataclass(frozen=True)
class RejectedOption:
    option_type: OptionType
    reason: str
    score: Optional[Decimal]
    feasibility_passed: bool


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: uuid.UUID
    workflow_id: uuid.UUID
    correlation_id: uuid.UUID
    version: int
    demand_signal_source: DemandSignalSource
    recommended_option: OptionType
    score: Decimal
    scoring_weights: ScoringWeights
    evidence: dict
    scoring_breakdown: ScoringBreakdown
    rejected_options: list[RejectedOption]
    feasibility_result: dict
    input_snapshot: dict
    created_at: datetime


@dataclass(frozen=True)
class Approval:
    approval_id: uuid.UUID
    recommendation_id: uuid.UUID
    correlation_id: uuid.UUID
    recommendation_version: int
    decision: ApprovalDecision
    approver: str
    reason: Optional[str]
    policy_version: str
    input_snapshot: dict
    decided_at: datetime


@dataclass(frozen=True)
class Task:
    task_id: uuid.UUID
    correlation_id: uuid.UUID
    recommendation_id: uuid.UUID
    recommendation_version: int
    task_type: OptionType
    current_state: DeliveryTaskState
    medication_id: uuid.UUID
    source_location_id: Optional[uuid.UUID]
    destination_location_id: uuid.UUID
    quantity: Decimal
    assigned_to: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


@dataclass(frozen=True)
class WorkflowContext:
    """Snapshot passed between orchestrator stages."""
    workflow_id: uuid.UUID
    correlation_id: uuid.UUID
    current_state: OrchestratorState
    medication_id: uuid.UUID
    location_id: uuid.UUID
    detection_type: DetectionType
    demand_signal_source: DemandSignalSource


@dataclass(frozen=True)
class InventoryPosition:
    medication_id: uuid.UUID
    location_id: uuid.UUID
    quantity_on_hand: Decimal
    lots: list[LotInfo]


@dataclass(frozen=True)
class LotInfo:
    lot_id: uuid.UUID
    lot_number: str
    quantity: Decimal
    expiration_date: date


@dataclass(frozen=True)
class SupplierInfo:
    supplier_id: uuid.UUID
    name: str
    lead_time_days: int
    unit_cost: Decimal
    is_preferred: bool
    has_active_shortage: bool


@dataclass(frozen=True)
class KpiSnapshot:
    kpi_name: str
    kpi_value: Decimal
    dimensions: dict
    snapshot_at: datetime

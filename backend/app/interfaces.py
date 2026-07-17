"""
Module interface contracts — typed function signatures only.

Each module exposes a minimal public interface consumed by other modules.
No implementation logic lives here. These protocols serve as the contract
between modules and are the basis for integration tests.

Modules:
  forecasting | detection | inventory | procurement | delivery |
  orchestration | recommendation | approval | task_management |
  audit | kpi | config | simulation
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Protocol

from .types import (
    Approval,
    ApprovalDecision,
    DateRange,
    DemandSignal,
    DemandSignalSource,
    DetectionEvent,
    DetectionType,
    DeliveryTaskState,
    ForecastPoint,
    InventoryPosition,
    KpiSnapshot,
    LotInfo,
    OptionType,
    OrchestratorState,
    Recommendation,
    RejectedOption,
    ScoringBreakdown,
    ScoringWeights,
    SupplierInfo,
    Task,
    WorkflowContext,
)


# ===========================================================================
# FORECASTING MODULE
# ===========================================================================

class ForecastingService(Protocol):
    """
    The forecasting module's public interface.
    get_demand_signal() is the ONLY export consumed by the detection module.
    """

    def get_demand_signal(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
        date_range: DateRange,
    ) -> DemandSignal:
        """
        Return the effective daily demand for a medication at a location
        over the specified date range.

        Behaviour:
        - If an ML forecast is available AND confidence >= threshold:
          returns p50 as effective_daily_demand, source = ml_forecast
        - Otherwise: returns rolling-average baseline,
          source = deterministic_baseline, with fallback_reason populated.

        Fallback rules (in priority order):
          1. confidence < threshold -> deterministic + fallback_reason
          2. Invalid forecast output -> deterministic + log + fallback_reason
          3. Stale cache (> 48h) -> deterministic + system alert + fallback_reason
          4. Cold start (< 14 days history) -> baseline * cold_start_multiplier
             + fallback_reason

        This function NEVER raises on forecast unavailability. It always
        returns a valid DemandSignal.
        """
        ...

    def get_forecast_points(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
        horizon_days: int,
    ) -> list[ForecastPoint]:
        """Return cached [p10, p50, p90] forecasts for the next N days."""
        ...

    def trigger_retrain(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> uuid.UUID:
        """Queue a retrain job. Returns the model training job ID."""
        ...


# ===========================================================================
# DETECTION MODULE
# ===========================================================================

class DetectionService(Protocol):
    """Scans inventory positions and raises detection events."""

    def run_detection_scan(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> list[DetectionEvent]:
        """
        Evaluate all detection rules for a medication+location pair.
        Returns zero or more detection events. Each event has a unique
        correlation_id that becomes the orchestrator workflow key.
        """
        ...

    def run_full_scan(self) -> list[DetectionEvent]:
        """Run detection across all active medication+location pairs."""
        ...


# ===========================================================================
# INVENTORY MODULE
# ===========================================================================

class InventoryService(Protocol):
    """Queries and manages inventory positions."""

    def get_position(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> InventoryPosition:
        """Return current on-hand quantity and lot details."""
        ...

    def get_transferable_quantity(
        self,
        medication_id: uuid.UUID,
        source_location_id: uuid.UUID,
        safety_stock: Decimal,
    ) -> Decimal:
        """Quantity available for transfer (on-hand minus safety stock)."""
        ...

    def get_lots_by_expiration(
        self,
        medication_id: uuid.UUID,
        location_id: uuid.UUID,
        before_date: date,
    ) -> list[LotInfo]:
        """Lots expiring before the given date, ordered soonest first."""
        ...


# ===========================================================================
# PROCUREMENT MODULE
# ===========================================================================

class ProcurementService(Protocol):
    """Queries supplier data and generates procurement options."""

    def get_suppliers(
        self,
        medication_id: uuid.UUID,
    ) -> list[SupplierInfo]:
        """All active suppliers for a medication, annotated with shortage status."""
        ...

    def estimate_arrival(
        self,
        supplier_id: uuid.UUID,
        order_date: date,
    ) -> date:
        """Projected arrival date = order_date + supplier lead_time_days."""
        ...

    def estimate_cost(
        self,
        supplier_id: uuid.UUID,
        medication_id: uuid.UUID,
        quantity: Decimal,
    ) -> Decimal:
        """Total procurement cost for the given quantity."""
        ...


# ===========================================================================
# DELIVERY MODULE
# ===========================================================================

class DeliveryService(Protocol):
    """Manages delivery/transfer task execution."""

    def estimate_transfer_arrival(
        self,
        source_location_id: uuid.UUID,
        destination_location_id: uuid.UUID,
    ) -> int:
        """Estimated transfer time in hours."""
        ...

    def estimate_transfer_cost(
        self,
        source_location_id: uuid.UUID,
        destination_location_id: uuid.UUID,
        quantity: Decimal,
    ) -> Decimal:
        """Estimated cost for an internal transfer."""
        ...

    def dispatch_task(
        self,
        task_id: uuid.UUID,
    ) -> DeliveryTaskState:
        """Submit task to delivery adapter. Returns new state."""
        ...


# ===========================================================================
# ORCHESTRATION MODULE
# ===========================================================================

class OrchestrationService(Protocol):
    """Orchestrator state machine — coordinates the workflow."""

    def start_workflow(
        self,
        event: DetectionEvent,
    ) -> WorkflowContext:
        """Create a new workflow from a detection event (state: detected)."""
        ...

    def transition(
        self,
        workflow_id: uuid.UUID,
        to_state: OrchestratorState,
        actor: str,
        metadata: Optional[dict] = None,
    ) -> WorkflowContext:
        """
        Persist a state transition (write-then-act).
        Raises InvalidTransitionError if the transition is not in the
        allowed transition table (ADR-002, 13 transitions).
        """
        ...

    def resume_incomplete_workflows(self) -> list[WorkflowContext]:
        """On worker startup: find and resume all non-terminal workflows."""
        ...


# ===========================================================================
# RECOMMENDATION MODULE
# ===========================================================================

class RecommendationService(Protocol):
    """Scores options and produces recommendations."""

    def evaluate_options(
        self,
        context: WorkflowContext,
        inventory_options: list[dict],
        procurement_options: list[dict],
    ) -> Recommendation:
        """
        Run option_feasibility gate, then score feasible options using
        weighted sum. Returns the top recommendation with evidence,
        rejected options, and scoring breakdown.

        Raises EscalationRequired if no option clears feasibility.
        """
        ...


# ===========================================================================
# APPROVAL MODULE
# ===========================================================================

class ApprovalService(Protocol):
    """Records human approval/rejection decisions."""

    def submit_decision(
        self,
        recommendation_id: uuid.UUID,
        decision: ApprovalDecision,
        approver: str,
        reason: Optional[str],
    ) -> Approval:
        """
        Record approval or rejection. Triggers orchestrator transition.
        Captures: approver, decision, timestamp UTC, reason,
        recommendation version, policy version, input snapshot.
        """
        ...

    def get_pending(self) -> list[Recommendation]:
        """All recommendations awaiting approval."""
        ...


# ===========================================================================
# TASK MANAGEMENT MODULE
# ===========================================================================

class TaskManagementService(Protocol):
    """Creates and tracks tasks (idempotent via correlation_id)."""

    def create_task(
        self,
        recommendation: Recommendation,
        approval: Approval,
    ) -> Task:
        """
        Create a task from an approved recommendation.
        Idempotency key: correlation_id = recommendation_id + version.
        If task already exists for this key, returns existing task.
        """
        ...

    def transition_task(
        self,
        task_id: uuid.UUID,
        to_state: DeliveryTaskState,
        actor: str,
        reason: Optional[str] = None,
    ) -> Task:
        """Persist a task state transition."""
        ...

    def get_active_tasks(self) -> list[Task]:
        """All tasks not in terminal state (completed/escalated)."""
        ...


# ===========================================================================
# AUDIT MODULE
# ===========================================================================

class AuditService(Protocol):
    """Immutable audit trail."""

    def log_event(
        self,
        correlation_id: Optional[uuid.UUID],
        event_type: str,
        actor: str,
        module: str,
        action: str,
        details: Optional[dict] = None,
        demand_signal_source: Optional[DemandSignalSource] = None,
    ) -> None:
        """Append an audit log entry. Never fails silently."""
        ...


# ===========================================================================
# KPI MODULE
# ===========================================================================

class KpiService(Protocol):
    """Records and retrieves KPI snapshots."""

    def record_snapshot(
        self,
        kpi_name: str,
        kpi_value: Decimal,
        dimensions: Optional[dict] = None,
    ) -> None:
        """Persist a KPI measurement."""
        ...

    def get_latest(
        self,
        kpi_name: str,
        dimensions: Optional[dict] = None,
    ) -> Optional[KpiSnapshot]:
        """Most recent snapshot for a KPI, optionally filtered."""
        ...

    def get_history(
        self,
        kpi_name: str,
        start: datetime,
        end: datetime,
        dimensions: Optional[dict] = None,
    ) -> list[KpiSnapshot]:
        """Historical KPI values over a time range."""
        ...


# ===========================================================================
# CONFIG MODULE
# ===========================================================================

class ConfigService(Protocol):
    """
    Sole read/write path for operational thresholds (FR-08).
    All config lives in PostgreSQL, never in env vars or code constants.
    """

    def get(self, key: str) -> object:
        """Get a config value by key. Raises KeyError if not found."""
        ...

    def get_decimal(self, key: str) -> Decimal:
        """Get a config value as Decimal."""
        ...

    def get_int(self, key: str) -> int:
        """Get a config value as int."""
        ...

    def get_scoring_weights(self) -> ScoringWeights:
        """Load current scoring weights from config table."""
        ...

    def set(self, key: str, value: object, updated_by: str = "system") -> None:
        """Upsert a config value."""
        ...


# ===========================================================================
# SIMULATION MODULE
# ===========================================================================

class SimulationService(Protocol):
    """Demo scenario runner and synthetic data management."""

    def run_scenario(self, scenario_number: int) -> dict:
        """Execute a demo scenario end-to-end. Returns execution summary."""
        ...

    def seed_synthetic_data(self, seed: int) -> None:
        """
        Generate synthetic data using the documented deterministic seed.
        5 locations, 10 medications, multiple lots, 90-day history.
        """
        ...

-- =============================================================================
-- Medication Operations Platform — PostgreSQL Schema
-- =============================================================================
-- Version: 1.0.0 (Step 3 — domain model, no application logic)
-- All operational thresholds live in the config table (FR-08).
-- All timestamps are stored as TIMESTAMPTZ (UTC).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Custom Enum Types
-- ---------------------------------------------------------------------------

CREATE TYPE demand_signal_source_t AS ENUM (
    'ml_forecast',
    'deterministic_baseline'
);

CREATE TYPE orchestrator_state_t AS ENUM (
    'detected',
    'agents_consulted',
    'options_ranked',
    'pending_approval',
    'approved',
    'task_created',
    'in_progress',
    'completed',
    'escalated'
);

CREATE TYPE delivery_task_state_t AS ENUM (
    'requested',
    'assigned',
    'accepted',
    'in_progress',
    'completed',
    'failed',
    'escalated'
);

CREATE TYPE approval_decision_t AS ENUM (
    'approved',
    'rejected'
);

CREATE TYPE event_type_t AS ENUM (
    'state_transition',
    'alert',
    'error',
    'llm_validation_failure'
);

CREATE TYPE detection_type_t AS ENUM (
    'low_days_of_supply',
    'projected_stockout',
    'excess_inventory',
    'expiration_risk',
    'supplier_shortage',
    'delayed_replenishment',
    'failed_delivery'
);

CREATE TYPE option_type_t AS ENUM (
    'internal_transfer',
    'procurement',
    'escalation'
);

CREATE TYPE forecast_model_t AS ENUM (
    'holt_winters',
    'arima',
    'npts',
    'lightgbm'
);

-- ---------------------------------------------------------------------------
-- Core Domain Tables
-- ---------------------------------------------------------------------------

CREATE TABLE locations (
    location_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,
    location_type       TEXT NOT NULL,  -- e.g. 'pharmacy', 'warehouse', 'ward'
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE medications (
    medication_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ndc                 TEXT NOT NULL UNIQUE,   -- National Drug Code
    name                TEXT NOT NULL,
    generic_name        TEXT,
    unit_of_measure     TEXT NOT NULL,          -- e.g. 'tablet', 'vial', 'mL'
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE inventory_lots (
    lot_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    lot_number          TEXT NOT NULL,
    quantity            NUMERIC(12, 2) NOT NULL CHECK (quantity >= 0),
    expiration_date     DATE NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (medication_id, location_id, lot_number)
);

CREATE INDEX idx_lots_medication_location ON inventory_lots (medication_id, location_id);
CREATE INDEX idx_lots_expiration ON inventory_lots (expiration_date);

-- Aggregated view helper: current on-hand per medication+location
CREATE TABLE inventory_levels (
    inventory_level_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    quantity_on_hand    NUMERIC(12, 2) NOT NULL CHECK (quantity_on_hand >= 0),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (medication_id, location_id)
);

-- ---------------------------------------------------------------------------
-- Demand / Consumption History (for deterministic baseline + ML training)
-- ---------------------------------------------------------------------------

CREATE TABLE consumption_history (
    consumption_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    consumption_date    DATE NOT NULL,
    quantity            NUMERIC(12, 2) NOT NULL CHECK (quantity >= 0),
    is_stockout_period  BOOLEAN NOT NULL DEFAULT FALSE, -- excluded from training
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (medication_id, location_id, consumption_date)
);

CREATE INDEX idx_consumption_med_loc_date
    ON consumption_history (medication_id, location_id, consumption_date DESC);

-- ---------------------------------------------------------------------------
-- Suppliers
-- ---------------------------------------------------------------------------

CREATE TABLE suppliers (
    supplier_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,
    lead_time_days      INTEGER NOT NULL CHECK (lead_time_days >= 0),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE supplier_medications (
    supplier_id         UUID NOT NULL REFERENCES suppliers(supplier_id),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    unit_cost           NUMERIC(10, 4) NOT NULL CHECK (unit_cost >= 0),
    is_preferred        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (supplier_id, medication_id)
);

CREATE TABLE supplier_shortage_events (
    shortage_event_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id         UUID NOT NULL REFERENCES suppliers(supplier_id),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    notice_text         TEXT,               -- raw supplier notice (may be LLM-summarized)
    summary             TEXT,               -- LLM-generated summary (untrusted, validated)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Forecasting Module
-- ---------------------------------------------------------------------------

CREATE TABLE forecast_models (
    model_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    model_type          forecast_model_t NOT NULL,
    model_artifact_path TEXT,              -- S3 key or local path
    holdout_mape        NUMERIC(6, 4),     -- e.g. 0.1523 = 15.23%
    data_sufficiency_score NUMERIC(4, 3),  -- 0.000 to 1.000
    series_stability_score NUMERIC(4, 3),  -- 0.000 to 1.000
    confidence_score    NUMERIC(4, 3),     -- composite, 0.000 to 1.000
    training_data_days  INTEGER NOT NULL,
    trained_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (medication_id, location_id, model_type, trained_at)
);

CREATE TABLE forecast_cache (
    forecast_cache_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES forecast_models(model_id),
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    forecast_date       DATE NOT NULL,
    p10                 NUMERIC(12, 2) NOT NULL,
    p50                 NUMERIC(12, 2) NOT NULL,
    p90                 NUMERIC(12, 2) NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (medication_id, location_id, forecast_date)
);

CREATE INDEX idx_forecast_cache_lookup
    ON forecast_cache (medication_id, location_id, forecast_date);

-- ---------------------------------------------------------------------------
-- Detection Events
-- ---------------------------------------------------------------------------

CREATE TABLE detection_events (
    detection_event_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detection_type      detection_type_t NOT NULL,
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    demand_signal_source demand_signal_source_t NOT NULL,
    details             JSONB NOT NULL DEFAULT '{}',  -- detection-specific payload
    correlation_id      UUID NOT NULL UNIQUE,          -- becomes the workflow key
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_detection_events_type ON detection_events (detection_type, detected_at DESC);

-- ---------------------------------------------------------------------------
-- Orchestrator State Machine
-- ---------------------------------------------------------------------------

CREATE TABLE orchestrator_workflows (
    workflow_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id      UUID NOT NULL UNIQUE REFERENCES detection_events(correlation_id),
    current_state       orchestrator_state_t NOT NULL DEFAULT 'detected',
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    location_id         UUID NOT NULL REFERENCES locations(location_id),
    detection_type      detection_type_t NOT NULL,
    demand_signal_source demand_signal_source_t NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflows_state ON orchestrator_workflows (current_state);
CREATE INDEX idx_workflows_correlation ON orchestrator_workflows (correlation_id);

CREATE TABLE orchestrator_state_log (
    log_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID NOT NULL REFERENCES orchestrator_workflows(workflow_id),
    correlation_id      UUID NOT NULL,
    from_state          orchestrator_state_t,
    to_state            orchestrator_state_t NOT NULL,
    actor               TEXT NOT NULL,         -- module/agent that triggered transition
    duration_ms         INTEGER,
    metadata            JSONB NOT NULL DEFAULT '{}',
    transitioned_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_state_log_workflow ON orchestrator_state_log (workflow_id, transitioned_at);

-- ---------------------------------------------------------------------------
-- Recommendations
-- ---------------------------------------------------------------------------

CREATE TABLE recommendations (
    recommendation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID NOT NULL REFERENCES orchestrator_workflows(workflow_id),
    correlation_id      UUID NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    demand_signal_source demand_signal_source_t NOT NULL,
    recommended_option  option_type_t NOT NULL,
    score               NUMERIC(6, 4) NOT NULL,
    scoring_weights     JSONB NOT NULL,        -- { availability, lead_time, cost, waste_reduction }
    evidence            JSONB NOT NULL,        -- supporting data snapshot
    scoring_breakdown   JSONB NOT NULL,        -- per-dimension scores
    rejected_options    JSONB NOT NULL DEFAULT '[]', -- [{ option, reason, score }]
    feasibility_result  JSONB NOT NULL,        -- option_feasibility gate output
    input_snapshot      JSONB NOT NULL,        -- frozen inputs at decision time
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (correlation_id, version)
);

CREATE INDEX idx_recommendations_workflow ON recommendations (workflow_id);

-- ---------------------------------------------------------------------------
-- Approvals (FR-05)
-- ---------------------------------------------------------------------------

CREATE TABLE approvals (
    approval_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL REFERENCES recommendations(recommendation_id),
    correlation_id      UUID NOT NULL,
    recommendation_version INTEGER NOT NULL,
    decision            approval_decision_t NOT NULL,
    approver            TEXT NOT NULL,          -- user identifier
    reason              TEXT,
    policy_version      TEXT NOT NULL,          -- version of approval policy in effect
    input_snapshot      JSONB NOT NULL,         -- frozen recommendation payload
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_approvals_recommendation ON approvals (recommendation_id);

-- ---------------------------------------------------------------------------
-- Tasks (FR-06)
-- ---------------------------------------------------------------------------

CREATE TABLE tasks (
    task_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id      UUID NOT NULL,
    recommendation_id   UUID NOT NULL REFERENCES recommendations(recommendation_id),
    recommendation_version INTEGER NOT NULL,
    task_type           option_type_t NOT NULL,
    current_state       delivery_task_state_t NOT NULL DEFAULT 'requested',
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    source_location_id  UUID REFERENCES locations(location_id),
    destination_location_id UUID NOT NULL REFERENCES locations(location_id),
    quantity            NUMERIC(12, 2) NOT NULL CHECK (quantity > 0),
    assigned_to         TEXT,
    description         TEXT,                  -- may be LLM-drafted
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    -- Idempotency: correlation_id = recommendation_id + version (FR-06)
    UNIQUE (correlation_id, recommendation_version)
);

CREATE INDEX idx_tasks_state ON tasks (current_state);
CREATE INDEX idx_tasks_correlation ON tasks (correlation_id);

CREATE TABLE task_state_log (
    log_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             UUID NOT NULL REFERENCES tasks(task_id),
    from_state          delivery_task_state_t,
    to_state            delivery_task_state_t NOT NULL,
    actor               TEXT NOT NULL,
    reason              TEXT,
    transitioned_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_state_log_task ON task_state_log (task_id, transitioned_at);

-- ---------------------------------------------------------------------------
-- Inventory Movements (only created on task completion)
-- ---------------------------------------------------------------------------

CREATE TABLE inventory_movements (
    movement_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             UUID NOT NULL REFERENCES tasks(task_id),
    correlation_id      UUID NOT NULL,
    medication_id       UUID NOT NULL REFERENCES medications(medication_id),
    from_location_id    UUID REFERENCES locations(location_id),
    to_location_id      UUID NOT NULL REFERENCES locations(location_id),
    quantity            NUMERIC(12, 2) NOT NULL,
    movement_type       TEXT NOT NULL,         -- 'transfer', 'receipt', 'adjustment'
    moved_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Idempotency: one movement per correlation_id
    UNIQUE (correlation_id, movement_type)
);

-- ---------------------------------------------------------------------------
-- Audit Trail
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    audit_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id      UUID,
    event_type          event_type_t NOT NULL,
    actor               TEXT NOT NULL,
    module              TEXT NOT NULL,
    action              TEXT NOT NULL,
    details             JSONB NOT NULL DEFAULT '{}',
    demand_signal_source demand_signal_source_t,
    timestamp_utc       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_correlation ON audit_log (correlation_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log (timestamp_utc DESC);

-- ---------------------------------------------------------------------------
-- KPIs (FR-07)
-- ---------------------------------------------------------------------------

CREATE TABLE kpi_snapshots (
    snapshot_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kpi_name            TEXT NOT NULL,
    kpi_value           NUMERIC(12, 4) NOT NULL,
    dimensions          JSONB NOT NULL DEFAULT '{}', -- { medication_id, location_id, period }
    snapshot_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kpi_snapshots_name ON kpi_snapshots (kpi_name, snapshot_at DESC);

-- ---------------------------------------------------------------------------
-- Configuration (FR-08 — all thresholds here, never in env vars or code)
-- ---------------------------------------------------------------------------

CREATE TABLE config (
    config_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key                 TEXT NOT NULL UNIQUE,
    value               JSONB NOT NULL,
    description         TEXT,
    updated_by          TEXT NOT NULL DEFAULT 'system',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed required config keys (values are set by the config module at init)
-- Examples of keys:
--   scoring_weight_availability, scoring_weight_lead_time,
--   scoring_weight_cost, scoring_weight_waste_reduction,
--   forecast_confidence_threshold, cold_start_multiplier,
--   cache_staleness_hours, minimum_feasibility_threshold,
--   safety_stock_days, low_dos_threshold_days

-- ---------------------------------------------------------------------------
-- Demo Scenarios (metadata for scenario runner)
-- ---------------------------------------------------------------------------

CREATE TABLE demo_scenarios (
    scenario_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_number     INTEGER NOT NULL UNIQUE CHECK (scenario_number BETWEEN 1 AND 7),
    name                TEXT NOT NULL,
    description         TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at         TIMESTAMPTZ,
    last_run_status     TEXT,  -- 'passed', 'failed', 'running'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- End of Schema
-- ---------------------------------------------------------------------------

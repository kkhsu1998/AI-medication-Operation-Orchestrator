# ADR-001: Initial Architecture for the Medication Operations Platform

- Status: Accepted
- Date: 2026-07-17
- Scope: v1 local prototype (Docker Compose). EKS deployment (Step 13)
  inherits these decisions unless explicitly superseded by a later ADR.

## Context

The platform detects medication supply problems, ranks operational
responses across Inventory/Procurement/Delivery, requires human
approval before any task executes, and must remain fully functional
if the ML forecasting layer is degraded or unavailable. This is a
prototype, not a production medical device or an autonomous purchasing
system (see steering constraints).

This ADR fixes the foundational technical decisions needed before any
application code is written, per the implementation order in the
design doc (Step 2 must complete before Step 3).

## Decisions

### D1. Language and backend framework: Python + FastAPI

Rationale: the decision engine (19 functions), forecasting module
(Holt-Winters / ARIMA / NPTS / LightGBM), and synthetic data simulator
all live naturally in Python's data/ML ecosystem (statsmodels,
lightgbm, numpy/pandas). Using one language for API, worker, decision
engine, and forecasting avoids a cross-language boundary around
numeric logic that must be unit-testable and never delegated to an
LLM. FastAPI gives typed request/response models (Pydantic) which map
directly onto the recommendation payload contract (evidence, rejected
options, scoring breakdown, demand_signal_source).

Alternatives considered: Node/TypeScript backend (rejected — weaker
ecosystem for ARIMA/Holt-Winters/LightGBM; would force a language
split between API and forecasting service, adding an unjustified
network boundary).

### D2. Module boundary: single backend application, logical modules only

Per the design doc, detection / inventory / procurement / delivery /
orchestration / recommendation / approval / task-management / audit /
simulation / kpi / config / forecasting are Python packages
(`backend/app/<module>`) inside one FastAPI application and one
worker process — not separate containers or microservices in v1.
This avoids premature distributed-systems complexity (network
failure handling, distributed tracing across services) for a
prototype whose complexity budget should go to the decision logic and
the approval/state-machine correctness instead.

### D3. Asynchronous workflow worker, no message queue in v1

The Orchestrator state machine (`detected -> ... -> completed |
escalated`) is persisted to PostgreSQL before every transition
(FR-03, restartable at any state). The worker polls/consumes
PostgreSQL-backed work items (outbox-style: a `workflow_events` /
`orchestrator_state` table drives the next step) rather than a
dedicated broker (e.g., RabbitMQ, SQS, Kafka).

Justification for omitting a message queue: the required durability
and restart guarantee ("resume from last persisted state, no
re-execution") is satisfied by transactional writes to Postgres plus
`correlation_id` idempotency keys. Demo scenario volume is small
(single-digit concurrent workflows), so a broker would add
operational surface area (extra container, extra failure mode) without
solving a problem Postgres doesn't already solve at this scale. If
throughput or fan-out requirements grow post-prototype, a queue can be
introduced as a superseding ADR — the outbox table is designed so a
queue could later consume from it without changing the state machine
contract.

### D4. Containers (v1, Docker Compose)

1. `frontend` — web UI (5 screens incl. Demand Forecast Dashboard)
2. `backend` — FastAPI application (REST API, decision engine,
   recommendation engine, approval endpoints)
3. `worker` — asynchronous workflow worker (orchestrator state machine,
   forecasting training/cache jobs in local mode)
4. `postgres` — primary store + configuration store (single instance,
   single database, schema-separated by module where useful)
5. `supplier-adapter` — simulated supplier adapter (HTTP stub)
6. `delivery-adapter` — simulated delivery/AMR adapter (HTTP stub)

This matches the design doc's container list exactly; no message
queue container is added (see D3).

### D5. State machine and idempotency persistence

- Orchestrator state is written to PostgreSQL synchronously before
  every transition (write-then-act, not act-then-write), so a crash
  between transitions never leaves an ambiguous state.
- Recovery key: `correlation_id`.
- Idempotency key for task creation: `correlation_id = recommendation_id
  + version`, enforced via a unique constraint in the tasks table
  (database-level guarantee, not just application-level checking).
- Failed delivery tasks transition to `failed -> escalated` without
  emitting new inventory movement events; movement events are only
  ever created on `completed`, and are themselves keyed by
  `correlation_id` to make replays safe.

### D6. Forecasting module isolation

`get_demand_signal(medication_id, location_id, date_range)` is the
only export of the forecasting module consumed by detection, per the
design doc. Internally, model selection (Holt-Winters -> ARIMA ->
NPTS -> LightGBM promotion at >=180 days) and the 4 fallback rules are
implementation details behind this interface. This lets Step 7
(forecasting) and Step 8 (integration) be developed and validated
independently, and lets the fallback-to-deterministic-baseline path
(steering constraint: "must remain fully functional when the ML
pipeline is unavailable") be tested in isolation before Detection
depends on it (Scenarios 6/7 gate, Step 8).

### D7. Decision engine isolation from LLM and from forecasting

The 19 decision functions (available_quantity ... 
expiration_risk_adjusted_horizon) are pure, deterministic Python
functions with no LLM calls and no direct network/DB calls where
avoidable — they take primitives/dataclasses in, return
primitives/dataclasses out. This is what makes "unit tests for all 19
functions (happy path, boundary, edge case, negative input)" tractable
and enforces the steering constraint that LLMs never compute
quantities, dates, costs, or scores. `effective_daily_demand` is the
one function that reads `get_demand_signal()`'s output, but the
arithmetic itself remains deterministic Python — the ML layer only
supplies an input value, never performs the calculation.

### D8. Configuration storage

All operational thresholds (feasibility gate, scoring weights,
forecast confidence threshold, cold-start multiplier, cache staleness
window, etc.) live in a PostgreSQL configuration table (FR-08). No
thresholds in environment variables or code constants. The config
module (`backend/app/config`) is the sole read/write path; other
modules must not read these values directly from the DB.

### D9. EKS decisions (deferred activation, decided now to avoid rework)

Per design doc, these apply starting Step 13, not before:
- EKS Pod Identity, not IRSA, for pod-to-AWS-service auth. Rationale:
  Pod Identity has a simpler trust model (no OIDC provider / IAM role
  trust policy per namespace-serviceaccount to hand-manage) and is the
  currently recommended AWS approach for new EKS workloads; IRSA is
  kept only as a fallback note in case the target EKS version does not
  support Pod Identity.
- Secrets: AWS Secrets Manager, no plaintext secrets in manifests
  (local Compose uses a `.env` file, gitignored, with example-only
  placeholder values committed as `.env.example`).
- Observability: CloudWatch Container Insights or OTel Collector,
  fed by the same structured JSON stdout logs used locally — no
  separate logging code path for EKS vs. Compose.
- Model artifacts: S3, least-privilege IAM, no SageMaker endpoints in
  the prototype (training/inference run in the worker container).
- Retraining: Kubernetes CronJobs (weekly full retrain Sun 02:00 UTC,
  daily incremental) — these are schedule wrappers around the same
  training pipeline code used locally, not new logic.

These are recorded now so the local architecture doesn't paint us into
a corner (e.g., structured logging to stdout from day one, config in
Postgres not env vars, S3-shaped model registry metadata even if the
prototype just uses a local/mounted path initially).

## Consequences

- Single-language stack simplifies tooling (one test runner, one
  dependency file, one lint config) at the cost of using Python for
  the frontend-adjacent glue too (mitigated: frontend is a separate
  container/stack, likely a small React/Vite app calling the FastAPI
  backend — final frontend framework choice deferred to Step 10 and
  will get its own short ADR note if non-trivial).
- No message broker means the worker's polling loop and Postgres
  contention under load are the main scaling risk; acceptable for a
  demo with 7 fixed scenarios, called out explicitly as a future
  revisit trigger.
- Deferring EKS specifics to Step 13 while deciding Pod Identity vs.
  IRSA now avoids re-architecting IAM auth after the prototype is
  built, at the cost of carrying an unused decision for several steps.

## Open Questions (to revisit before Step 10 / Step 13)

- Exact frontend framework/build tool (React+Vite assumed, not yet
  committed).
- Whether `workflow_events` outbox table needs partitioning/pruning
  strategy for the demo's data volume (likely no, but flag before
  Step 9).

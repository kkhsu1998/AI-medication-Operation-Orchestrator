# AI-Driven Medication Operations and Task Management Platform

Prototype system for detecting medication shortages, excess inventory,
expiration risk, supplier shortages, and replenishment delays; ranking
operational responses; and requiring human approval before any task
executes.

This is a prototype. It is not a production medical device and not an
autonomous purchasing system.

See `.kiro/specs/medication-platform/requirements.md` and
`.kiro/specs/medication-platform/design.md` for the full specification,
and `.kiro/steering/medication-platform.md` for non-negotiable
constraints. See `docs/adr/` for architecture decisions.

## Status

Repository scaffold only. No application code has been written yet.
Following the implementation order defined in the design doc
(Step 1: repository setup — in progress; Step 2: ADR — in progress).

## Layout

- `backend/app/` — logical modules (detection, inventory, procurement,
  delivery, orchestration, recommendation, approval, task_management,
  audit, simulation, kpi, config, forecasting) run inside a single
  backend application / worker process, per the design doc's module
  boundary rule (no per-agent containers in v1).
- `worker/` — asynchronous workflow worker entrypoint.
- `frontend/` — web frontend.
- `simulators/` — simulated supplier and delivery/AMR adapters.
- `data/synthetic/` — synthetic data generation (deterministic seed).
- `k8s/` — EKS manifests (not to be created until Step 13, after the
  Docker Compose demo passes all 7 scenarios).
- `docs/adr/` — Architecture Decision Records.

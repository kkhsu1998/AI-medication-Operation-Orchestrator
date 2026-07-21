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

Prototype in progress. Implemented so far: decision engine (19 functions),
config cache, scenario runner, demand forecasting (RandomForest / XGBoost),
and a React + Vite frontend (Stock + Forecast + Orchestrator screens).

## Running

Backend (tests):

    cd backend
    pip install -e '.[dev]'
    pytest

Frontend (dev server on http://localhost:5173, proxies /api → backend:8000):

    cd frontend
    npm install
    npm run dev        # or: npm start

## Forecasting

`app.forecasting.forecast_demand(history, horizon_days=14, model_type="random_forest")`
turns a daily consumption series for one (medication, location) into a
multi-step p10/p50/p90 forecast using tree-ensemble quantile regression
(`random_forest` or `xgboost`), with confidence scoring (holdout MAPE, data
sufficiency, series stability). Short series fall back to a seasonal-naive
baseline. See `backend/tests/test_forecasting.py`.

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

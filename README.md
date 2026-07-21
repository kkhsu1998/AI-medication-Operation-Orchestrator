# AI-Driven Medication Operations and Task Management Platform

Prototype system for detecting medication shortages, excess inventory,
expiration risk, supplier shortages, and replenishment delays; ranking
operational responses (transfer preferred over procurement); and requiring
human approval before any task executes.

This is a prototype. It is not a production medical device and not an
autonomous purchasing system. All data is synthetic; no PHI.

## What's here

- **Stock** — Excel-like inventory worksheet (paginated at 100K rows,
  import/export .xlsx, paste from Excel, per-row saves to SQL, right-click
  per-drug summaries). Stored relationally; an HL7 FHIR `InventoryItem`
  Bundle view is generated on demand (`/api/v1/fhir/InventoryItem`).
- **Forecast** — daily demand (2 years of history) with a configurable
  feature grid: columns are the features; click a header to set a
  categorical encoder (one-hot/ordinal), a lag range (N-1…N-n), a calendar
  kind, or a derived formula column. Predict trains XGBoost / Random Forest
  (with normalization) and draws history (white) + forecast (red).
- **Orchestrator** — detected issues (stockout / shortage / expiring /
  overstock) with ranked transfer-vs-procurement options and one-click
  human approve/reject → task + audit.
- **Dashboard** — live KPIs from inventory + consumption (SQL-side, fast).
- **Audit** — every consequential action with a YYYYMMDDHHMMSS change-point
  stamp (who, when, what, why).
- **Settings** — operational thresholds and scoring weights (persisted,
  audited, drive detection).
- **MCP server** (`backend/mcp_server.py`, registered in `.mcp.json`) —
  lets an agent drive the system: `query`, `store_stock`, `forecast`,
  `cash_out`. Every mutating action records a change point.

## Running

Backend (auto-creates tables and seeds 100K inventory + 100K consumption
rows when empty; SQLite by default, set `DATABASE_URL` for Postgres):

    cd backend
    pip install -e '.[dev]'
    uvicorn app.main:app --reload      # http://localhost:8000 (docs at /docs)
    pytest                             # test suite

Frontend (npm workspaces — run from the repo root):

    npm install
    npm run dev                        # http://localhost:5173, proxies /api → :8000

Docker (full stack: Postgres + backend + frontend + Adminer):

    docker compose up --build          # frontend :3000, API :8000, Adminer :8080

Seed sizes are env-tunable: `MEDOPS_AUTOSEED`, `MEDOPS_SEED_INVENTORY`,
`MEDOPS_SEED_CONSUMPTION`. Regenerate manually with
`python data/synthetic/generate_hl7_inventory.py [N]` and
`python data/synthetic/generate_consumption.py [N]`.

## Layout

- `backend/app/` — FastAPI app: `stock/` (relational inventory + FHIR view),
  `consumption/` (daily series), `forecasting/` (univariate + multivariate
  feature-lattice models), `orchestration/`, `audit/`, `settings/`,
  `dashboard/`, `analytics.py`, `seed.py`, `db.py`, `main.py`.
- `backend/mcp_server.py` — MCP tools over the REST API.
- `frontend/` — React + TypeScript + Vite (screens, Excel-like DataGrid,
  API clients, module-level cache).
- `data/synthetic/` — deterministic synthetic data generators.
- `docs/adr/` — architecture decision records; `docs/schema.sql` — the
  fuller target schema.

See `docs/adr/` for architecture decisions.

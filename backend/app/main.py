"""
FastAPI application entrypoint.

Run locally (SQLite, zero-config):
    cd backend && uvicorn app.main:app --reload

Point DATABASE_URL at Postgres to use that instead. The frontend dev server
proxies /api and /health here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.audit.routes import router as audit_router
from app.dashboard.routes import router as dashboard_router
from app.db import init_db
from app.forecasting.routes import router as forecast_router
from app.orchestration.routes import router as orchestrator_router
from app.settings.routes import router as settings_router
from app.stock.routes import router as stock_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables if missing
    from app.db import SessionLocal
    from app.seed import seed_if_empty
    from app.settings.routes import ensure_defaults

    with SessionLocal() as session:
        ensure_defaults(session)  # seed default settings
        seed_if_empty(session)  # seed synthetic inventory + consumption when empty
    yield


app = FastAPI(title="MedOps API", version="0.1.0", lifespan=lifespan)

# Allow the Vite dev server to call directly (the proxy also covers this).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock_router)
app.include_router(forecast_router)
app.include_router(dashboard_router)
app.include_router(orchestrator_router)
app.include_router(audit_router)
app.include_router(settings_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

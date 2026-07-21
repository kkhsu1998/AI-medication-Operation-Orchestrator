"""
MedOps Orchestrator MCP server.

Exposes the platform as MCP tools so an agent/LLM can drive it over a simple
command interface: query the system, store inventory, forecast demand, or cash
out (approve/execute) a recommendation.

Every mutating action creates a timestamped CHANGE POINT (YYYYMMDDHHMMSS) in the
history — a real, auditable step that updates the SQL database and is visible on
the Stock / Forecast / Audit pages.

Run (stdio transport):
    python backend/mcp_server.py
Requires the MedOps API running (uvicorn app.main:app); override its URL with
the MEDOPS_API env var.
"""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("MEDOPS_API", "http://localhost:8000")
mcp = FastMCP("medops-orchestrator")
_client = httpx.Client(base_url=BASE, timeout=30.0)


def _change_point(action: str, target: str, detail: str) -> str:
    """Record a timestamped change point in the shared history (SQL)."""
    r = _client.post("/api/v1/changepoints", json={"action": action, "source": "mcp", "target": target, "detail": detail})
    r.raise_for_status()
    return r.json().get("change_id", "")


@mcp.tool()
def query(resource: str, drug: str = "") -> dict:
    """
    Query the MedOps system (read-only).

    resource: one of "dashboard", "issues", "stock_summary", "forecast_overview",
    "audit", "changepoints". For "stock_summary", pass `drug` to get one drug's
    per-location breakdown.
    """
    routes = {
        "dashboard": "/api/v1/dashboard",
        "issues": "/api/v1/orchestrator/issues",
        "forecast_overview": "/api/v1/forecast/overview",
        "audit": "/api/v1/audit?limit=20",
        "changepoints": "/api/v1/changepoints",
        "stock_summary": f"/api/v1/stock/summary{('?drug=' + drug) if drug else ''}",
    }
    if resource not in routes:
        return {"error": f"unknown resource {resource!r}", "valid": list(routes)}
    return _client.get(routes[resource]).json()


@mcp.tool()
def store_stock(
    drug: str, location: str, on_hand: float, unit: str = "", expiry_date: str = "",
    avg_daily_use: float = 0, supplier: str = "", last_delivery: str = "",
) -> dict:
    """
    Store (add) an inventory row. Mutates SQL and records a timestamped change
    point. Returns the stored row (with its id) and the change_id.
    """
    row = _client.post("/api/v1/stock", json={
        "drug": drug, "location": location, "on_hand": on_hand, "unit": unit,
        "expiry_date": expiry_date, "avg_daily_use": avg_daily_use,
        "supplier": supplier, "last_delivery": last_delivery,
    }).json()
    change_id = _change_point("mcp.store_stock", f"{drug} @ {location}", f"on_hand={on_hand}")
    return {"stored": row, "change_id": change_id}


@mcp.tool()
def forecast(drug: str, steps: int = 14, model: str = "xgboost", lags: int | None = None) -> dict:
    """
    Forecast a drug's daily demand: fetches its history and runs the chosen model
    ("xgboost", "random_forest", "arima", "moving_average"). Records a change
    point. Returns the predictions and change_id.
    """
    hist = _client.get("/api/v1/forecast/item", params={"drug": drug})
    if hist.status_code != 200:
        return {"error": f"no history for {drug!r}"}
    series = hist.json()["values"]
    pred = _client.post("/api/v1/forecast/predict", json={
        "series": series, "steps": steps, "model": model, "lags": lags,
    }).json()
    change_id = _change_point("mcp.forecast", drug, f"{model} {steps}d lags={lags}")
    return {"drug": drug, "model": model, "steps": steps, "predictions": pred.get("predictions"), "change_id": change_id}


@mcp.tool()
def cash_out(drug: str, location: str, option_type: str = "transfer", reason: str = "", approver_role: str = "Agent") -> dict:
    """
    Cash out (approve/execute) an orchestrator recommendation for a drug at a
    location — creates a task. option_type is "transfer" or "procurement".
    Mutates SQL and records a timestamped change point. Returns the task result.
    """
    result = _client.post("/api/v1/orchestrator/decision", json={
        "issue_id": f"{drug}::{location}", "drug": drug, "location": location,
        "option_type": option_type, "decision": "approved", "reason": reason, "approver_role": approver_role,
    }).json()
    change_id = _change_point("mcp.cash_out", f"{drug} @ {location}", f"{option_type} approved by {approver_role}")
    return {"result": result, "change_id": change_id}


if __name__ == "__main__":
    mcp.run()

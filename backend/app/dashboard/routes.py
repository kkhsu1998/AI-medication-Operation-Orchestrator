"""Dashboard API — operational KPIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import dashboard_kpis
from app.db import get_session
from app.settings.models import Setting

router = APIRouter(tags=["dashboard"])


@router.get("/api/v1/dashboard")
def dashboard(session: Session = Depends(get_session)) -> dict:
    min_days = session.get(Setting, "days_of_supply_minimum")
    return dashboard_kpis(session, min_days=min_days.value if min_days else 7.0)

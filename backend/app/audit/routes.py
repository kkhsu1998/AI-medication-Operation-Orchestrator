"""Audit trail + change-point API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.audit.service import record
from app.db import get_session

router = APIRouter(tags=["audit"])


def _serialize(a: AuditLog) -> dict:
    return {
        "id": a.id,
        "change_id": a.change_id,
        "ts": a.ts.isoformat(),
        "actor": a.actor,
        "action": a.action,
        "entity": a.entity,
        "detail": a.detail,
    }


@router.get("/api/v1/audit")
def list_audit(limit: int = Query(100, le=500), offset: int = 0, session: Session = Depends(get_session)) -> dict:
    total = session.scalar(select(func.count()).select_from(AuditLog)) or 0
    stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit).offset(offset)
    return {"total": total, "items": [_serialize(a) for a in session.scalars(stmt)]}


class ChangePointIn(BaseModel):
    action: str
    source: str = "mcp"
    target: str = ""
    detail: str = ""


@router.post("/api/v1/changepoints")
def create_change_point(body: ChangePointIn, session: Session = Depends(get_session)) -> dict:
    """Record a change point (a timestamped history step). Returns its change_id."""
    entry = record(session, action=body.action, entity=body.target, detail=body.detail, actor=body.source)
    return _serialize(entry)


@router.get("/api/v1/changepoints")
def list_change_points(limit: int = Query(50, le=200), session: Session = Depends(get_session)) -> dict:
    """Recent change points (newest first) — used by the pages to mark real changes."""
    stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
    return {"items": [_serialize(a) for a in session.scalars(stmt)]}

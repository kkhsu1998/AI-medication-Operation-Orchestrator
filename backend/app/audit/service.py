"""Helper to record audit entries / change points from anywhere in the app."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.audit.models import AuditLog


def new_change_id() -> str:
    """Compact change-point stamp: YYYYMMDDHHMMSS (local time)."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def record(session: Session, action: str, entity: str = "", detail: str = "", actor: str = "system") -> AuditLog:
    """Append an audit entry (a change point) and return it."""
    entry = AuditLog(change_id=new_change_id(), action=action, entity=entity, detail=detail, actor=actor)
    session.add(entry)
    session.commit()
    return entry

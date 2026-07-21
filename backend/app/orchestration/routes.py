"""
Orchestrator API — detect operational issues and record human approvals.

Mirrors the operating flow: detect (shortage / stockout / expiry / overstock),
rank options (transfer preferred over procurement), require a human approve /
reject decision, and log every decision to the audit trail.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics import issue_counts, top_issues
from app.audit.service import record
from app.db import get_session
from app.settings.models import Setting

router = APIRouter(tags=["orchestrator"])


@router.get("/api/v1/orchestrator/issues")
def issues(session: Session = Depends(get_session)) -> dict:
    setting = session.get(Setting, "days_of_supply_minimum")
    min_days = setting.value if setting else 7.0
    total = sum(issue_counts(session, min_days).values())
    return {"total": total, "items": top_issues(session, min_days, limit=100)}


class Decision(BaseModel):
    issue_id: str
    drug: str = ""
    location: str = ""
    option_type: str = ""  # transfer | procurement
    decision: str  # approved | rejected
    reason: str = ""
    approver_role: str = "Manager"


@router.post("/api/v1/orchestrator/decision")
def decide(body: Decision, session: Session = Depends(get_session)) -> dict:
    action = "orchestrator.approve" if body.decision == "approved" else "orchestrator.reject"
    detail = f"{body.option_type or 'n/a'} for {body.drug} @ {body.location}"
    if body.reason:
        detail += f" — {body.reason}"
    record(session, action, entity=body.issue_id, detail=detail, actor=body.approver_role)

    task_id = None
    if body.decision == "approved":
        task_id = str(uuid.uuid4())
        record(session, "task.create", entity=task_id, detail=f"{body.option_type} task: {detail}", actor="system")

    return {"status": body.decision, "task_id": task_id, "issue_id": body.issue_id}

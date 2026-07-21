"""Settings API — read + update operational configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.db import get_session
from app.settings.models import DEFAULTS, Setting


def ensure_defaults(session: Session) -> None:
    existing = {s.key for s in session.scalars(select(Setting))}
    added = False
    for key, meta in DEFAULTS.items():
        if key not in existing:
            session.add(Setting(key=key, value=float(meta["value"])))
            added = True
    if added:
        session.commit()


router = APIRouter(tags=["settings"])


class SettingsPatch(BaseModel):
    values: dict[str, float] = {}


@router.get("/api/v1/settings")
def get_settings(session: Session = Depends(get_session)) -> dict:
    ensure_defaults(session)
    current = {s.key: s.value for s in session.scalars(select(Setting))}
    items = [
        {
            "key": key,
            "value": current.get(key, meta["value"]),
            "label": meta["label"],
            "group": meta["group"],
        }
        for key, meta in DEFAULTS.items()
    ]
    return {"items": items}


@router.patch("/api/v1/settings")
def patch_settings(body: SettingsPatch, session: Session = Depends(get_session)) -> dict:
    ensure_defaults(session)
    changed = []
    for key, value in body.values.items():
        if key not in DEFAULTS:
            continue
        setting = session.get(Setting, key)
        if setting is None:
            setting = Setting(key=key, value=float(value))
            session.add(setting)
        else:
            setting.value = float(value)
        changed.append(f"{key}={value}")
    session.commit()
    if changed:
        record(session, "settings.update", "settings", ", ".join(changed))
    return get_settings(session)

"""
Shared analytics over the inventory (relational) + consumption data.

All heavy figures are computed in SQL so the Dashboard and Orchestrator stay
sub-second at 100K+ inventory rows. Issue detection returns only the worst
top-N candidates (never a full 100K Python scan).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.consumption.models import Consumption
from app.stock.models import StockItem

EXPIRY_HORIZON_DAYS = 60
OVERSTOCK_DAYS = 120

# Reusable SQL expression for days-of-supply.
def _dos_expr():
    return StockItem.on_hand / func.nullif(StockItem.avg_daily_use, 0)


def _kind_filters(min_days: float):
    today = date.today()
    horizon = today + timedelta(days=EXPIRY_HORIZON_DAYS)
    dos = _dos_expr()
    return {
        "stockout": StockItem.on_hand <= 0,
        "shortage": and_(StockItem.avg_daily_use > 0, StockItem.on_hand > 0, dos < min_days),
        # No lower bound: stock that is ALREADY past its expiry date still holds
        # units and must be flagged, not fall through as healthy.
        "expiration_risk": and_(StockItem.on_hand > 0, StockItem.expiry_date.isnot(None),
                                StockItem.expiry_date <= horizon),
        "overstock": and_(StockItem.avg_daily_use > 0, dos > OVERSTOCK_DAYS),
    }


def issue_counts(session: Session, min_days: float) -> dict[str, int]:
    filters = _kind_filters(min_days)
    cols = [func.sum(case((f, 1), else_=0)).label(k) for k, f in filters.items()]
    row = session.execute(select(*cols)).one()
    return {k: int(v or 0) for k, v in zip(filters.keys(), row)}


def _describe(item: StockItem, kind: str, min_days: float) -> str:
    use = item.avg_daily_use or 0
    dos = (item.on_hand / use) if use > 0 else None
    if kind == "stockout":
        return "On hand is zero"
    if kind == "shortage":
        return f"~{dos:.1f} days of supply (min {min_days:.0f})"
    if kind == "expiration_risk":
        days = (item.expiry_date - date.today()).days if item.expiry_date else 0
        return f"Expired {-days} days ago" if days < 0 else f"Expires in {days} days"
    return f"~{dos:.0f} days of supply (overstocked)"


def _options(session: Session, item: StockItem, min_days: float) -> list[dict]:
    options: list[dict] = []
    dos = _dos_expr()
    surplus = session.scalars(
        select(StockItem)
        .where(and_(StockItem.drug == item.drug, StockItem.location != item.location,
                    StockItem.avg_daily_use > 0, dos > min_days * 3))
        .order_by(dos.desc()).limit(1)
    ).first()
    if surplus is not None:
        s_dos = surplus.on_hand / surplus.avg_daily_use if surplus.avg_daily_use else 0
        options.append({"type": "transfer", "label": f"Transfer from {surplus.location}", "feasible": True,
                        "detail": f"{surplus.location} has ~{s_dos:.0f} days of supply", "score": 0.9})
    options.append({"type": "procurement", "label": f"Procure from {item.supplier or 'supplier'}", "feasible": True,
                    "detail": "Reorder from supplier", "score": 0.6})
    return options


SEVERITY = {"stockout": 4, "shortage": 3, "expiration_risk": 2, "overstock": 1}


def top_issues(session: Session, min_days: float, limit: int = 100, with_options: bool = True) -> list[dict]:
    filters = _kind_filters(min_days)
    dos = _dos_expr()
    order = {
        "stockout": StockItem.position,
        "shortage": dos.asc(),
        "expiration_risk": StockItem.expiry_date.asc(),
        "overstock": dos.desc(),
    }
    issues: list[dict] = []
    for kind in ("stockout", "shortage", "expiration_risk", "overstock"):
        if len(issues) >= limit:
            break
        remaining = limit - len(issues)
        for item in session.scalars(select(StockItem).where(filters[kind]).order_by(order[kind]).limit(remaining)):
            d = item.avg_daily_use and item.on_hand / item.avg_daily_use
            issues.append({
                "id": f"{item.drug}::{item.location}",
                "kind": kind,
                "severity": SEVERITY[kind],
                "drug": item.drug,
                "location": item.location,
                "on_hand": item.on_hand,
                "days_of_supply": round(d, 1) if d else None,
                "detail": _describe(item, kind, min_days),
                "options": _options(session, item, min_days) if with_options and kind in ("stockout", "shortage") else [],
            })
    return issues


def dashboard_kpis(session: Session, min_days: float = 7.0) -> dict:
    counts = issue_counts(session, min_days)
    total_units = session.scalar(select(func.sum(StockItem.on_hand))) or 0
    meds = session.scalar(select(func.count(func.distinct(StockItem.drug)))) or 0
    locations = session.scalar(select(func.count(func.distinct(StockItem.location)))) or 0
    rows = session.scalar(select(func.count()).select_from(StockItem)) or 0

    cons = (
        session.query(Consumption.day, func.sum(Consumption.quantity))
        .group_by(Consumption.day).order_by(Consumption.day).all()
    )
    trend = [{"day": d.isoformat(), "value": round(float(v), 1)} for d, v in cons[-30:]]

    return {
        "inventory_rows": int(rows),
        "medications": int(meds),
        "locations": int(locations),
        "total_units_on_hand": round(float(total_units), 1),
        "issues_total": sum(counts.values()),
        "issues_by_kind": counts,
        "top_issues": top_issues(session, min_days, limit=8, with_options=False),
        "consumption_trend": trend,
    }

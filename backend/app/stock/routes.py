"""
Stock API — relational inventory, built for 100K+ rows.

  GET    /api/v1/stock          paginated rows (limit/offset, optional drug/q)
  POST   /api/v1/stock          add one row
  PATCH  /api/v1/stock/{id}     update one row (incremental — no full-sheet PUT)
  DELETE /api/v1/stock/{id}     delete one row
  PUT    /api/v1/stock          full replace (used only on import)
  GET    /api/v1/stock/summary            per-drug totals (SUM on_hand, rows, locations)
  GET    /api/v1/stock/summary?drug=X     one drug: total + per-location breakdown
  GET    /api/v1/fhir/InventoryItem       FHIR Bundle view (generated from columns)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.db import get_session
from app.stock import fhir
from app.stock.models import StockItem
from app.stock.schemas import StockPut, StockRow, StockRowUpdate

router = APIRouter(tags=["stock"])


def _blank(row: dict) -> bool:
    return all(row.get(c) in ("", None) for c in fhir.STOCK_COLUMNS)


@router.get("/api/v1/stock")
def list_stock(
    limit: int = Query(200, le=2000),
    offset: int = 0,
    drug: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(StockItem)
    count_stmt = select(func.count()).select_from(StockItem)
    if drug:
        stmt = stmt.where(StockItem.drug == drug)
        count_stmt = count_stmt.where(StockItem.drug == drug)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(StockItem.drug.ilike(like))
        count_stmt = count_stmt.where(StockItem.drug.ilike(like))
    total = session.scalar(count_stmt) or 0
    items = [i.to_row() for i in session.scalars(stmt.order_by(StockItem.position).limit(limit).offset(offset))]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/api/v1/stock")
def add_stock(row: StockRow, session: Session = Depends(get_session)) -> dict:
    max_pos = session.scalar(select(func.max(StockItem.position))) or 0
    item = StockItem(position=max_pos + 1)
    item.apply(row.model_dump())
    session.add(item)
    session.commit()
    return item.to_row()


@router.patch("/api/v1/stock/{item_id}")
def update_stock(item_id: int, patch: StockRowUpdate, session: Session = Depends(get_session)) -> dict:
    item = session.get(StockItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="row not found")
    item.apply(patch.model_dump(exclude_none=True))
    session.commit()
    return item.to_row()


@router.delete("/api/v1/stock/{item_id}")
def delete_stock(item_id: int, session: Session = Depends(get_session)) -> dict:
    item = session.get(StockItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="row not found")
    session.delete(item)
    session.commit()
    return {"deleted": item_id}


@router.put("/api/v1/stock")
def replace_stock(body: StockPut, session: Session = Depends(get_session)) -> dict:
    """Full replace — used on import. Heavy; prefer PATCH for single edits."""
    session.execute(delete(StockItem))
    position = 0
    for row in body.items:
        data = row.model_dump()
        if _blank(data):
            continue
        item = StockItem(position=position)
        item.apply(data)
        session.add(item)
        position += 1
    session.commit()
    record(session, "stock.import", entity="StockItem", detail=f"replaced with {position} rows")
    return {"total": position}


@router.get("/api/v1/stock/summary")
def stock_summary(drug: str | None = None, session: Session = Depends(get_session)) -> dict:
    if drug:
        rows = session.execute(
            select(
                StockItem.location,
                func.sum(StockItem.on_hand),
                func.sum(StockItem.avg_daily_use),
                func.count(),
            ).where(StockItem.drug == drug).group_by(StockItem.location)
        ).all()
        total_on_hand = sum(float(r[1] or 0) for r in rows)
        total_daily = sum(float(r[2] or 0) for r in rows)
        return {
            "drug": drug,
            "total_on_hand": round(total_on_hand, 1),
            "rows": sum(int(r[3]) for r in rows),
            "locations": len(rows),
            "days_of_supply": round(total_on_hand / total_daily, 1) if total_daily > 0 else None,
            "by_location": [
                {"location": r[0], "on_hand": round(float(r[1] or 0), 1), "avg_daily_use": round(float(r[2] or 0), 1), "rows": int(r[3])}
                for r in sorted(rows, key=lambda r: -float(r[1] or 0))
            ],
        }

    rows = session.execute(
        select(StockItem.drug, func.sum(StockItem.on_hand), func.count(), func.count(func.distinct(StockItem.location)))
        .group_by(StockItem.drug)
        .order_by(func.sum(StockItem.on_hand).desc())
    ).all()
    return {
        "items": [
            {"drug": r[0], "total_on_hand": round(float(r[1] or 0), 1), "rows": int(r[2]), "locations": int(r[3])}
            for r in rows
        ]
    }


@router.get("/api/v1/fhir/InventoryItem")
def fhir_inventory(limit: int = Query(500, le=5000), offset: int = 0, session: Session = Depends(get_session)) -> dict:
    items = session.scalars(select(StockItem).order_by(StockItem.position).limit(limit).offset(offset))
    return fhir.to_bundle([fhir.row_to_inventory_item(i.to_row(), str(i.id)) for i in items])

"""
Relational inventory model.

Inventory is stored as indexed columns (not FHIR-JSON blobs) so pagination,
SQL aggregation ("how much in every stock"), and issue detection stay fast at
100K+ rows. A FHIR ``InventoryItem`` view is generated from these columns on
demand (see app/stock/fhir.py) to keep the data HL7-accessible.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _parse_date(v) -> Optional[date]:
    if isinstance(v, date):
        return v
    if not v:
        return None
    try:
        return datetime.strptime(str(v), "%Y-%m-%d").date()
    except ValueError:
        return None


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    drug: Mapped[str] = mapped_column(String, default="", index=True)
    location: Mapped[str] = mapped_column(String, default="")
    on_hand: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String, default="")
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    avg_daily_use: Mapped[float] = mapped_column(Float, default=0.0)
    supplier: Mapped[str] = mapped_column(String, default="")
    last_delivery: Mapped[str] = mapped_column(String, default="")

    __table_args__ = (Index("ix_stock_drug", "drug"),)

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "drug": self.drug,
            "location": self.location,
            "on_hand": self.on_hand,
            "unit": self.unit,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else "",
            "avg_daily_use": self.avg_daily_use,
            "supplier": self.supplier,
            "last_delivery": self.last_delivery,
        }

    def apply(self, data: dict) -> None:
        if "drug" in data:
            self.drug = str(data["drug"] or "")
        if "location" in data:
            self.location = str(data["location"] or "")
        if "on_hand" in data:
            self.on_hand = _num(data["on_hand"])
        if "unit" in data:
            self.unit = str(data["unit"] or "")
        if "expiry_date" in data:
            self.expiry_date = _parse_date(data["expiry_date"])
        if "avg_daily_use" in data:
            self.avg_daily_use = _num(data["avg_daily_use"])
        if "supplier" in data:
            self.supplier = str(data["supplier"] or "")
        if "last_delivery" in data:
            self.last_delivery = str(data["last_delivery"] or "")

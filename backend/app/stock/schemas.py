"""Request/response schemas for the stock API (grid-friendly rows)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class StockRow(BaseModel):
    """One inventory row as the grid sends it (numbers may arrive as strings)."""

    model_config = ConfigDict(extra="ignore")

    drug: str = ""
    location: str = ""
    on_hand: float | str | None = None
    unit: str = ""
    expiry_date: str = ""
    avg_daily_use: float | str | None = None
    supplier: str = ""
    last_delivery: str = ""


class StockRowUpdate(BaseModel):
    """Partial update for a single cell/row edit — only provided fields change."""

    model_config = ConfigDict(extra="ignore")

    drug: Optional[str] = None
    location: Optional[str] = None
    on_hand: float | str | None = None
    unit: Optional[str] = None
    expiry_date: Optional[str] = None
    avg_daily_use: float | str | None = None
    supplier: Optional[str] = None
    last_delivery: Optional[str] = None


class StockPut(BaseModel):
    """Full-sheet replace payload — used on import."""

    items: list[StockRow] = []

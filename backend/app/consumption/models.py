"""
Daily consumption model.

One row = quantity of a medication used at a location on a given day. This is
the daily time series the forecaster learns from (lags by day: 1/2/3/7/14).
Stored relationally (indexed on drug/day) for fast aggregation at 100K+ points;
a FHIR MedicationDispense view can be generated from these columns for interop.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Consumption(Base):
    __tablename__ = "consumption"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drug: Mapped[str] = mapped_column(String, index=True)
    location: Mapped[str] = mapped_column(String, default="")
    day: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("ix_consumption_drug_day", "drug", "day"),)

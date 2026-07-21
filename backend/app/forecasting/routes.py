"""
Forecast API — driven by the daily consumption history (2 years, lags by day).

  - GET /api/v1/forecast/overview  -> medication list + aggregate DAILY demand
                                      across all medications (recent window).
  - GET /api/v1/forecast/item?drug -> one medication's daily demand series.
  - POST /api/v1/forecast/predict  -> forecast N steps from a numeric series
                                      using the chosen model (XGB/RF/ARIMA/MA).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.consumption.models import Consumption
from app.db import get_session
from app.forecasting.simple import predict_series

router = APIRouter(tags=["forecasting"])

OVERVIEW_WINDOW = 180  # days of aggregate history to return
ITEM_WINDOW = 365      # days of per-drug history to return


class PredictIn(BaseModel):
    series: list[float] = []
    steps: int = 14
    model: str = "xgboost"
    lags: int | None = None


@router.post("/api/v1/forecast/predict")
def predict(body: PredictIn) -> dict:
    """Forecast `steps` ahead from a raw numeric series using the chosen model."""
    steps = max(1, min(365, body.steps))
    lags = body.lags
    if lags is not None:
        lags = max(1, min(60, int(lags)))
    series = [float(v) for v in body.series if v is not None]
    if len(series) < 2:
        raise HTTPException(status_code=400, detail="need at least 2 data points")
    try:
        predictions = predict_series(series, steps, body.model, lags)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"model": body.model, "steps": steps, "lags": lags, "predictions": predictions}


def _daily(session: Session, drug: str | None, window: int) -> tuple[list[str], list[float]]:
    q = session.query(Consumption.day, func.sum(Consumption.quantity))
    if drug is not None:
        q = q.filter(Consumption.drug == drug)
    rows = q.group_by(Consumption.day).order_by(Consumption.day).all()
    rows = rows[-window:]
    days = [d.isoformat() for d, _ in rows]
    values = [round(float(v), 1) for _, v in rows]
    return days, values


@router.get("/api/v1/forecast/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    meds = [m[0] for m in session.query(Consumption.drug).distinct().all()]
    days, aggregate = _daily(session, None, OVERVIEW_WINDOW)
    return {"days": days, "medications": sorted(meds), "aggregate": aggregate}


@router.get("/api/v1/forecast/item")
def item(drug: str = Query(...), session: Session = Depends(get_session)) -> dict:
    days, values = _daily(session, drug, ITEM_WINDOW)
    if not days:
        raise HTTPException(status_code=404, detail=f"no consumption history for {drug!r}")
    return {"drug": drug, "days": days, "values": values}

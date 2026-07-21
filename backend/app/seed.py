"""
Auto-seed synthetic data on startup when the database is empty.

So a fresh setup (fresh SQLite file, or a new Postgres) comes up already
populated — no need to run the data/synthetic scripts by hand. Controlled by
env vars:

  MEDOPS_AUTOSEED             "1" (default) to seed when empty, "0" to disable
  MEDOPS_SEED_INVENTORY       inventory rows to create (default 10000)
  MEDOPS_SEED_CONSUMPTION     daily consumption points (default 100000)

Seeding only runs when the relevant table is empty, so it never clobbers real
data and is cheap on subsequent starts. All records are synthetic (no PHI).
"""

from __future__ import annotations

import math
import os
import random
from datetime import date, datetime, timedelta
from itertools import product

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.consumption.models import Consumption
from app.stock.models import StockItem

BASE_DRUGS = [
    "Lisinopril", "Metformin", "Amoxicillin", "Atorvastatin", "Omeprazole",
    "Ibuprofen", "Amlodipine", "Metoprolol", "Losartan", "Albuterol",
    "Gabapentin", "Sertraline", "Simvastatin", "Levothyroxine", "Azithromycin",
]
STRENGTHS = ["10mg", "50mg", "500mg"]
LOCATIONS = ["Central Hospital", "Downtown Pharmacy", "Westside Clinic", "Northgate ICU", "ER Pharmacy"]
UNITS = ["tablet", "capsule", "vial", "ampoule"]
SUPPLIERS = ["PharmaCorp", "MediSource", "BioSupply", "HealthDist"]
CONSUMPTION_DAYS = 730  # 2 years


def _seed_inventory(session: Session, n: int) -> None:
    rng = random.Random(42)
    objs = []
    for i in range(n):
        drug = f"{rng.choice(BASE_DRUGS)} {rng.choice(STRENGTHS)}"
        objs.append(StockItem(
            position=i,
            drug=drug,
            location=rng.choice(LOCATIONS),
            on_hand=float(rng.randint(0, 5000)),
            unit=rng.choice(UNITS),
            expiry_date=datetime(2026, rng.randint(1, 12), rng.randint(1, 28)).date(),
            avg_daily_use=float(rng.randint(1, 120)),
            supplier=rng.choice(SUPPLIERS),
            last_delivery=f"2026-07-{rng.randint(1, 21):02d}",
        ))
    session.bulk_save_objects(objs)
    session.commit()


def _seed_consumption(session: Session, n_points: int) -> None:
    drugs = [f"{d} {s}" for d in BASE_DRUGS for s in STRENGTHS]
    pairs = list(product(drugs, LOCATIONS))[: max(1, math.ceil(n_points / CONSUMPTION_DAYS))]
    start = date.today() - timedelta(days=CONSUMPTION_DAYS)
    objs = []
    for idx, (drug, location) in enumerate(pairs):
        rng = np.random.default_rng(1000 + idx)
        base = float(rng.uniform(20, 200))
        trend = float(rng.uniform(-0.02, 0.06))
        for i in range(CONSUMPTION_DAYS):
            d = start + timedelta(days=i)
            weekly = 1.0 if d.weekday() < 5 else 0.55
            yearly = 1.0 + 0.18 * math.sin(2 * math.pi * (d.timetuple().tm_yday / 365.0) + math.pi)
            qty = max(0.0, (base + trend * i) * weekly * yearly + rng.normal(0, base * 0.08))
            objs.append(Consumption(drug=drug, location=location, day=d, quantity=round(qty, 1)))
    session.bulk_save_objects(objs)
    session.commit()


def seed_if_empty(session: Session) -> None:
    if os.environ.get("MEDOPS_AUTOSEED", "1") != "1":
        return
    inv = int(os.environ.get("MEDOPS_SEED_INVENTORY", "100000"))
    cons = int(os.environ.get("MEDOPS_SEED_CONSUMPTION", "100000"))

    if session.scalar(select(func.count()).select_from(StockItem)) == 0:
        _seed_inventory(session, inv)
    if session.scalar(select(func.count()).select_from(Consumption)) == 0:
        _seed_consumption(session, cons)

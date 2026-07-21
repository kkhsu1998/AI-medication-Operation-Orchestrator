"""
Generate ~100,000 daily consumption points over 2 years of history and load
them into the ``consumption`` table.

Each (medication, location) series spans 730 days with:
  - weekly seasonality (higher Mon-Fri, lower weekends)
  - yearly seasonality (winter respiratory bump)
  - a mild linear trend
  - Gaussian noise

Deterministic (seeded). No patient data.

Usage:
    python data/synthetic/generate_consumption.py [N_POINTS]
"""

from __future__ import annotations

import math
import sys
import time
from datetime import date, timedelta
from itertools import product
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.consumption.models import Consumption  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402

DAYS = 730  # 2 years
BASE_DRUGS = [
    "Lisinopril", "Metformin", "Amoxicillin", "Atorvastatin", "Omeprazole",
    "Ibuprofen", "Amlodipine", "Metoprolol", "Losartan", "Albuterol",
    "Gabapentin", "Sertraline", "Simvastatin", "Levothyroxine", "Azithromycin",
]
STRENGTHS = ["10mg", "50mg", "500mg"]
LOCATIONS = ["Central Hospital", "Downtown Pharmacy", "Westside Clinic", "Northgate ICU", "ER Pharmacy"]


def main(n_points: int) -> None:
    init_db()
    drugs = [f"{d} {s}" for d in BASE_DRUGS for s in STRENGTHS]  # 45 variants
    pairs = list(product(drugs, LOCATIONS))
    n_series = max(1, math.ceil(n_points / DAYS))
    pairs = pairs[:n_series]

    start = date.today() - timedelta(days=DAYS)
    t0 = time.time()

    with SessionLocal() as session:
        session.query(Consumption).delete()
        objs = []
        for idx, (drug, location) in enumerate(pairs):
            rng = np.random.default_rng(1000 + idx)
            base = float(rng.uniform(20, 200))
            trend = float(rng.uniform(-0.02, 0.06))  # per-day drift
            for i in range(DAYS):
                d = start + timedelta(days=i)
                weekly = 1.0 if d.weekday() < 5 else 0.55
                yearly = 1.0 + 0.18 * math.sin(2 * math.pi * (d.timetuple().tm_yday / 365.0) + math.pi)
                level = (base + trend * i) * weekly * yearly
                qty = max(0.0, level + rng.normal(0, base * 0.08))
                objs.append(Consumption(drug=drug, location=location, day=d, quantity=round(qty, 1)))
        session.bulk_save_objects(objs)
        session.commit()

    dt = time.time() - t0
    print(f"Loaded {len(objs):,} daily consumption points ({len(pairs)} series × {DAYS} days) in {dt:.2f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100_000)

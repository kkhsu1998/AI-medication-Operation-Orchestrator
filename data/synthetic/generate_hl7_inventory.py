"""
(Re)load synthetic inventory into the relational stock_items table.

Note: the backend now auto-seeds inventory on startup when empty
(app/seed.py). Use this script only to force a reload at a specific size.

Usage:
    python data/synthetic/generate_hl7_inventory.py [N]   # default 100000
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.db import SessionLocal, init_db  # noqa: E402
from app.seed import _seed_inventory  # noqa: E402
from app.stock.models import StockItem  # noqa: E402


def main(n: int) -> None:
    init_db()
    t0 = time.time()
    with SessionLocal() as session:
        session.query(StockItem).delete()
        session.commit()
        _seed_inventory(session, n)
    print(f"Loaded {n:,} inventory rows into stock_items in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100_000)

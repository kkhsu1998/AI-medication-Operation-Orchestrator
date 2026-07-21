"""
Database setup (SQLAlchemy 2.0, sync).

Defaults to a zero-config SQLite file so the app runs locally with no
infrastructure. Point ``DATABASE_URL`` at Postgres (the platform's target, e.g.
``postgresql+psycopg://medops:...@localhost:5432/medops``) to use that instead —
no code changes required.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Repo-relative default: <repo>/data/medops.db (the data/ dir already exists).
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "medops.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False when shared across FastAPI's threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if they don't exist. Fine for a prototype (no migrations)."""
    # Import models so they're registered on Base.metadata before create_all.
    from app.stock import models  # noqa: F401
    from app.consumption import models as _consumption_models  # noqa: F401
    from app.audit import models as _audit_models  # noqa: F401
    from app.settings import models as _settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI dependency: yield a session, always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

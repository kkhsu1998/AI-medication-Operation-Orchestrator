"""
Tests for the relational stock API: pagination, incremental edits (POST/PATCH/
DELETE), per-drug summaries, and the generated FHIR InventoryItem view.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.stock import models  # noqa: F401  (register tables)
from app.consumption import models as _c  # noqa: F401


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


SAMPLE = {
    "drug": "Lisinopril 10mg", "location": "Downtown Pharmacy", "on_hand": 420, "unit": "tablet",
    "expiry_date": "2026-03-01", "avg_daily_use": 55, "supplier": "PharmaCorp", "last_delivery": "2026-07-14",
}


def test_add_list_and_pagination(client):
    for i in range(5):
        client.post("/api/v1/stock", json={**SAMPLE, "drug": f"Drug {i}"})
    r = client.get("/api/v1/stock?limit=2&offset=0").json()
    assert r["total"] == 5
    assert len(r["items"]) == 2
    assert "id" in r["items"][0]


def test_patch_updates_single_row(client):
    created = client.post("/api/v1/stock", json=SAMPLE).json()
    r = client.patch(f"/api/v1/stock/{created['id']}", json={"on_hand": 999})
    assert r.status_code == 200
    assert r.json()["on_hand"] == 999
    # other fields untouched
    assert r.json()["drug"] == "Lisinopril 10mg"


def test_numeric_strings_coerced(client):
    r = client.post("/api/v1/stock", json={**SAMPLE, "on_hand": "88"}).json()
    assert r["on_hand"] == 88


def test_delete_row(client):
    created = client.post("/api/v1/stock", json=SAMPLE).json()
    assert client.delete(f"/api/v1/stock/{created['id']}").status_code == 200
    assert client.get("/api/v1/stock").json()["total"] == 0


def test_patch_missing_row_404(client):
    assert client.patch("/api/v1/stock/999", json={"on_hand": 1}).status_code == 404


def test_filter_by_drug(client):
    client.post("/api/v1/stock", json={**SAMPLE, "drug": "A"})
    client.post("/api/v1/stock", json={**SAMPLE, "drug": "B"})
    r = client.get("/api/v1/stock?drug=A").json()
    assert r["total"] == 1 and r["items"][0]["drug"] == "A"


def test_bulk_replace_import(client):
    client.post("/api/v1/stock", json=SAMPLE)
    client.put("/api/v1/stock", json={"items": [SAMPLE, {**SAMPLE, "drug": "X"}]})
    assert client.get("/api/v1/stock").json()["total"] == 2


def test_summary_per_drug(client):
    client.post("/api/v1/stock", json={**SAMPLE, "location": "Loc A", "on_hand": 100})
    client.post("/api/v1/stock", json={**SAMPLE, "location": "Loc B", "on_hand": 50})
    s = client.get(f"/api/v1/stock/summary?drug=Lisinopril 10mg").json()
    assert s["total_on_hand"] == 150
    assert s["locations"] == 2
    assert len(s["by_location"]) == 2


def test_summary_all_drugs(client):
    client.post("/api/v1/stock", json={**SAMPLE, "drug": "A", "on_hand": 10})
    client.post("/api/v1/stock", json={**SAMPLE, "drug": "B", "on_hand": 20})
    items = client.get("/api/v1/stock/summary").json()["items"]
    assert {i["drug"] for i in items} == {"A", "B"}


def test_fhir_view_generated(client):
    client.post("/api/v1/stock", json=SAMPLE)
    bundle = client.get("/api/v1/fhir/InventoryItem").json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["entry"][0]["resource"]["resourceType"] == "InventoryItem"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"

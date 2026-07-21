"""
Tests for the four "panel" route groups: Dashboard KPIs, Orchestrator
issues/decisions, Audit trail + change points, and Settings.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.stock import models  # noqa: F401  (register tables)
from app.consumption import models as _c  # noqa: F401
from app.audit import models as _a  # noqa: F401
from app.settings import models as _s  # noqa: F401
from app.settings.models import DEFAULTS


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


CHANGE_ID_RE = re.compile(r"^\d{14}$")

BASE_ROW = {
    "drug": "Lisinopril 10mg", "location": "Downtown Pharmacy", "on_hand": 100, "unit": "tablet",
    "expiry_date": "", "avg_daily_use": 5, "supplier": "PharmaCorp", "last_delivery": "2026-07-14",
}


def add_stock(client, **overrides):
    r = client.post("/api/v1/stock", json={**BASE_ROW, **overrides})
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------- dashboard

def test_dashboard_empty_db_all_zero(client):
    d = client.get("/api/v1/dashboard").json()
    assert d["inventory_rows"] == 0
    assert d["medications"] == 0
    assert d["locations"] == 0
    assert d["total_units_on_hand"] == 0
    assert d["issues_total"] == 0
    assert d["issues_by_kind"] == {"stockout": 0, "shortage": 0, "expiration_risk": 0, "overstock": 0}
    assert d["top_issues"] == []
    assert d["consumption_trend"] == []


def test_dashboard_counts_reflect_inventory(client):
    add_stock(client, drug="Amoxicillin", location="A", on_hand=0, avg_daily_use=5)  # stockout
    add_stock(client, drug="Metformin", location="A", on_hand=10, avg_daily_use=10)  # dos=1 -> shortage
    add_stock(client, drug="Lisinopril 10mg", location="A", on_hand=100, avg_daily_use=5)  # dos=20 -> healthy

    d = client.get("/api/v1/dashboard").json()
    assert d["inventory_rows"] == 3
    assert d["medications"] == 3
    assert d["locations"] == 1
    assert d["total_units_on_hand"] == 110
    assert d["issues_by_kind"]["stockout"] == 1
    assert d["issues_by_kind"]["shortage"] == 1
    assert d["issues_by_kind"]["expiration_risk"] == 0
    assert d["issues_by_kind"]["overstock"] == 0
    assert d["issues_total"] == 2
    kinds = [i["kind"] for i in d["top_issues"]]
    assert kinds == ["stockout", "shortage"]
    # dashboard top_issues never carry options
    assert all(i["options"] == [] for i in d["top_issues"])


# ------------------------------------------------------------- orchestrator

def test_issues_transfer_option_first_when_surplus_exists(client):
    # Shortage at A; big surplus of the SAME drug at B (dos = 3000/10 = 300 > 21).
    add_stock(client, drug="Metformin", location="A", on_hand=10, avg_daily_use=10)
    add_stock(client, drug="Metformin", location="B", on_hand=3000, avg_daily_use=10)

    r = client.get("/api/v1/orchestrator/issues").json()
    shortages = [i for i in r["items"] if i["kind"] == "shortage"]
    assert len(shortages) == 1
    issue = shortages[0]
    assert issue["id"] == "Metformin::A"
    assert issue["days_of_supply"] == 1.0
    types = [o["type"] for o in issue["options"]]
    assert types == ["transfer", "procurement"]
    assert issue["options"][0]["score"] == 0.9
    assert "B" in issue["options"][0]["label"]
    assert issue["options"][1]["score"] == 0.6
    # total counts every issue kind (the surplus row is itself an overstock)
    assert r["total"] == len(r["items"]) == 2


def test_issues_procurement_only_without_surplus(client):
    add_stock(client, drug="Metformin", location="A", on_hand=10, avg_daily_use=10, supplier="Acme")
    r = client.get("/api/v1/orchestrator/issues").json()
    assert r["total"] == 1
    issue = r["items"][0]
    assert issue["kind"] == "shortage"
    assert [o["type"] for o in issue["options"]] == ["procurement"]
    assert "Acme" in issue["options"][0]["label"]


def test_decision_approve_creates_task_and_audit(client):
    body = {"issue_id": "Metformin::A", "drug": "Metformin", "location": "A",
            "option_type": "transfer", "decision": "approved", "reason": "urgent"}
    r = client.post("/api/v1/orchestrator/decision", json=body).json()
    assert r["status"] == "approved"
    assert r["issue_id"] == "Metformin::A"
    assert r["task_id"]

    audit = client.get("/api/v1/audit").json()
    by_action = {a["action"]: a for a in audit["items"]}
    assert "orchestrator.approve" in by_action
    assert "task.create" in by_action
    approve = by_action["orchestrator.approve"]
    assert CHANGE_ID_RE.match(approve["change_id"])
    assert approve["entity"] == "Metformin::A"
    assert "urgent" in approve["detail"]
    task = by_action["task.create"]
    assert CHANGE_ID_RE.match(task["change_id"])
    assert task["entity"] == r["task_id"]
    assert task["actor"] == "system"


def test_decision_reject_no_task(client):
    body = {"issue_id": "Metformin::A", "decision": "rejected", "reason": "not needed"}
    r = client.post("/api/v1/orchestrator/decision", json=body).json()
    assert r["status"] == "rejected"
    assert r["task_id"] is None

    audit = client.get("/api/v1/audit").json()
    actions = [a["action"] for a in audit["items"]]
    assert "orchestrator.reject" in actions
    assert "task.create" not in actions


# --------------------------------------------------------- audit/changepoints

def test_changepoint_roundtrip(client):
    r = client.post("/api/v1/changepoints",
                    json={"action": "docs.update", "source": "mcp", "target": "readme", "detail": "edited"})
    assert r.status_code == 200
    cp = r.json()
    assert CHANGE_ID_RE.match(cp["change_id"])
    assert cp["action"] == "docs.update"
    assert cp["actor"] == "mcp"
    assert cp["entity"] == "readme"

    listed = client.get("/api/v1/changepoints").json()["items"]
    assert any(i["change_id"] == cp["change_id"] and i["action"] == "docs.update" for i in listed)
    # newest first: timestamps non-increasing
    ts = [i["ts"] for i in listed]
    assert ts == sorted(ts, reverse=True)


def test_audit_pagination(client):
    for i in range(5):
        client.post("/api/v1/changepoints", json={"action": f"step.{i}"})
    page = client.get("/api/v1/audit?limit=2&offset=0").json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    rest = client.get("/api/v1/audit?limit=100&offset=4").json()
    assert rest["total"] == 5
    assert len(rest["items"]) == 1
    empty = client.get("/api/v1/audit").json()  # default limit covers all
    assert len(empty["items"]) == 5


# ------------------------------------------------------------------ settings

def test_settings_defaults(client):
    items = client.get("/api/v1/settings").json()["items"]
    assert {i["key"] for i in items} == set(DEFAULTS)
    for i in items:
        assert i["value"] == float(DEFAULTS[i["key"]]["value"])
        assert i["label"] == DEFAULTS[i["key"]]["label"]
        assert i["group"] == DEFAULTS[i["key"]]["group"]


def test_settings_patch_persists_and_audits(client):
    r = client.patch("/api/v1/settings", json={"values": {"days_of_supply_minimum": 10}})
    updated = {i["key"]: i["value"] for i in r.json()["items"]}
    assert updated["days_of_supply_minimum"] == 10.0

    again = {i["key"]: i["value"] for i in client.get("/api/v1/settings").json()["items"]}
    assert again["days_of_supply_minimum"] == 10.0

    audit = client.get("/api/v1/audit").json()["items"]
    entries = [a for a in audit if a["action"] == "settings.update"]
    assert len(entries) == 1
    assert "days_of_supply_minimum=10" in entries[0]["detail"]
    assert CHANGE_ID_RE.match(entries[0]["change_id"])


def test_settings_patch_ignores_unknown_keys(client):
    r = client.patch("/api/v1/settings", json={"values": {"bogus_key": 42}})
    assert r.status_code == 200
    keys = {i["key"] for i in r.json()["items"]}
    assert "bogus_key" not in keys
    # no-op patch records no audit entry
    actions = [a["action"] for a in client.get("/api/v1/audit").json()["items"]]
    assert "settings.update" not in actions


def test_dashboard_respects_min_days_setting(client):
    # dos = 10 — not a shortage at the default min of 7, but one at 15.
    add_stock(client, drug="Metformin", location="A", on_hand=100, avg_daily_use=10)
    assert client.get("/api/v1/dashboard").json()["issues_by_kind"]["shortage"] == 0
    client.patch("/api/v1/settings", json={"values": {"days_of_supply_minimum": 15}})
    assert client.get("/api/v1/dashboard").json()["issues_by_kind"]["shortage"] == 1

"""Tests for the public landing page and the dashboard portal routes."""
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from resumetool.config import Settings
from resumetool.database.models import (
    Application, Base, Candidate, Company, JobRequisition,
    TierEnum, TriageResult,
)


@pytest.fixture
def client(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite:///{path}"
    monkeypatch.setenv("RESUMETOOL_DATABASE_URL", url)
    monkeypatch.setenv("RESUMETOOL_DRY_RUN_EMAIL", "true")
    monkeypatch.setenv("RESUMETOOL_HR_AUTH_USERS", "admin:changeme")
    import resumetool.config as cfg
    cfg.settings = Settings()
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    # Re-seed the global engine so FastAPI lifespan uses the same DB
    import resumetool.database.session as sess
    sess.engine = engine
    sess.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    from resumetool.server.app import app
    yield TestClient(app), sessionmaker(bind=engine)
    Path(path).unlink(missing_ok=True)


def _seed_funnel(session_factory, tier_counts: dict[str, int]):
    db = session_factory()
    try:
        company = Company(id=str(uuid.uuid4()), name="Demo Co")
        req = JobRequisition(
            id=str(uuid.uuid4()),
            company_id=company.id,
            title="Platform Engineer",
            description="K8s + AWS + Python",
            status="open",
            criteria=[{"name": "K8s depth", "description": "k8s", "weight": 1.0}],
            stage_weights={"stage1": 0.5, "stage2": 0.35, "behavioral": 0.15},
        )
        db.add_all([company, req])
        db.commit()
        for tier, n in tier_counts.items():
            for _ in range(n):
                cand = Candidate(
                    id=str(uuid.uuid4()),
                    email=f"{uuid.uuid4().hex[:8]}@example.com",
                    name=f"Candidate {uuid.uuid4().hex[:6]}",
                    resume_text="Resume text",
                    resume_parsed={},
                )
                app = Application(
                    id=str(uuid.uuid4()),
                    req_id=req.id,
                    candidate_id=cand.id,
                    applied_at=datetime.utcnow() - timedelta(days=1),
                    source="linkedin",
                    application_metadata={},
                )
                triage = TriageResult(
                    id=str(uuid.uuid4()),
                    application_id=app.id,
                    stage1_score=0.5,
                    stage1_detail={},
                    stage2_score=None,
                    stage2_notes={},
                    behavioral_score=0.5,
                    behavioral_detail={},
                    composite_score=0.5,
                    tier=TierEnum(tier),
                    response_email_body=f"Body for {tier}",
                    response_sent_at=None,
                )
                db.add_all([cand, app, triage])
        db.commit()
        return req.id
    finally:
        db.close()


def test_landing_unauthed_ok(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "Process 250 resumes" in r.text or "250 resumes" in r.text
    assert "Tier A" in r.text and "Tier D" in r.text
    # New marketing-page sections
    for needle in ("trust-bar", "problem", "pillars", "risk",
                   "personas", "testimonials", "compare", "faq"):
        assert needle in r.text, f"missing marketing section: {needle}"
    # Free-pilot panel replaces the old pricing tier section
    assert "why-free" in r.text or "Why this is free" in r.text
    assert "first" in r.text and "2 companies" in r.text
    # Pilot asks-for / offers-for copy
    assert "What happens next" in r.text
    assert "What helps me decide" in r.text
    # Testimonials have real-looking names
    assert "Jamie Chen" in r.text
    # Risk section is research-backed
    assert "EEOC" in r.text
    # Reframe callout is present
    assert "reframe" in r.text
    # Old pricing tiers are gone
    assert "Starter" not in r.text
    assert "$199" not in r.text
    assert "alongside" in r.text
    assert "Keyword density" in r.text
    assert "Demonstrated competency" in r.text
    # Signal-quality problem card is present
    assert "lossy" in r.text or "wrong direction" in r.text
    assert "retaliation" in r.text
    assert "29 C.F.R. §1607" in r.text or "Uniform Guidelines" in r.text


def test_demo_unauthed_ok(client):
    c, _ = client
    r = c.get("/demo")
    assert r.status_code == 200
    assert "60" in r.text  # "60 seconds"
    assert "Start the demo" in r.text or "Start" in r.text
    # All 6 stages referenced
    for stage in ("Apply", "Triage", "Screen", "AI Interview", "HR Review", "Hire"):
        assert stage in r.text, f"missing demo stage: {stage}"
    # Closing promise: nobody left unheard
    assert "heard back" in r.text.lower() or "heard" in r.text.lower()


def test_dashboard_unauthed_returns_401(client):
    c, _ = client
    r = c.get("/dashboard")
    assert r.status_code == 401


def test_dashboard_empty(client):
    c, _ = client
    r = c.get("/dashboard", auth=("admin", "changeme"))
    assert r.status_code == 200
    assert "No applications" in r.text or "No requisitions" in r.text or "Pick a role" in r.text


def test_funnel_page_shows_counts(client):
    c, session_factory = client
    _seed_funnel(session_factory, {"A": 2, "B": 8, "C": 20, "D": 20})
    r = c.get("/dashboard/funnel", auth=("admin", "changeme"))
    assert r.status_code == 200
    assert "Funnel" in r.text or "Tier" in r.text
    # Should show 50 total candidates
    assert "50" in r.text


def test_outbox_groups_by_tier(client):
    c, session_factory = client
    _seed_funnel(session_factory, {"A": 1, "B": 1, "C": 1, "D": 1})
    r = c.get("/dashboard/outbox", auth=("admin", "changeme"))
    assert r.status_code == 200
    # Each tier header should appear
    for tier in "ABCD":
        assert f"Tier {tier}" in r.text


def test_outbox_detail_renders_email_preview(client):
    c, session_factory = client
    _seed_funnel(session_factory, {"C": 1})
    from resumetool.database.models import TriageResult
    db = session_factory()
    try:
        app_id = db.query(TriageResult).first().application_id
    finally:
        db.close()
    r = c.get(f"/dashboard/outbox/{app_id}", auth=("admin", "changeme"))
    assert r.status_code == 200
    assert "Body for C" in r.text or "Send log" in r.text or "Send now" in r.text


def test_send_outbox_marks_sent(client):
    c, session_factory = client
    _seed_funnel(session_factory, {"B": 1})
    from resumetool.database.models import TriageResult
    db = session_factory()
    try:
        app_id = db.query(TriageResult).first().application_id
    finally:
        db.close()
    r = c.post(f"/dashboard/outbox/{app_id}/send", auth=("admin", "changeme"))
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    # Check the triage result is marked sent
    db = session_factory()
    try:
        triage = db.query(TriageResult).first()
        assert triage.response_sent_at is not None
    finally:
        db.close()


def test_static_css_served(client):
    c, _ = client
    r = c.get("/static/portal.css")
    assert r.status_code == 200
    assert "design-token" in r.text or "--ink" in r.text
    r = c.get("/static/landing.css")
    assert r.status_code == 200


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

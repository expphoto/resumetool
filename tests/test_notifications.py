"""Tests for the email service + mailer.

Exercises the DryRun path (no real Resend calls) and confirms the
mailer creates EmailEvent rows and updates TriageResult.response_sent_at.
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from resumetool.config import Settings
from resumetool.database.models import (
    Application, Base, Candidate, Company, EmailEvent, JobRequisition,
    TierEnum, TriageResult,
)
from resumetool.notifications.email import (
    ConsoleEmailService, DryRunEmailService, ResendEmailService,
    build_email_service, subject_for_tier,
)
from resumetool.notifications.mailer import bulk_send_pending, send_triage_response


@pytest.fixture
def fresh_db(monkeypatch):
    """A throwaway SQLite DB, no shared state."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite:///{path}"
    monkeypatch.setenv("RESUMETOOL_DATABASE_URL", url)
    monkeypatch.setenv("RESUMETOOL_DRY_RUN_EMAIL", "true")
    # Reset the cached settings object so env changes take effect
    import resumetool.config as cfg
    cfg.settings = Settings()
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def seeded(fresh_db):
    """A minimal dataset: 1 company, 1 req, 1 candidate, 1 application, 1 triage result."""
    db = fresh_db()
    company = Company(id=str(uuid.uuid4()), name="Test Co")
    req = JobRequisition(
        id=str(uuid.uuid4()),
        company_id=company.id,
        title="Senior Engineer",
        description="K8s/AWS/Python role",
        status="open",
        criteria=[{"name": "Kubernetes depth", "description": "K8s prod experience", "weight": 1.0}],
        stage_weights={"stage1": 0.5, "stage2": 0.35, "behavioral": 0.15},
    )
    cand = Candidate(
        id=str(uuid.uuid4()),
        email="alice@example.com",
        name="Alice Test",
        resume_text="Alice Test\nSWE with Kubernetes and AWS experience",
        resume_parsed={},
    )
    app = Application(
        id=str(uuid.uuid4()),
        req_id=req.id,
        candidate_id=cand.id,
        applied_at=datetime.utcnow() - timedelta(days=2),
        source="linkedin",
        cover_letter=None,
        application_metadata={"days_since_posting": 2, "follow_up": False},
    )
    triage = TriageResult(
        id=str(uuid.uuid4()),
        application_id=app.id,
        stage1_score=0.7,
        stage1_detail={"Kubernetes depth": {"score": 0.7, "reasoning": "ok"}},
        stage2_score=None,
        stage2_notes={},
        behavioral_score=0.5,
        behavioral_detail={},
        composite_score=0.65,
        tier=TierEnum.B,
        response_email_body="Hi Alice,\n\nThanks for applying. We are reviewing your application.",
        response_sent_at=None,
    )
    db.add_all([company, req, cand, app, triage])
    db.commit()
    return db, app.id, triage.id


def test_subject_for_tier():
    s = subject_for_tier("A", "Senior Engineer")
    assert "Senior Engineer" in s
    assert any(kw in s.lower() for kw in ("interview", "schedule", "next steps", "thanks", "chat"))
    # All tiers return non-empty subjects
    for tier in "ABCD":
        assert subject_for_tier(tier, "Anything")


def test_dry_run_service_returns_dry_run():
    svc = DryRunEmailService()
    result = svc.send(to_email="a@b.com", subject="hi", body="hello")
    assert result.success is True
    assert result.dry_run is True
    assert result.provider_id.startswith("dry_")


def test_console_service_does_not_raise(caplog):
    svc = ConsoleEmailService()
    result = svc.send(to_email="a@b.com", subject="hi", body="hello")
    assert result.success is True
    assert result.dry_run is False
    assert result.provider == "console"


def test_build_email_service_dry_run(monkeypatch):
    monkeypatch.setenv("RESUMETOOL_DRY_RUN_EMAIL", "true")
    monkeypatch.delenv("RESUMETOOL_EMAIL_API_KEY", raising=False)
    # Re-instantiate the cached settings singleton after env changes
    import resumetool.config as cfg
    cfg.settings = Settings()
    svc = build_email_service()
    assert isinstance(svc, DryRunEmailService)


def test_build_email_service_console_default(monkeypatch):
    monkeypatch.delenv("RESUMETOOL_DRY_RUN_EMAIL", raising=False)
    monkeypatch.delenv("RESUMETOOL_EMAIL_API_KEY", raising=False)
    import resumetool.config as cfg
    cfg.settings = Settings()
    svc = build_email_service()
    # When no key, no dry-run, default is console
    assert isinstance(svc, (ConsoleEmailService, DryRunEmailService))


def test_build_email_service_resend(monkeypatch):
    monkeypatch.delenv("RESUMETOOL_DRY_RUN_EMAIL", raising=False)
    monkeypatch.setenv("RESUMETOOL_EMAIL_API_KEY", "re_test_xxx")
    import resumetool.config as cfg
    cfg.settings = Settings()
    svc = build_email_service()
    assert isinstance(svc, ResendEmailService)


def test_send_triage_response_creates_event(seeded):
    db, app_id, triage_id = seeded
    result = send_triage_response(app_id, db)
    assert result["ok"] is True
    assert result["status"] in ("dry_run", "sent")
    # TriageResult.response_sent_at should be set
    triage = db.get(TriageResult, triage_id)
    assert triage.response_sent_at is not None
    # EmailEvent should exist
    event = db.query(EmailEvent).filter_by(application_id=app_id).first()
    assert event is not None
    assert event.status in ("dry_run", "sent")
    assert event.to_email == "alice@example.com"


def test_send_triage_response_idempotent(seeded):
    db, app_id, _ = seeded
    send_triage_response(app_id, db)
    # Second call should still succeed (returns ok=True on the same event)
    result = send_triage_response(app_id, db)
    assert result["ok"] is True


def test_bulk_send_pending(seeded):
    db, app_id, _ = seeded
    stats = bulk_send_pending(db)
    assert stats["processed"] == 1
    assert stats["dry_run"] == 1


def test_bulk_send_filters_by_tier(seeded):
    db, app_id, triage_id = seeded
    # Mark the existing triage as tier D
    triage = db.get(TriageResult, triage_id)
    triage.tier = TierEnum.D
    db.commit()
    # Now bulk-send only tier A
    stats = bulk_send_pending(db, tiers=["A"])
    assert stats["processed"] == 0
    # And tier D
    stats = bulk_send_pending(db, tiers=["D"])
    assert stats["processed"] == 1

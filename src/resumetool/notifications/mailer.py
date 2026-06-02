"""High-level mailer: send a TriageResult's response email and persist the event.

Keeps the route handlers free of email-service plumbing. Always goes
through :func:`build_email_service` so the right provider is picked
automatically based on config.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from resumetool.database.models import Application, TriageResult
from resumetool.notifications.email import (
    build_email_service,
    log_email_event,
    subject_for_tier,
)

logger = logging.getLogger(__name__)


def send_triage_response(
    application_id: str,
    db: Session,
    force_dry_run: Optional[bool] = None,
) -> dict:
    """Send the response email for a single application's triage result.

    Returns a small dict describing the outcome so route handlers can render
    flash messages or JSON.
    """
    app: Application = db.get(Application, application_id)
    if not app:
        return {"ok": False, "error": "Application not found"}
    result: TriageResult = (
        db.query(TriageResult).filter_by(application_id=application_id).first()
    )
    if not result or not result.response_email_body:
        return {"ok": False, "error": "No generated response email on this triage result"}

    candidate = app.candidate
    tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
    req = app.requisition
    subject = subject_for_tier(tier, req.title if req else None)

    service = build_email_service(force_dry_run=force_dry_run)
    outcome = service.send(
        to_email=candidate.email,
        subject=subject,
        body=result.response_email_body,
    )

    from datetime import datetime
    status = "dry_run" if outcome.dry_run else ("sent" if outcome.success else "failed")
    event = log_email_event(
        db,
        application_id=application_id,
        tier=tier,
        to_email=candidate.email,
        subject=subject,
        body=result.response_email_body,
        status=status,
        provider=outcome.provider,
        provider_id=outcome.provider_id,
        error=outcome.error,
        sent_at=datetime.utcnow() if status in ("sent", "dry_run") else None,
    )

    return {
        "ok": outcome.success,
        "status": status,
        "provider": outcome.provider,
        "provider_id": outcome.provider_id,
        "error": outcome.error,
        "event_id": event.id,
    }


def bulk_send_pending(
    db: Session,
    req_id: Optional[str] = None,
    tiers: Optional[list[str]] = None,
    force_dry_run: Optional[bool] = None,
    limit: int = 500,
) -> dict:
    """Send queued response emails for every application in scope.

    "Pending" means: triage result exists with a response body, and the
    application has not yet had a successful send (no TriageResult
    response_sent_at, and no successful EmailEvent).
    """
    q = (
        db.query(Application)
        .join(TriageResult, TriageResult.application_id == Application.id)
        .filter(TriageResult.response_email_body.isnot(None))
        .filter(TriageResult.response_sent_at.is_(None))
    )
    if req_id:
        q = q.filter(Application.req_id == req_id)
    if tiers:
        q = q.filter(TriageResult.tier.in_(tiers))
    apps = q.limit(limit).all()

    sent = dry_run = failed = 0
    for app in apps:
        result = send_triage_response(app.id, db, force_dry_run=force_dry_run)
        if not result.get("ok"):
            failed += 1
        elif result.get("status") == "dry_run":
            dry_run += 1
        else:
            sent += 1

    return {
        "processed": len(apps),
        "sent": sent,
        "dry_run": dry_run,
        "failed": failed,
    }

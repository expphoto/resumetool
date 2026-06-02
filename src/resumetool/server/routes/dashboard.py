"""HR web dashboard views (Jinja2 rendered) — auth required."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import (
    Application, EmailEvent, HMDecisionRecord, JobRequisition,
    ScreeningSession, TriageResult,
)
from resumetool.notifications import build_email_service, subject_for_tier
from resumetool.notifications.mailer import bulk_send_pending, send_triage_response

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/resumetool/server/templates")


# =========================================================================
#  Top-level dashboard
# =========================================================================

@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/dashboard/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    req_id: str | None = None,
    tier: str | None = None,
    db: Session = Depends(get_db),
):
    """Main HR dashboard: list all active reqs, show candidates for selected req."""
    reqs = db.query(JobRequisition).filter_by(status="open").all()

    candidates = []
    selected_req = None
    if req_id:
        selected_req = db.get(JobRequisition, req_id)
        apps = db.query(Application).filter_by(req_id=req_id).all()
        for app in apps:
            result = db.query(TriageResult).filter_by(application_id=app.id).first()
            screening = db.query(ScreeningSession).filter_by(application_id=app.id).first()
            decision = db.query(HMDecisionRecord).filter_by(application_id=app.id).first()
            if not result:
                continue
            detail = result.stage1_detail or {}
            tier_val = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
            if tier and tier_val != tier:
                continue
            candidates.append({
                "application_id": app.id,
                "name": app.candidate.name or "Unknown",
                "email": app.candidate.email,
                "tier": tier_val,
                "composite_score": result.composite_score or 0.0,
                "stage1_score": result.stage1_score,
                "stage2_score": result.stage2_score,
                "behavioral_score": result.behavioral_score,
                "screen_status": (
                    screening.status.value if screening and hasattr(screening.status, "value")
                    else (str(screening.status) if screening else "pending")
                ),
                "top_strengths": detail.get("_top_strengths", []),
                "top_gaps": detail.get("_top_gaps", []),
                "hm_decision": (
                    decision.decision.value if decision and hasattr(decision.decision, "value")
                    else None
                ),
                "applied_at": app.applied_at,
                "response_sent_at": result.response_sent_at,
            })
        # Sort: tier A first, then by composite score descending
        tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        candidates.sort(key=lambda c: (tier_order.get(c["tier"], 9), -c["composite_score"]))

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "requisitions": reqs,
            "selected_req": selected_req,
            "candidates": candidates,
            "req_id": req_id,
            "tier_filter": tier,
        },
    )


# =========================================================================
#  Per-candidate detail
# =========================================================================

@router.get("/dashboard/candidates/{application_id}", response_class=HTMLResponse)
def candidate_detail(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Full candidate detail page for HM review."""
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")

    result = db.query(TriageResult).filter_by(application_id=application_id).first()
    screening = db.query(ScreeningSession).filter_by(application_id=application_id).first()
    decision = db.query(HMDecisionRecord).filter_by(application_id=application_id).first()
    email_events = (
        db.query(EmailEvent)
        .filter_by(application_id=application_id)
        .order_by(EmailEvent.created_at.desc())
        .all()
    )

    criterion_scores = []
    if result and result.stage1_detail:
        for name, detail in result.stage1_detail.items():
            if name.startswith("_") or not isinstance(detail, dict):
                continue
            criterion_scores.append({
                "name": name,
                "score": detail.get("score", 0),
                "reasoning": detail.get("reasoning", ""),
            })
        criterion_scores.sort(key=lambda x: -x["score"])

    tier = None
    if result:
        tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)

    # Where the response email *would* go
    send_subject = subject_for_tier(tier, app.requisition.title if app.requisition else None)
    send_recipient = app.candidate.email if app.candidate else None

    return templates.TemplateResponse(
        "candidate.html",
        {
            "request": request,
            "app": app,
            "candidate": app.candidate,
            "req": app.requisition,
            "result": result,
            "tier": tier,
            "criterion_scores": criterion_scores,
            "screening": screening,
            "decision": decision,
            "email_events": email_events,
            "send_subject": send_subject,
            "send_recipient": send_recipient,
        },
    )


# =========================================================================
#  Funnel analytics
# =========================================================================

@router.get("/dashboard/funnel", response_class=HTMLResponse)
def funnel(request: Request, req_id: str | None = None, db: Session = Depends(get_db)):
    """Aggregate funnel view: per-tier counts, screen status, decision status."""
    reqs = db.query(JobRequisition).filter_by(status="open").all()
    selected_req = db.get(JobRequisition, req_id) if req_id else None

    scope_apps = db.query(Application)
    if selected_req:
        scope_apps = scope_apps.filter_by(req_id=selected_req.id)
    apps = scope_apps.all()
    app_ids = [a.id for a in apps]

    results = (
        db.query(TriageResult).filter(TriageResult.application_id.in_(app_ids)).all()
        if app_ids else []
    )
    by_tier = Counter()
    by_screen = Counter()
    by_decision = Counter()
    for r in results:
        t = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        by_tier[t] += 1
    for app_id in app_ids:
        s: ScreeningSession = (
            db.query(ScreeningSession).filter_by(application_id=app_id).first()
        )
        if s:
            v = s.status.value if hasattr(s.status, "value") else str(s.status)
            by_screen[v] += 1
        d: HMDecisionRecord = (
            db.query(HMDecisionRecord).filter_by(application_id=app_id).first()
        )
        if d:
            v = d.decision.value if hasattr(d.decision, "value") else str(d.decision)
            by_decision[v] += 1

    total_apps = len(apps)
    triaged = len(results)
    decided = sum(by_decision.values())

    emails_total = (
        db.query(EmailEvent).filter(EmailEvent.application_id.in_(app_ids)).count()
        if app_ids else 0
    )
    emails_sent = (
        db.query(EmailEvent)
        .filter(EmailEvent.application_id.in_(app_ids))
        .filter(EmailEvent.status.in_(["sent", "dry_run"]))
        .count()
        if app_ids else 0
    )

    tier_definitions = [
        ("A", "Fast-track to interview", "Reach out within 1 business day.", "var(--tier-a)"),
        ("B", "Hold pool — HM review", "Under active review for 5-7 business days.", "var(--tier-b)"),
        ("C", "Polite decline + feedback", "Name 1-2 specific gaps, encourage.", "var(--tier-c)"),
        ("D", "Brief, warm decline", "Acknowledge the time spent, no details.", "var(--tier-d)"),
    ]

    return templates.TemplateResponse(
        "funnel.html",
        {
            "request": request,
            "requisitions": reqs,
            "selected_req": selected_req,
            "req_id": req_id,
            "total_apps": total_apps,
            "triaged": triaged,
            "decided": decided,
            "by_tier": dict(by_tier),
            "by_screen": dict(by_screen),
            "by_decision": dict(by_decision),
            "emails_total": emails_total,
            "emails_sent": emails_sent,
            "tier_definitions": tier_definitions,
        },
    )


# =========================================================================
#  Outbox (communication queue)
# =========================================================================

@router.get("/dashboard/outbox", response_class=HTMLResponse)
def outbox(
    request: Request,
    req_id: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """Communication queue: every response email we can send, grouped by tier."""
    reqs = db.query(JobRequisition).filter_by(status="open").all()
    selected_req = db.get(JobRequisition, req_id) if req_id else None

    q = (
        db.query(Application, TriageResult, EmailEvent)
        .join(TriageResult, TriageResult.application_id == Application.id)
        .outerjoin(
            EmailEvent,
            EmailEvent.id == (
                db.query(EmailEvent.id)
                .filter(EmailEvent.application_id == Application.id)
                .order_by(EmailEvent.created_at.desc())
                .limit(1)
                .correlate(Application)
                .scalar_subquery()
            ),
        )
        .filter(TriageResult.response_email_body.isnot(None))
    )
    if selected_req:
        q = q.filter(Application.req_id == selected_req.id)
    if tier:
        q = q.filter(TriageResult.tier == tier)
    rows = q.all()

    by_tier: dict[str, list[dict]] = {"A": [], "B": [], "C": [], "D": []}
    for app, result, event in rows:
        t_val = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
        if t_val not in by_tier:
            by_tier[t_val] = []
        evt_status = (
            event.status.value if event and hasattr(event.status, "value")
            else (str(event.status) if event else None)
        )
        if status and evt_status != status:
            continue
        by_tier[t_val].append({
            "application_id": app.id,
            "candidate_name": app.candidate.name or "Unknown",
            "candidate_email": app.candidate.email,
            "tier": t_val,
            "subject": subject_for_tier(t_val, app.requisition.title if app.requisition else None),
            "body_preview": (result.response_email_body or "")[:140],
            "email_status": evt_status,
            "sent_at": event.sent_at if event else None,
            "provider": event.provider if event else None,
        })
    for t in by_tier:
        by_tier[t].sort(key=lambda r: r["candidate_name"] or "")

    # Determine the email service mode for the bulk-action button label
    service = build_email_service()
    service_mode = service.name  # "dry_run" / "resend" / "console"

    return templates.TemplateResponse(
        "outbox.html",
        {
            "request": request,
            "requisitions": reqs,
            "selected_req": selected_req,
            "req_id": req_id,
            "by_tier": by_tier,
            "tier_filter": tier,
            "status_filter": status,
            "service_mode": service_mode,
        },
    )


@router.get("/dashboard/outbox/{application_id}", response_class=HTMLResponse)
def outbox_detail(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Full email preview + send controls for one candidate."""
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    result = db.query(TriageResult).filter_by(application_id=application_id).first()
    if not result or not result.response_email_body:
        raise HTTPException(404, "No generated response email yet")

    tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
    subject = subject_for_tier(tier, app.requisition.title if app.requisition else None)
    events = (
        db.query(EmailEvent)
        .filter_by(application_id=application_id)
        .order_by(EmailEvent.created_at.desc())
        .all()
    )
    service = build_email_service()
    return templates.TemplateResponse(
        "outbox_detail.html",
        {
            "request": request,
            "app": app,
            "candidate": app.candidate,
            "req": app.requisition,
            "result": result,
            "tier": tier,
            "subject": subject,
            "body": result.response_email_body,
            "events": events,
            "service_mode": service.name,
        },
    )


# =========================================================================
#  Send actions
# =========================================================================

@router.post("/dashboard/outbox/{application_id}/send")
def outbox_send(application_id: str, db: Session = Depends(get_db)):
    """Send the response email for a single application. JSON response."""
    return send_triage_response(application_id, db)


@router.post("/dashboard/outbox/bulk-send")
def outbox_bulk_send(
    req_id: str | None = None,
    tier: str | None = None,
    db: Session = Depends(get_db),
):
    """Bulk-send all queued response emails. JSON response."""
    tiers = [tier] if tier else None
    return bulk_send_pending(db, req_id=req_id, tiers=tiers)

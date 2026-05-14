"""HR web dashboard views (Jinja2 rendered)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import (
    Application, JobRequisition, ScreeningSession, TriageResult, HMDecisionRecord,
)

router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(directory="src/resumetool/server/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, req_id: str | None = None, db: Session = Depends(get_db)):
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
            tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
            candidates.append({
                "application_id": app.id,
                "name": app.candidate.name or "Unknown",
                "email": app.candidate.email,
                "tier": tier,
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
        },
    )


@router.get("/candidates/{application_id}", response_class=HTMLResponse)
def candidate_detail(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Full candidate detail page for HM review."""
    app = db.get(Application, application_id)
    if not app:
        from fastapi import HTTPException
        raise HTTPException(404, "Application not found")

    result = db.query(TriageResult).filter_by(application_id=application_id).first()
    screening = db.query(ScreeningSession).filter_by(application_id=application_id).first()
    decision = db.query(HMDecisionRecord).filter_by(application_id=application_id).first()

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
        },
    )

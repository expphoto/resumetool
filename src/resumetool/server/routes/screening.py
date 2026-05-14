"""Async screening form endpoints — public (no auth required)."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import ScreeningSession
from resumetool.triage.pipeline import update_triage_with_screen_score
from resumetool.triage.screening import score_screening_answers

router = APIRouter(tags=["screening"])

templates = Jinja2Templates(directory="src/resumetool/server/templates")


@router.get("/screen/{token}", response_class=HTMLResponse)
def screening_form(token: str, request: Request, db: Session = Depends(get_db)):
    """Public screening form — candidate visits this link."""
    session = db.query(ScreeningSession).filter_by(token=token).first()
    if not session:
        raise HTTPException(404, "Screening link not found")
    if session.status.value == "completed":
        return templates.TemplateResponse(
            "screen_done.html", {"request": request, "already_done": True}
        )
    if session.expires_at and datetime.utcnow() > session.expires_at:
        session.status = "expired"
        db.commit()
        return templates.TemplateResponse(
            "screen_done.html", {"request": request, "expired": True}
        )
    return templates.TemplateResponse(
        "screen_form.html",
        {
            "request": request,
            "token": token,
            "questions": session.questions or [],
            "req_title": session.application.requisition.title,
        },
    )


@router.post("/screen/{token}", response_class=HTMLResponse)
async def submit_screening(token: str, request: Request, db: Session = Depends(get_db)):
    """Accept candidate's text answers and trigger AI scoring."""
    session = db.query(ScreeningSession).filter_by(token=token).first()
    if not session or session.status.value in ("completed", "expired"):
        raise HTTPException(400, "Screening session is no longer active")

    form = await request.form()
    answers = {q["id"]: form.get(q["id"], "") for q in (session.questions or [])}

    req_title = session.application.requisition.title
    ai_score, ai_notes = score_screening_answers(session.questions or [], answers, req_title)

    session.answers = answers
    session.ai_score = ai_score
    session.ai_score_notes = ai_notes
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()

    # Re-score composite with stage2 now available
    update_triage_with_screen_score(session.application_id, db)

    return templates.TemplateResponse(
        "screen_done.html", {"request": request, "already_done": False, "expired": False}
    )

"""Public landing page (no auth) — the marketing-facing entry point."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import (
    Application, EmailEvent, HMDecisionRecord, TriageResult, JobRequisition,
)

router = APIRouter(tags=["landing"])
templates = Jinja2Templates(directory="src/resumetool/server/templates")


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)):
    """Public landing page.

    For a quick "how big is the funnel?" callout we show a few live
    numbers from the database when it's populated; otherwise we fall
    back to the marketing illustrative numbers in the template.
    """
    stats = _live_stats(db)
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "live_stats": stats,
        },
    )


@router.get("/demo", response_class=HTMLResponse)
def demo(request: Request):
    """Guided, animated walkthrough of one full hiring cycle.

    No auth — purely a marketing / sales page. JavaScript on the page
    drives the timeline; the server just renders the shell.
    """
    return templates.TemplateResponse(
        "demo.html",
        {"request": request},
    )


def _live_stats(db: Session) -> dict:
    """Compute a small set of live numbers to render on the landing page."""
    total = db.query(Application).count()
    triaged = (
        db.query(TriageResult).filter(TriageResult.composite_score.isnot(None)).count()
    )
    emails_sent = (
        db.query(EmailEvent)
        .filter(EmailEvent.status.in_(["sent", "dry_run"]))
        .count()
    )
    decisions = db.query(HMDecisionRecord).count()
    open_reqs = (
        db.query(JobRequisition).filter_by(status="open").count()
    )
    return {
        "total_applications": total,
        "triaged": triaged,
        "emails_sent": emails_sent,
        "decisions": decisions,
        "open_reqs": open_reqs,
    }

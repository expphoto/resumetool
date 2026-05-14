"""Application intake and candidate management endpoints."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from resumetool.analysis.resume_parser import ResumeParser
from resumetool.database import get_db
from resumetool.database.models import Application, Candidate, JobRequisition, TriageResult, ScreeningSession
from resumetool.employer.models import ApplicationCreate, CandidateTierResult
from resumetool.triage.pipeline import run_triage

router = APIRouter(prefix="/api/v1", tags=["candidates"])
_parser = ResumeParser()


@router.post("/applications", status_code=202)
def submit_application(
    req_id: str = Form(...),
    candidate_email: str = Form(...),
    candidate_name: str = Form(...),
    candidate_phone: str = Form(None),
    source: str = Form("direct"),
    cover_letter: str = Form(None),
    days_since_posting: int = Form(None),
    follow_up: bool = Form(False),
    resume_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    req = db.get(JobRequisition, req_id)
    if not req:
        raise HTTPException(404, "Job requisition not found")

    # Parse resume bytes
    file_bytes = resume_file.file.read()
    filename = resume_file.filename or "resume.pdf"
    resume_text, resume_parsed = _parse_resume_bytes(file_bytes, filename)

    # Upsert candidate by email
    candidate = db.query(Candidate).filter_by(email=candidate_email).first()
    if not candidate:
        candidate = Candidate(
            id=str(uuid.uuid4()),
            email=candidate_email,
            name=candidate_name,
            phone=candidate_phone,
            resume_text=resume_text,
            resume_parsed=resume_parsed,
        )
        db.add(candidate)
    else:
        candidate.resume_text = resume_text
        candidate.resume_parsed = resume_parsed

    db.flush()

    # Prevent duplicate applications
    existing = db.query(Application).filter_by(
        req_id=req_id, candidate_id=candidate.id
    ).first()
    if existing:
        return {"application_id": existing.id, "status": "already_applied"}

    app = Application(
        id=str(uuid.uuid4()),
        req_id=req_id,
        candidate_id=candidate.id,
        source=source,
        cover_letter=cover_letter,
        application_metadata={
            "days_since_posting": days_since_posting,
            "follow_up": follow_up,
        },
    )
    db.add(app)
    db.commit()

    # Run triage synchronously (wrap with Celery in production)
    try:
        result = run_triage(app.id, db)
        return {
            "application_id": app.id,
            "status": "triaged",
            "tier": result.tier.value if hasattr(result.tier, "value") else result.tier,
            "composite_score": result.composite_score,
        }
    except Exception as exc:
        return {"application_id": app.id, "status": "pending", "error": str(exc)}


@router.get("/candidates", response_model=list[CandidateTierResult])
def list_candidates(req_id: str, db: Session = Depends(get_db)):
    """List all candidates for a requisition sorted by tier then composite score."""
    apps = db.query(Application).filter_by(req_id=req_id).all()
    results = []
    for app in apps:
        result: TriageResult = db.query(TriageResult).filter_by(application_id=app.id).first()
        screening: ScreeningSession = db.query(ScreeningSession).filter_by(application_id=app.id).first()
        if not result:
            continue
        detail = result.stage1_detail or {}
        results.append(CandidateTierResult(
            candidate_id=app.candidate_id,
            application_id=app.id,
            name=app.candidate.name,
            email=app.candidate.email,
            tier=result.tier.value if hasattr(result.tier, "value") else result.tier,
            composite_score=result.composite_score or 0.0,
            stage1_score=result.stage1_score,
            stage2_score=result.stage2_score,
            behavioral_score=result.behavioral_score,
            screen_status=screening.status.value if screening and hasattr(screening.status, "value") else (screening.status if screening else "pending"),
            top_strengths=detail.get("_top_strengths", []),
            top_gaps=detail.get("_top_gaps", []),
            routed_at=result.routed_at,
        ))
    results.sort(key=lambda r: (r.tier, -r.composite_score))
    return results


@router.get("/candidates/{application_id}")
def get_candidate_detail(application_id: str, db: Session = Depends(get_db)):
    """Full candidate detail with all stage scores and screening answers."""
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    result: TriageResult = db.query(TriageResult).filter_by(application_id=application_id).first()
    screening: ScreeningSession = db.query(ScreeningSession).filter_by(application_id=application_id).first()

    return {
        "application_id": application_id,
        "candidate": {
            "id": app.candidate.id,
            "name": app.candidate.name,
            "email": app.candidate.email,
            "phone": app.candidate.phone,
        },
        "requisition": {"id": app.req_id, "title": app.requisition.title},
        "source": app.source,
        "applied_at": app.applied_at,
        "triage": {
            "tier": result.tier.value if result and hasattr(result.tier, "value") else (result.tier if result else None),
            "composite_score": result.composite_score if result else None,
            "stage1_score": result.stage1_score if result else None,
            "stage1_detail": result.stage1_detail if result else {},
            "stage2_score": result.stage2_score if result else None,
            "behavioral_score": result.behavioral_score if result else None,
            "behavioral_detail": result.behavioral_detail if result else {},
            "response_email_preview": result.response_email_body if result else None,
        },
        "screening": {
            "status": screening.status.value if screening and hasattr(screening.status, "value") else (screening.status if screening else None),
            "questions": screening.questions if screening else [],
            "answers": screening.answers if screening else {},
            "ai_score": screening.ai_score if screening else None,
            "ai_score_notes": screening.ai_score_notes if screening else {},
        } if screening else None,
    }


def _parse_resume_bytes(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    """Parse resume bytes to (raw_text, parsed_dict)."""
    import tempfile, os
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        analysis = _parser.parse_file(tmp_path)
        return analysis.raw_text, analysis.model_dump(exclude={"raw_text"})
    except Exception:
        return file_bytes.decode("utf-8", errors="ignore"), {}
    finally:
        os.unlink(tmp_path)

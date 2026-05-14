"""Triage pipeline orchestrator — runs Stages 1-4 for one application."""
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from resumetool.analysis.resume_parser import ResumeParser
from resumetool.database.models import (
    Application, ScreeningSession, TriageResult,
)
from resumetool.employer.models import Criterion, CriterionScore
from resumetool.triage.behavioral import compute_behavioral_score
from resumetool.triage.router import assign_tier, compute_composite, generate_response_email
from resumetool.triage.scoring import score_resume_against_rubric
from resumetool.triage.screening import (
    generate_screen_token, generate_screening_questions, screen_expiry,
)

logger = logging.getLogger(__name__)


def run_triage(application_id: str, db: Session) -> TriageResult:
    """Run the full triage pipeline for one application synchronously.

    In production this would be a Celery task; the function signature is
    identical so wrapping it is trivial.
    """
    app: Application = db.get(Application, application_id)
    if not app:
        raise ValueError(f"Application {application_id} not found")

    req = app.requisition
    candidate = app.candidate
    company = req.company
    criteria = [Criterion(**c) for c in req.criteria]
    calibration = company.scoring_config.get("calibration_examples", [])

    # --- Stage 1: Rubric scoring ---
    parser = ResumeParser()
    if candidate.resume_text:
        resume = parser.parse_text(candidate.resume_text)
    else:
        logger.warning("Candidate %s has no resume text; using empty analysis", candidate.id)
        from resumetool.types import ResumeAnalysis
        resume = ResumeAnalysis(raw_text="")

    stage1_score, criterion_scores = score_resume_against_rubric(resume, criteria, calibration)
    stage1_detail = {
        cs.criterion: {"score": cs.score, "reasoning": cs.reasoning}
        for cs in criterion_scores
    }

    # --- Stage 2: Generate screen questions (scoring happens on submission) ---
    screen_token = generate_screen_token()
    questions = generate_screening_questions(
        resume, req.title, criteria, stage1_detail
    )

    screening = ScreeningSession(
        id=str(uuid.uuid4()),
        application_id=application_id,
        token=screen_token,
        questions=questions,
        answers={},
        status="sent",
        expires_at=screen_expiry(),
    )
    db.add(screening)

    # --- Stage 3: Behavioral signals ---
    meta = app.application_metadata or {}
    behavioral_score, behavioral_detail = compute_behavioral_score(
        cover_letter=app.cover_letter,
        source=app.source or "direct",
        days_since_posting=meta.get("days_since_posting"),
        follow_up=meta.get("follow_up", False),
        req_title=req.title,
    )

    # --- Stage 4: Composite score + tier routing ---
    composite = compute_composite(
        stage1_score=stage1_score,
        stage2_score=None,  # Screen not yet completed
        behavioral_score=behavioral_score,
        stage_weights=req.stage_weights or {},
    )
    tier = assign_tier(composite)

    response_email = generate_response_email(
        tier=tier,
        candidate_name=candidate.name or "",
        req_title=req.title,
        company_name=company.name,
        criterion_scores=criterion_scores,
    )

    top_strengths = [cs.criterion for cs in sorted(criterion_scores, key=lambda x: x.score, reverse=True)[:2]]
    top_gaps = [cs.criterion for cs in sorted(criterion_scores, key=lambda x: x.score)[:2] if cs.score < 0.6]

    now = datetime.utcnow()
    result = TriageResult(
        id=str(uuid.uuid4()),
        application_id=application_id,
        stage1_score=stage1_score,
        stage1_detail=stage1_detail,
        stage2_score=None,
        stage2_notes={},
        behavioral_score=behavioral_score,
        behavioral_detail=behavioral_detail,
        composite_score=composite,
        tier=tier,
        response_email_body=response_email,
        routed_at=now,
        response_sent_at=None,
    )
    # Store top strengths/gaps in stage1_detail for dashboard display
    result.stage1_detail["_top_strengths"] = top_strengths
    result.stage1_detail["_top_gaps"] = top_gaps

    db.add(result)
    db.commit()
    db.refresh(result)

    logger.info(
        "Triage complete for application %s: tier=%s composite=%.3f screen_token=%s",
        application_id, tier, composite, screen_token,
    )
    return result


def update_triage_with_screen_score(application_id: str, db: Session) -> TriageResult:
    """Re-score composite after screening answers submitted."""
    result: TriageResult = (
        db.query(TriageResult).filter_by(application_id=application_id).first()
    )
    screening: ScreeningSession = (
        db.query(ScreeningSession).filter_by(application_id=application_id).first()
    )
    if not result or not screening or screening.ai_score is None:
        return result

    req = db.get(Application, application_id).requisition
    stage_weights = req.stage_weights or {}

    composite = compute_composite(
        stage1_score=result.stage1_score,
        stage2_score=screening.ai_score,
        behavioral_score=result.behavioral_score,
        stage_weights=stage_weights,
    )
    tier = assign_tier(composite)

    result.stage2_score = screening.ai_score
    result.stage2_notes = screening.ai_score_notes or {}
    result.composite_score = composite
    result.tier = tier
    db.commit()
    db.refresh(result)

    logger.info(
        "Triage updated after screen for application %s: tier=%s composite=%.3f",
        application_id, tier, composite,
    )
    return result

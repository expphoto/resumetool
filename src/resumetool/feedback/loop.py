"""Stage 5: Feedback loop — store HM decisions and calibrate per-company scoring prompts."""
import logging
from sqlalchemy.orm import Session

from resumetool.database.models import Company, HMDecisionRecord, TriageResult, Application

logger = logging.getLogger(__name__)

MIN_DECISIONS_FOR_CALIBRATION = 10


def record_decision(
    application_id: str,
    decision: str,
    notes: str | None,
    db: Session,
) -> HMDecisionRecord:
    """Persist a hiring manager decision and trigger calibration if threshold met."""
    import uuid
    record = HMDecisionRecord(
        id=str(uuid.uuid4()),
        application_id=application_id,
        decision=decision,
        notes=notes,
    )
    db.add(record)
    db.commit()

    app = db.get(Application, application_id)
    company_id = app.requisition.company_id
    _maybe_calibrate(company_id, db)

    return record


def _maybe_calibrate(company_id: str, db: Session) -> None:
    """If we have enough decisions, rebuild the company's calibration examples."""
    decisions = (
        db.query(HMDecisionRecord)
        .join(Application, HMDecisionRecord.application_id == Application.id)
        .join(Application.requisition)
        .filter_by(company_id=company_id)
        .all()
    )

    if len(decisions) < MIN_DECISIONS_FOR_CALIBRATION:
        logger.debug(
            "Company %s has %d decisions, need %d for calibration",
            company_id, len(decisions), MIN_DECISIONS_FOR_CALIBRATION,
        )
        return

    examples = _build_calibration_examples(decisions, db)
    company: Company = db.get(Company, company_id)
    if not company:
        return

    company.scoring_config = {"calibration_examples": examples}
    db.commit()
    logger.info("Calibrated company %s with %d examples", company_id, len(examples))


def _build_calibration_examples(decisions: list[HMDecisionRecord], db: Session) -> list[dict]:
    """Build few-shot examples from HM decisions joined with resume and triage data.

    Each example: {criterion, resume_snippet, score, hm_decision}
    """
    examples = []
    for decision in decisions[-50:]:  # Use most recent 50 decisions
        app = db.get(Application, decision.application_id)
        if not app:
            continue
        result: TriageResult = (
            db.query(TriageResult).filter_by(application_id=decision.application_id).first()
        )
        if not result or not result.stage1_detail:
            continue

        candidate = app.candidate
        resume_snippet = _resume_snippet(candidate.resume_parsed or {})

        # One example per criterion from this decision
        for criterion_name, detail in result.stage1_detail.items():
            if criterion_name.startswith("_"):
                continue
            if not isinstance(detail, dict):
                continue
            examples.append({
                "criterion": criterion_name,
                "resume_snippet": resume_snippet,
                "score": detail.get("score", "?"),
                "hm_decision": decision.decision,
            })

    return examples


def _resume_snippet(resume_parsed: dict) -> str:
    """Extract a short identifying snippet from a parsed resume dict."""
    parts = []
    if resume_parsed.get("title"):
        parts.append(resume_parsed["title"])
    if resume_parsed.get("skills"):
        skill_names = [s.get("name", "") for s in resume_parsed["skills"][:5]]
        parts.append(", ".join(filter(None, skill_names)))
    if resume_parsed.get("experience"):
        exp = resume_parsed["experience"][0]
        parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}")
    return " | ".join(parts)[:200]

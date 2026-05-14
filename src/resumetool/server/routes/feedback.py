"""HM decision capture and analytics endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import Application, HMDecisionRecord, TriageResult
from resumetool.employer.models import HMDecisionCreate
from resumetool.feedback.loop import record_decision

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback/{application_id}", status_code=201)
def submit_decision(
    application_id: str,
    payload: HMDecisionCreate,
    db: Session = Depends(get_db),
):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")

    record = record_decision(
        application_id=application_id,
        decision=payload.decision,
        notes=payload.notes,
        db=db,
    )
    return {"id": record.id, "decision": record.decision, "decided_at": record.decided_at}


@router.get("/analytics")
def get_analytics(company_id: str, db: Session = Depends(get_db)):
    """Tier distribution and calibration stats for a company."""
    from resumetool.database.models import JobRequisition
    reqs = db.query(JobRequisition).filter_by(company_id=company_id).all()
    req_ids = [r.id for r in reqs]

    apps = db.query(Application).filter(Application.req_id.in_(req_ids)).all()
    app_ids = [a.id for a in apps]

    results = db.query(TriageResult).filter(TriageResult.application_id.in_(app_ids)).all()
    decisions = db.query(HMDecisionRecord).filter(HMDecisionRecord.application_id.in_(app_ids)).all()

    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        t = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    decision_counts = {"interview": 0, "hold": 0, "reject": 0}
    for d in decisions:
        dec = d.decision.value if hasattr(d.decision, "value") else str(d.decision)
        decision_counts[dec] = decision_counts.get(dec, 0) + 1

    # Compute HM-vs-tier accuracy: what % of HM interviews came from Tier A/B?
    interviewed_apps = {d.application_id for d in decisions if str(d.decision) in ("interview", "interview")}
    tier_ab_apps = {r.application_id for r in results if str(r.tier) in ("A", "B", "TierEnum.A", "TierEnum.B")}
    accuracy = (
        len(interviewed_apps & tier_ab_apps) / len(interviewed_apps)
        if interviewed_apps else None
    )

    from resumetool.database.models import Company
    company = db.get(Company, company_id)
    calibration_count = len((company.scoring_config or {}).get("calibration_examples", []))

    return {
        "total_applications": len(apps),
        "tier_distribution": tier_counts,
        "hm_decisions": decision_counts,
        "tier_accuracy": round(accuracy, 3) if accuracy is not None else None,
        "calibration_examples": calibration_count,
        "calibrated": calibration_count > 0,
    }

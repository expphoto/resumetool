"""Job requisition CRUD endpoints."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from resumetool.database import get_db
from resumetool.database.models import Company, JobRequisition
from resumetool.employer.models import JobRequisitionCreate, JobRequisitionRead

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/", response_model=JobRequisitionRead, status_code=201)
def create_requisition(payload: JobRequisitionCreate, db: Session = Depends(get_db)):
    # Auto-create company if it doesn't exist
    company = db.get(Company, payload.company_id)
    if not company:
        company = Company(id=payload.company_id, name=payload.company_id)
        db.add(company)

    req = JobRequisition(
        id=str(uuid.uuid4()),
        company_id=payload.company_id,
        title=payload.title,
        description=payload.description,
        criteria=[c.model_dump() for c in payload.rubric.criteria],
        stage_weights=payload.stage_weights,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_read(req)


@router.get("/", response_model=list[JobRequisitionRead])
def list_requisitions(company_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(JobRequisition)
    if company_id:
        q = q.filter_by(company_id=company_id)
    return [_to_read(r) for r in q.all()]


@router.get("/{req_id}", response_model=JobRequisitionRead)
def get_requisition(req_id: str, db: Session = Depends(get_db)):
    req = db.get(JobRequisition, req_id)
    if not req:
        raise HTTPException(404, "Requisition not found")
    return _to_read(req)


@router.patch("/{req_id}/close", response_model=JobRequisitionRead)
def close_requisition(req_id: str, db: Session = Depends(get_db)):
    req = db.get(JobRequisition, req_id)
    if not req:
        raise HTTPException(404, "Requisition not found")
    req.status = "closed"
    db.commit()
    db.refresh(req)
    return _to_read(req)


def _to_read(req: JobRequisition) -> JobRequisitionRead:
    from resumetool.employer.models import Criterion
    return JobRequisitionRead(
        id=req.id,
        company_id=req.company_id,
        title=req.title,
        description=req.description,
        status=req.status.value if hasattr(req.status, "value") else req.status,
        criteria=[Criterion(**c) for c in (req.criteria or [])],
        stage_weights=req.stage_weights or {},
        created_at=req.created_at,
    )

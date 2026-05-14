"""Employer-side Pydantic models for job requisitions and triage results."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Criterion(BaseModel):
    """A single dimension of the scoring rubric with weight."""
    name: str
    description: str
    weight: float = Field(gt=0.0, le=1.0)
    examples_good: list[str] = []
    examples_bad: list[str] = []


class ScoringRubric(BaseModel):
    """Weighted rubric of criteria for a job requisition."""
    criteria: list[Criterion]

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ScoringRubric":
        total = sum(c.weight for c in self.criteria)
        if not (0.98 <= total <= 1.02):
            raise ValueError(f"Criterion weights must sum to 1.0 (got {total:.2f})")
        return self


class JobRequisitionCreate(BaseModel):
    """Payload to create a new job requisition."""
    company_id: str
    title: str
    description: str
    rubric: ScoringRubric
    stage_weights: dict[str, float] = Field(
        default_factory=lambda: {"stage1": 0.50, "stage2": 0.35, "behavioral": 0.15}
    )


class JobRequisitionRead(BaseModel):
    """Full job requisition returned from API."""
    id: str
    company_id: str
    title: str
    description: str
    status: Literal["open", "closed"]
    criteria: list[Criterion]
    stage_weights: dict[str, float]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    """Payload to submit an application (resume uploaded separately)."""
    req_id: str
    candidate_email: str
    candidate_name: str
    candidate_phone: Optional[str] = None
    source: str = "direct"
    cover_letter: Optional[str] = None
    days_since_posting: Optional[int] = None
    follow_up: bool = False


class CriterionScore(BaseModel):
    """AI score for a single rubric criterion."""
    criterion: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class CandidateTierResult(BaseModel):
    """Summary row shown in the HR candidate list."""
    candidate_id: str
    application_id: str
    name: Optional[str]
    email: str
    tier: Literal["A", "B", "C", "D"]
    composite_score: float
    stage1_score: Optional[float]
    stage2_score: Optional[float]
    behavioral_score: Optional[float]
    screen_status: Literal["pending", "sent", "completed", "expired"]
    top_strengths: list[str] = []
    top_gaps: list[str] = []
    routed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class HMDecisionCreate(BaseModel):
    """Hiring manager decision on a candidate."""
    decision: Literal["interview", "hold", "reject"]
    notes: Optional[str] = None

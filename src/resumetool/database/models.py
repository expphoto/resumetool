"""SQLAlchemy ORM models for the hiring triage system."""
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Text, JSON, ForeignKey,
    Enum as SAEnum, Boolean,
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class TierEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ReqStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class ScreenStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    completed = "completed"
    expired = "expired"


class HMDecision(str, enum.Enum):
    interview = "interview"
    hold = "hold"
    reject = "reject"


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Stores few-shot calibration examples after feedback loop runs
    scoring_config = Column(JSON, default=dict)

    requisitions = relationship("JobRequisition", back_populates="company")


class JobRequisition(Base):
    __tablename__ = "job_requisitions"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SAEnum(ReqStatus), default=ReqStatus.open)
    # JSON list of Criterion dicts: {name, description, weight, examples_good, examples_bad}
    criteria = Column(JSON, default=list)
    # Composite score weights for this req
    stage_weights = Column(JSON, default=lambda: {"stage1": 0.50, "stage2": 0.35, "behavioral": 0.15})
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="requisitions")
    applications = relationship("Application", back_populates="requisition")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    name = Column(String)
    phone = Column(String)
    resume_text = Column(Text)
    # Parsed ResumeAnalysis as JSON
    resume_parsed = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="candidate")


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True)
    req_id = Column(String, ForeignKey("job_requisitions.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    # e.g. "referral", "indeed", "linkedin", "direct"
    source = Column(String, default="direct")
    cover_letter = Column(Text)
    # Extra signals: {"follow_up": bool, "days_since_posting": int}
    application_metadata = Column(JSON, default=dict)

    requisition = relationship("JobRequisition", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    triage_result = relationship("TriageResult", back_populates="application", uselist=False)
    screening_session = relationship("ScreeningSession", back_populates="application", uselist=False)
    hm_decision = relationship("HMDecisionRecord", back_populates="application", uselist=False)


class TriageResult(Base):
    __tablename__ = "triage_results"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, unique=True)
    stage1_score = Column(Float)
    # Per-criterion breakdown: {criterion_name: {score, reasoning}}
    stage1_detail = Column(JSON, default=dict)
    stage2_score = Column(Float)
    stage2_notes = Column(JSON, default=dict)
    behavioral_score = Column(Float)
    behavioral_detail = Column(JSON, default=dict)
    composite_score = Column(Float)
    tier = Column(SAEnum(TierEnum))
    # The tier-specific response email body generated
    response_email_body = Column(Text)
    routed_at = Column(DateTime)
    response_sent_at = Column(DateTime)

    application = relationship("Application", back_populates="triage_result")


class ScreeningSession(Base):
    __tablename__ = "screening_sessions"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, unique=True)
    # URL-safe token for the public screen link
    token = Column(String, nullable=False, unique=True)
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=dict)
    ai_score = Column(Float)
    ai_score_notes = Column(JSON, default=dict)
    status = Column(SAEnum(ScreenStatus), default=ScreenStatus.pending)
    expires_at = Column(DateTime)
    completed_at = Column(DateTime)

    application = relationship("Application", back_populates="screening_session")


class HMDecisionRecord(Base):
    __tablename__ = "hm_decisions"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, unique=True)
    decision = Column(SAEnum(HMDecision), nullable=False)
    notes = Column(Text)
    decided_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="hm_decision")

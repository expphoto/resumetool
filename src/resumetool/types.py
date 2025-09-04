"""Core types and data models for AI job matching system."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SkillLevel(str, Enum):
    """Skill proficiency levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"  
    ADVANCED = "advanced"
    EXPERT = "expert"


class ApplicationStatus(str, Enum):
    """Job application status."""
    SAVED = "saved"
    APPLIED = "applied" 
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    OFFERED = "offered"


class Skill(BaseModel):
    """Individual skill with proficiency level."""
    name: str
    level: SkillLevel
    years_experience: Optional[int] = None
    category: Optional[str] = None  # e.g., "programming", "design", "management"


class Experience(BaseModel):
    """Work experience entry."""
    title: str
    company: str
    duration: str  # e.g., "2 years", "Jan 2020 - Dec 2022"
    description: str
    key_achievements: List[str] = []
    skills_used: List[str] = []


class ResumeAnalysis(BaseModel):
    """Complete analysis of a resume."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    skills: List[Skill] = []
    experience: List[Experience] = []
    education: List[str] = []
    certifications: List[str] = []
    raw_text: str
    metadata: Dict[str, Any] = {}


class JobListing(BaseModel):
    """Job listing from job boards."""
    id: str
    title: str
    company: str
    location: str
    remote: bool = False
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: str
    requirements: List[str] = []
    preferred_skills: List[str] = []
    posted_date: Optional[datetime] = None
    source: str  # "indeed", "ziprecruiter", etc.
    url: str
    
    
class JobMatch(BaseModel):
    """Job match result with scoring."""
    job: JobListing
    match_score: float = Field(ge=0.0, le=1.0)
    skill_match_score: float = Field(ge=0.0, le=1.0)
    experience_match_score: float = Field(ge=0.0, le=1.0)
    missing_skills: List[str] = []
    matching_skills: List[str] = []
    experience_gaps: List[str] = []
    recommendations: List[str] = []


class OptimizedResume(BaseModel):
    """Optimized resume version for specific job."""
    job_id: str
    original_resume_id: str
    optimized_content: str
    key_changes: List[str] = []
    ats_score: Optional[float] = None
    format: str = "docx"  # docx, pdf, html
    created_at: datetime = Field(default_factory=datetime.now)


class JobApplication(BaseModel):
    """Job application tracking."""
    id: str
    job: JobListing
    resume_version: OptimizedResume
    status: ApplicationStatus = ApplicationStatus.SAVED
    applied_date: Optional[datetime] = None
    notes: List[str] = []
    follow_up_date: Optional[datetime] = None


# Legacy types for compatibility
class JobExperience(BaseModel):
    """Legacy job experience type."""
    company: str
    title: str
    duration: str
    bullet_points: List[str]


class Resume(BaseModel):
    """Legacy resume type."""
    full_name: Optional[str] = Field(default=None, description="May be redacted.")
    contact_info_redacted: bool = True
    summary: Optional[str] = None
    skills: List[str] = []
    experience: List[JobExperience] = []


class JobDescription(BaseModel):
    """Legacy job description type."""
    title: Optional[str] = None
    company: Optional[str] = None
    text: str


class MatchResult(BaseModel):
    """Legacy match result type."""
    score: float
    missing_keywords: List[str] = []
    notes: Optional[str] = None
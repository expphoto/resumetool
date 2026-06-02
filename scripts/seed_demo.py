"""Demo data seeder for the HR triage portal.

Populates the database with one company, one open job requisition, and a
configurable number of synthetic candidates spread across the four tiers.
Runs the full triage pipeline offline (no OpenAI key required) and pushes
some emails through the outbox so the portal shows a realistic "we
processed 500 resumes" story.

Usage:
    python -m scripts.seed_demo              # 50 candidates (default)
    python -m scripts.seed_demo --count 200  # 200 candidates
    python -m scripts.seed_demo --reset      # wipe DB first
    python -m scripts.seed_demo --send       # also send outbox emails (dry-run by default)
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Make `src/` importable when invoked as `python scripts/seed_demo.py`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from resumetool.config import settings  # noqa: E402
from resumetool.database.models import (  # noqa: E402
    Application, Candidate, Company, EmailEvent, HMDecision, HMDecisionRecord,
    JobRequisition, ScreeningSession, TriageResult,
)
from resumetool.database.session import SessionLocal, engine  # noqa: E402
from resumetool.database.models import Base  # noqa: E402
from resumetool.employer.models import Criterion  # noqa: E402
from resumetool.notifications.mailer import bulk_send_pending  # noqa: E402
from resumetool.triage.pipeline import run_triage  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_demo")

# --- Demo data -------------------------------------------------------------

COMPANY_ID = "demo-co"
COMPANY_NAME = "Acme Talent Co."

REQ_ID = "demo-req-001"
REQ_TITLE = "Senior Cloud Platform Engineer"
REQ_DESCRIPTION = (
    "Lead our Kubernetes platform team. You'll design and operate multi-tenant "
    "Kubernetes clusters on AWS, improve our CI/CD pipelines, and mentor junior "
    "engineers."
)
REQ_CRITERIA = [
    Criterion(name="Kubernetes depth", description="Production K8s operator/developer experience", weight=0.30),
    Criterion(name="AWS expertise", description="VPC, EC2, EKS, IAM, Terraform", weight=0.20),
    Criterion(name="Coding (Python/Go)", description="Strong in Python and/or Go", weight=0.20),
    Criterion(name="Communication & mentoring", description="Can review designs and mentor juniors", weight=0.15),
    Criterion(name="Production track record", description="Has run large production systems", weight=0.15),
]
STAGE_WEIGHTS = {"stage1": 0.50, "stage2": 0.35, "behavioral": 0.15}

FIRST_NAMES = [
    "Sarah", "Marcus", "Priya", "Alex", "Diego", "Wei", "Jamal", "Hannah",
    "Liam", "Aisha", "Noah", "Mei", "Diego", "Yuki", "Carlos", "Riya",
    "Tomás", "Zara", "Felix", "Ines", "Ravi", "Olivia", "Bilal", "Nadia",
    "Owen", "Saanvi", "Ethan", "Anya", "Theo", "Leila",
]
LAST_NAMES = [
    "Patel", "Kim", "Nguyen", "Garcia", "Johnson", "Lee", "Ahmed", "Müller",
    "Rossi", "Silva", "Khan", "O'Connor", "Mendez", "Park", "Singh", "Brown",
    "Hernandez", "Tanaka", "Ali", "Cohen", "Petrov", "Kowalski", "Yusuf",
    "Williams", "Lopez", "Diaz", "Nakamura", "Andersen", "Volkov", "Sato",
]
SOURCES = ["linkedin", "indeed", "referral", "direct", "ziprecruiter"]

# Skill mixes per "tier" to keep the offline triage deterministic & believable
TIER_PROFILES = {
    "A": {
        "skills": ["Kubernetes", "AWS", "Python", "Go", "PostgreSQL", "Terraform", "Docker"],
        "title": "Staff Platform Engineer",
        "years": "8+",
    },
    "B": {
        "skills": ["Kubernetes", "AWS", "Python", "Docker", "PostgreSQL"],
        "title": "Senior Software Engineer",
        "years": "5-7",
    },
    "C": {
        "skills": ["Python", "AWS", "Docker"],
        "title": "Software Engineer",
        "years": "3-4",
    },
    "D": {
        "skills": ["Java", "Excel"],
        "title": "Junior Developer",
        "years": "0-1",
    },
}


def _make_resume_text(name: str, tier: str) -> str:
    """Build a plausible resume text for a given tier."""
    p = TIER_PROFILES[tier]
    skill_line = "Skills: " + ", ".join(p["skills"])
    cover_letter = (
        f"Hi Acme team — I'm excited about the {REQ_TITLE} role. "
        f"I've spent the last {p['years']} years working with "
        f"{', '.join(p['skills'][:3])} and I'd love to bring that experience "
        "to your platform team."
    ) if random.random() < 0.6 else None
    body = (
        f"{name}\n"
        f"{p['title']} with {p['years']} years of experience.\n\n"
        f"Summary\n{'-' * 30}\nExperienced engineer with deep hands-on work in "
        f"{', '.join(p['skills'][:3])}.\n\n"
        f"{skill_line}\n\n"
        f"Experience\n{'-' * 30}\n"
        f"{p['title']} at RecentCo — 2020 - present\n"
        f"- Led migration projects using {p['skills'][0]}\n"
        f"- Improved system reliability and on-call processes\n"
        f"- Mentored junior team members\n\n"
        f"Education\n{'-' * 30}\nB.S. Computer Science, State University, 2018\n"
    )
    if cover_letter:
        body += f"\nCover Letter\n{'-' * 30}\n{cover_letter}\n"
    return body


def _seed_company(db) -> Company:
    company = db.get(Company, COMPANY_ID)
    if not company:
        company = Company(id=COMPANY_ID, name=COMPANY_NAME)
        db.add(company)
        db.commit()
    return company


def _seed_req(db) -> JobRequisition:
    req = db.get(JobRequisition, REQ_ID)
    criteria_dicts = [c.model_dump() for c in REQ_CRITERIA]
    if not req:
        req = JobRequisition(
            id=REQ_ID,
            company_id=COMPANY_ID,
            title=REQ_TITLE,
            description=REQ_DESCRIPTION,
            status="open",
            criteria=criteria_dicts,
            stage_weights=STAGE_WEIGHTS,
        )
        db.add(req)
        db.commit()
    else:
        req.criteria = criteria_dicts
        req.stage_weights = STAGE_WEIGHTS
        db.commit()
    return req


def _reset(db) -> None:
    """Wipe all application data (keep schema)."""
    logger.info("Resetting demo data…")
    for model in (
        HMDecisionRecord, EmailEvent, ScreeningSession, TriageResult,
        Application, Candidate, JobRequisition, Company,
    ):
        db.query(model).delete()
    db.commit()


def _create_candidate(db, tier: str, index: int) -> Candidate:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    # Use a short uuid suffix so emails are unique even with a fixed seed.
    email = f"{first.lower()}.{last.lower()}.{uuid.uuid4().hex[:6]}@example.com"
    candidate = Candidate(
        id=str(uuid.uuid4()),
        email=email,
        name=name,
        phone=f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
        resume_text=_make_resume_text(name, tier),
        resume_parsed={},
    )
    db.add(candidate)
    db.commit()
    return candidate


def _create_application(db, candidate: Candidate, req: JobRequisition, tier: str) -> Application:
    days_ago = random.randint(0, 14)
    source = random.choice(SOURCES)
    cover_letter = (
        f"Hi team, I'm very interested in the {REQ_TITLE} role. "
        f"See attached for my background."
    ) if random.random() < 0.5 else None
    app = Application(
        id=str(uuid.uuid4()),
        req_id=req.id,
        candidate_id=candidate.id,
        applied_at=datetime.utcnow() - timedelta(days=days_ago),
        source=source,
        cover_letter=cover_letter,
        application_metadata={
            "days_since_posting": days_ago,
            "follow_up": random.random() < 0.1,
        },
    )
    db.add(app)
    db.commit()
    return app


def _post_triage_hooks(db, app: Application, tier: str) -> None:
    """For some apps, simulate completed screening and HM decisions."""
    if tier in ("B", "C") and random.random() < 0.5:
        # Simulate a completed screen
        session = (
            db.query(ScreeningSession).filter_by(application_id=app.id).first()
        )
        if session:
            from datetime import datetime as _dt
            session.answers = {
                "q1": "I led a multi-region K8s rollout and reduced incidents by 40%.",
                "q2": "I mentor 2-3 juniors a year; reviews are part of my weekly cadence.",
                "q3": "Python and Go daily; comfortable in TypeScript when needed.",
            }
            session.ai_score = 0.55 + (0.20 if tier == "B" else 0.05) + random.uniform(-0.1, 0.1)
            session.status = "completed"
            session.completed_at = _dt.utcnow()
            db.commit()
            from resumetool.triage.pipeline import update_triage_with_screen_score
            update_triage_with_screen_score(app.id, db)

    if tier in ("A", "B") and random.random() < 0.4:
        # Simulate an HM decision
        decision = HMDecision.interview if tier == "A" else random.choice([HMDecision.hold, HMDecision.interview])
        record = HMDecisionRecord(
            id=str(uuid.uuid4()),
            application_id=app.id,
            decision=decision,
            notes="Strong screen; pushing to onsite." if decision == HMDecision.interview else None,
        )
        db.add(record)
        db.commit()


def _tier_distribution(n: int) -> dict[str, int]:
    """Default 500-resume style distribution scaled to n candidates."""
    return {
        "A": max(1, round(n * 0.05)),
        "B": max(1, round(n * 0.15)),
        "C": max(1, round(n * 0.40)),
        "D": max(1, n - round(n * 0.05) - round(n * 0.15) - round(n * 0.40)),
    }


def seed(count: int = 50, reset: bool = False, send: bool = False) -> dict:
    """Run the full seed. Returns a small stats dict."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if reset:
            _reset(db)
        _seed_company(db)
        req = _seed_req(db)

        # If we already have candidates, just report the current state
        existing_apps = db.query(Application).count()
        if existing_apps and not reset:
            logger.info("DB already has %d applications. Pass --reset to wipe.", existing_apps)
            return _stats(db)

        dist = _tier_distribution(count)
        logger.info("Seeding %d candidates: %s", count, dist)
        random.seed(42)  # reproducible demos

        created = 0
        for tier, n in dist.items():
            for i in range(n):
                try:
                    cand = _create_candidate(db, tier, index=created)
                    app = _create_application(db, cand, req, tier)
                    # Run the offline triage pipeline
                    run_triage(app.id, db)
                    _post_triage_hooks(db, app, tier)
                    created += 1
                except Exception as exc:
                    logger.warning("Failed to seed %s #%d: %s", tier, i, exc)
                    db.rollback()
        db.commit()

        if send:
            logger.info("Sending all queued response emails (dry-run)…")
            send_stats = bulk_send_pending(db, req_id=req.id, force_dry_run=True)
            logger.info("Outbox: %s", send_stats)
        else:
            send_stats = None

        return _stats(db, send_stats=send_stats)
    finally:
        db.close()


def _stats(db, send_stats: dict | None = None) -> dict:
    from resumetool.database.models import TriageResult
    apps = db.query(Application).count()
    results = db.query(TriageResult).all()
    by_tier = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        t = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        by_tier[t] = by_tier.get(t, 0) + 1
    return {
        "applications": apps,
        "by_tier": by_tier,
        "send_stats": send_stats,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Seed the ResumeTool portal with demo data")
    p.add_argument("--count", type=int, default=50, help="Number of candidates to seed (default: 50)")
    p.add_argument("--reset", action="store_true", help="Wipe all existing data first")
    p.add_argument("--send", action="store_true", help="Also run bulk dry-run email send")
    args = p.parse_args()

    stats = seed(count=args.count, reset=args.reset, send=args.send)
    print()
    print("=" * 50)
    print("Seeding complete.")
    print(f"  Applications: {stats['applications']}")
    print(f"  By tier:      {stats['by_tier']}")
    if stats.get("send_stats"):
        print(f"  Outbox:       {stats['send_stats']}")
    print()
    print("Open the portal:")
    print(f"  {settings.database_url}")
    print("  python -m uvicorn resumetool.server.app:app --reload")
    print("Login with: admin / changeme (or whatever you set RESUMETOOL_HR_AUTH_USERS to)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Tests for the demo data seeder script.

Runs the seeder against a throwaway DB and asserts that it produces a
realistic mix of candidates across the four tiers and that bulk-send
queues (or marks sent) the response emails.
"""
import os
import subprocess
import sys
from pathlib import Path



REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "seed_demo.py"


def _run_seeder(env_overrides: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_seeder_creates_diverse_tier_mix(tmp_path):
    db_path = tmp_path / "seed.db"
    env = {
        "RESUMETOOL_DATABASE_URL": f"sqlite:///{db_path}",
        "RESUMETOOL_DRY_RUN_EMAIL": "true",
    }
    res = _run_seeder(env, "--count", "50", "--reset")
    assert res.returncode == 0, res.stderr

    # Now query the DB directly to confirm the distribution
    # Re-import to pick up the new env
    sys.path.insert(0, str(REPO_ROOT / "src"))
    # The seeder process populated the DB; just import the models to read it
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from resumetool.database.models import Application, TriageResult

    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        apps = db.query(Application).count()
        assert apps == 50

        results = db.query(TriageResult).all()
        by_tier: dict[str, int] = {}
        for r in results:
            t = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
            by_tier[t] = by_tier.get(t, 0) + 1
        # Default distribution: ~5% A, ~15% B, ~40% C, ~40% D
        assert by_tier.get("A", 0) >= 1
        assert by_tier.get("D", 0) >= 1
        # Sanity: no tier should be empty
        for tier in "ABCD":
            assert tier in by_tier, f"tier {tier} is missing"
    finally:
        db.close()


def test_seeder_send_flag_marks_emails_sent(tmp_path):
    db_path = tmp_path / "seed_send.db"
    env = {
        "RESUMETOOL_DATABASE_URL": f"sqlite:///{db_path}",
        "RESUMETOOL_DRY_RUN_EMAIL": "true",
    }
    res = _run_seeder(env, "--count", "20", "--reset", "--send")
    assert res.returncode == 0, res.stderr

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from resumetool.database.models import EmailEvent, TriageResult

    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # All triage results should have response_sent_at set
        triages = db.query(TriageResult).all()
        assert triages
        for t in triages:
            assert t.response_sent_at is not None, f"triage {t.id} missing response_sent_at"
        # EmailEvent rows should exist
        events = db.query(EmailEvent).all()
        assert len(events) == 20
        for e in events:
            assert e.status == "dry_run"
    finally:
        db.close()


def test_seeder_reset_wipes_data(tmp_path):
    db_path = tmp_path / "seed_reset.db"
    env = {
        "RESUMETOOL_DATABASE_URL": f"sqlite:///{db_path}",
        "RESUMETOOL_DRY_RUN_EMAIL": "true",
    }
    # First run: populate
    res1 = _run_seeder(env, "--count", "20", "--reset")
    assert res1.returncode == 0, res1.stderr
    # Second run: detect existing data, no reset
    res2 = _run_seeder(env, "--count", "20")
    assert res2.returncode == 0
    assert "already has" in res2.stderr or "DB already has" in res2.stderr

"""Stage 2: Async text-based AI screening — question generation and answer scoring."""
import json
import logging
import secrets
from datetime import datetime, timedelta

from openai import OpenAI

from resumetool.config import settings
from resumetool.employer.models import Criterion
from resumetool.types import ResumeAnalysis

logger = logging.getLogger(__name__)

SCREEN_EXPIRY_DAYS = 5


def generate_screen_token() -> str:
    return secrets.token_urlsafe(32)


def generate_screening_questions(
    resume: ResumeAnalysis,
    req_title: str,
    criteria: list[Criterion],
    stage1_detail: dict,
) -> list[dict]:
    """Generate 5-7 targeted questions based on rubric gaps from Stage 1.

    Returns list of {id, question, criterion, context} dicts.
    """
    client = OpenAI(api_key=settings.openai_api_key)

    gaps = _identify_gaps(stage1_detail, criteria)
    gap_text = "\n".join(f"- {g}" for g in gaps) if gaps else "No major gaps identified."

    candidate_title = resume.title or "the candidate"
    skills_str = ", ".join(s.name for s in resume.skills[:15])

    system = (
        "You are a skilled technical recruiter conducting an asynchronous text screen. "
        "Generate targeted questions that reveal whether a candidate can actually do this job. "
        "Focus on specific gaps and verify claimed experience. "
        'Return ONLY valid JSON: {"questions": [{"id": "q1", "question": "...", "criterion": "...", "what_good_looks_like": "..."}]}'
    )

    user = f"""ROLE: {req_title}
CANDIDATE: {candidate_title}, skills include {skills_str}

SCORING GAPS TO PROBE:
{gap_text}

ALL RUBRIC CRITERIA:
{chr(10).join(f"- {c.name}: {c.description}" for c in criteria)}

Generate 5-7 questions. Mix behavioral (tell me about a time...), situational (how would you handle...), and skill-verification questions. Keep each question under 60 words."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        questions = data.get("questions", [])
        for i, q in enumerate(questions):
            q.setdefault("id", f"q{i + 1}")
        return questions[:7]
    except Exception as exc:
        logger.warning("Question generation failed: %s", exc)
        return _fallback_questions(criteria)


def score_screening_answers(
    questions: list[dict],
    answers: dict[str, str],
    req_title: str,
) -> tuple[float, dict]:
    """Score a candidate's text answers. Returns (score 0-1, notes dict)."""
    client = OpenAI(api_key=settings.openai_api_key)

    qa_pairs = []
    for q in questions:
        qid = q.get("id", "")
        answer = answers.get(qid, "").strip()
        qa_pairs.append({
            "question": q.get("question", ""),
            "what_good_looks_like": q.get("what_good_looks_like", ""),
            "answer": answer or "(no answer provided)",
        })

    system = (
        "You are a recruiter evaluating async screening answers for a job role. "
        "Score overall answer quality and provide brief notes per question. "
        'Return ONLY valid JSON: {"overall_score": <0.0-1.0>, "notes": {"q1": "...", "q2": "..."}, "summary": "..."}'
    )

    user = f"""ROLE: {req_title}

Q&A PAIRS:
{json.dumps(qa_pairs, indent=2)}

Score 0.0 if answers are evasive/thin/irrelevant, 1.0 if answers demonstrate strong competency with specific examples."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        score = max(0.0, min(1.0, float(data.get("overall_score", 0.5))))
        notes = {"notes": data.get("notes", {}), "summary": data.get("summary", "")}
        return score, notes
    except Exception as exc:
        logger.warning("Answer scoring failed: %s", exc)
        return 0.5, {"summary": "Scoring unavailable", "notes": {}}


def screen_expiry() -> datetime:
    return datetime.utcnow() + timedelta(days=SCREEN_EXPIRY_DAYS)


def _identify_gaps(stage1_detail: dict, criteria: list[Criterion]) -> list[str]:
    """Return criteria names where score was below 0.6."""
    gaps = []
    for criterion in criteria:
        detail = stage1_detail.get(criterion.name, {})
        score = detail.get("score", 1.0) if isinstance(detail, dict) else 1.0
        if score < 0.6:
            gaps.append(f"{criterion.name} (score: {score:.2f}) — {criterion.description}")
    return gaps


def _fallback_questions(criteria: list[Criterion]) -> list[dict]:
    questions = []
    for i, c in enumerate(criteria[:5]):
        questions.append({
            "id": f"q{i + 1}",
            "question": f"Describe your experience with {c.name}. Please give a specific example.",
            "criterion": c.name,
            "what_good_looks_like": c.description,
        })
    return questions

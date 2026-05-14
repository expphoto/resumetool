"""Stage 1: Rubric-based resume-to-JD scoring."""
import json
import logging
from typing import Any

from openai import OpenAI

from resumetool.config import settings
from resumetool.employer.models import Criterion, CriterionScore
from resumetool.types import ResumeAnalysis

logger = logging.getLogger(__name__)


def score_resume_against_rubric(
    resume: ResumeAnalysis,
    criteria: list[Criterion],
    calibration_examples: list[dict[str, Any]] | None = None,
) -> tuple[float, list[CriterionScore]]:
    """Score a parsed resume against each rubric criterion.

    Returns (weighted_score, per_criterion_scores).
    """
    client = OpenAI(api_key=settings.openai_api_key)

    per_scores: list[CriterionScore] = []
    for criterion in criteria:
        score, reasoning = _score_criterion(client, resume, criterion, calibration_examples or [])
        per_scores.append(CriterionScore(criterion=criterion.name, score=score, reasoning=reasoning))

    weighted = sum(cs.score * c.weight for cs, c in zip(per_scores, criteria))
    return round(weighted, 4), per_scores


def _score_criterion(
    client: OpenAI,
    resume: ResumeAnalysis,
    criterion: Criterion,
    calibration_examples: list[dict[str, Any]],
) -> tuple[float, str]:
    """Ask the AI to score one criterion. Returns (score 0-1, reasoning)."""
    resume_summary = _build_resume_summary(resume)
    few_shot = _build_few_shot_block(calibration_examples, criterion.name)

    system = (
        "You are an expert technical recruiter. Score how well a candidate's resume "
        "meets a specific job criterion. Return ONLY valid JSON: "
        '{"score": <float 0.0-1.0>, "reasoning": "<one sentence>"}'
    )

    examples_block = ""
    if criterion.examples_good:
        examples_block += f"\nGood examples: {'; '.join(criterion.examples_good)}"
    if criterion.examples_bad:
        examples_block += f"\nPoor examples: {'; '.join(criterion.examples_bad)}"

    user = f"""CRITERION: {criterion.name}
DESCRIPTION: {criterion.description}{examples_block}

{few_shot}

CANDIDATE RESUME:
{resume_summary}

Score this candidate 0.0 (does not meet criterion) to 1.0 (exceeds criterion)."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        score = max(0.0, min(1.0, float(data.get("score", 0.5))))
        reasoning = data.get("reasoning", "")
        return score, reasoning
    except Exception as exc:
        logger.warning("Criterion scoring failed for '%s': %s", criterion.name, exc)
        return 0.5, "Scoring unavailable"


def _build_resume_summary(resume: ResumeAnalysis) -> str:
    lines = []
    if resume.title:
        lines.append(f"Title: {resume.title}")
    if resume.summary:
        lines.append(f"Summary: {resume.summary}")
    if resume.skills:
        skills_str = ", ".join(f"{s.name} ({s.level.value})" for s in resume.skills[:20])
        lines.append(f"Skills: {skills_str}")
    if resume.experience:
        for exp in resume.experience[:4]:
            lines.append(f"- {exp.title} at {exp.company} ({exp.duration}): {exp.description[:200]}")
    if resume.education:
        lines.append(f"Education: {'; '.join(resume.education[:3])}")
    return "\n".join(lines)


def _build_few_shot_block(examples: list[dict[str, Any]], criterion_name: str) -> str:
    """Build a few-shot context block from company calibration examples for this criterion."""
    relevant = [e for e in examples if e.get("criterion") == criterion_name][:3]
    if not relevant:
        return ""
    lines = ["COMPANY CALIBRATION EXAMPLES (use these to understand what this company values):"]
    for ex in relevant:
        lines.append(
            f"  - Resume snippet: {ex.get('resume_snippet', '')} "
            f"→ HM decision: {ex.get('hm_decision', '')} "
            f"(score was {ex.get('score', '?')})"
        )
    return "\n".join(lines) + "\n"

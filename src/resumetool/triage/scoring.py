"""Stage 1: Rubric-based resume-to-JD scoring."""
import json
import logging
from typing import Any

from resumetool.employer.models import Criterion, CriterionScore
from resumetool.llm import get_client
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
    client = get_client()

    per_scores: list[CriterionScore] = []
    for criterion in criteria:
        score, reasoning = _score_criterion(client, resume, criterion, calibration_examples or [])
        per_scores.append(CriterionScore(criterion=criterion.name, score=score, reasoning=reasoning))

    weighted = sum(cs.score * c.weight for cs, c in zip(per_scores, criteria))
    return round(weighted, 4), per_scores


def _score_criterion(
    client,
    resume: ResumeAnalysis,
    criterion: Criterion,
    calibration_examples: list[dict[str, Any]],
) -> tuple[float, str]:
    """Ask the AI to score one criterion. Returns (score 0-1, reasoning).

    Falls back to a deterministic keyword-overlap heuristic when no
    OpenAI client is available (offline demos, unit tests).
    """
    if client is None:
        return _heuristic_score_criterion(resume, criterion)

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


_KEYWORD_GROUPS: dict[str, list[str]] = {
    "Kubernetes depth": ["kubernetes", "k8s", "helm", "istio", "kubectl", "operators", "cncf"],
    "AWS expertise": ["aws", "ec2", "eks", "s3", "vpc", "iam", "lambda", "cloudformation", "terraform"],
    "Coding (Python/Go)": ["python", "go", "golang", "django", "flask", "fastapi", "grpc"],
    "Communication & mentoring": ["mentor", "led", "lead", "presented", "spoke", "wrote", "documentation", "design review"],
    "Production track record": ["production", "on-call", "incident", "sre", "reliability", "scale", "scaled"],
}


def _heuristic_score_criterion(
    resume: ResumeAnalysis,
    criterion: Criterion,
) -> tuple[float, str]:
    """Offline fallback: keyword overlap between criterion keywords and resume.

    Counts keyword **occurrences** across the resume, weighting skills-list
    matches at 2x and prose mentions at 1x, with a small bonus per unique
    keyword hit (so a resume that mentions many distinct terms beats one
    that hammers the same term repeatedly).
    """
    keywords = _KEYWORD_GROUPS.get(criterion.name, [criterion.name.lower()])

    skills_text = " ".join(s.name.lower() for s in resume.skills)
    prose_parts = [(resume.summary or "").lower()]
    for exp in resume.experience:
        prose_parts.append((exp.title or "").lower())
        prose_parts.append((exp.description or "").lower())
    prose_text = " ".join(prose_parts)

    weighted_occurrences = 0
    unique_hits = 0
    for kw in keywords:
        skill_count = skills_text.count(kw)
        prose_count = prose_text.count(kw)
        if skill_count or prose_count:
            unique_hits += 1
        weighted_occurrences += 2 * skill_count + prose_count

    if weighted_occurrences == 0:
        return 0.10, "Offline heuristic: no keyword overlap"

    # Combine raw depth (occurrences) and breadth (distinct keywords)
    depth = weighted_occurrences          # 0..~20 typical
    breadth = unique_hits                 # 0..len(keywords)
    raw = 0.18 * depth + 0.20 * breadth  # depth 1→0.18, breadth 1→0.20
    score = min(0.97, 0.20 + raw)
    return round(score, 3), f"Offline heuristic: {unique_hits} keywords, {weighted_occurrences} weighted occurrences"

"""Stage 4: Composite scoring, tier assignment, and response email generation."""
import json
import logging
from typing import Literal

from openai import OpenAI

from resumetool.config import settings
from resumetool.employer.models import CriterionScore

logger = logging.getLogger(__name__)

TierLiteral = Literal["A", "B", "C", "D"]

TIER_THRESHOLDS = {
    "A": 0.85,  # Fast-track to human interview
    "B": 0.65,  # Hold pool — HM reviews
    "C": 0.45,  # Polite decline with specific feedback
    # Below 0.45 → D: Immediate polite decline
}


def assign_tier(composite_score: float) -> TierLiteral:
    if composite_score >= TIER_THRESHOLDS["A"]:
        return "A"
    if composite_score >= TIER_THRESHOLDS["B"]:
        return "B"
    if composite_score >= TIER_THRESHOLDS["C"]:
        return "C"
    return "D"


def compute_composite(
    stage1_score: float,
    stage2_score: float | None,
    behavioral_score: float,
    stage_weights: dict[str, float],
) -> float:
    """Weighted composite. If stage2 not yet done, stage1 fills its weight too."""
    w1 = stage_weights.get("stage1", 0.50)
    w2 = stage_weights.get("stage2", 0.35)
    wb = stage_weights.get("behavioral", 0.15)

    if stage2_score is None:
        # Redistribute stage2 weight to stage1 until screen completes
        effective_w1 = w1 + w2
        return round(effective_w1 * stage1_score + wb * behavioral_score, 4)

    return round(w1 * stage1_score + w2 * stage2_score + wb * behavioral_score, 4)


def generate_response_email(
    tier: TierLiteral,
    candidate_name: str,
    req_title: str,
    company_name: str,
    criterion_scores: list[CriterionScore],
) -> str:
    """Generate a tier-appropriate response email body. No candidate gets silence."""
    client = OpenAI(api_key=settings.openai_api_key)

    top_strengths = [cs.criterion for cs in sorted(criterion_scores, key=lambda x: x.score, reverse=True)[:2]]
    top_gaps = [cs.criterion for cs in sorted(criterion_scores, key=lambda x: x.score)[:2] if cs.score < 0.6]

    tier_instructions = {
        "A": "Congratulate them warmly and invite them to schedule an interview. Express genuine enthusiasm. Keep it brief.",
        "B": (
            "Acknowledge their application positively. Let them know they are under active review "
            "and will hear back within 5-7 business days. Do not over-promise."
        ),
        "C": (
            f"Decline respectfully. Briefly mention 1-2 specific gaps ({', '.join(top_gaps) or 'experience fit'}). "
            "Encourage them — the decision is about fit, not quality. Keep it human."
        ),
        "D": (
            "Decline politely. Keep it brief and warm. Do not mention specific reasons. "
            "Thank them for their time and wish them well."
        ),
    }

    system = (
        "You write warm, human hiring response emails on behalf of a company. "
        "Never sound like a bot. Be concise (3-5 sentences max). No corporate filler."
    )

    user = f"""Write a {tier_instructions[tier]}

Candidate: {candidate_name or 'there'}
Role: {req_title}
Company: {company_name}
Candidate strengths noted: {', '.join(top_strengths) or 'N/A'}

Write only the email body (no subject line, no signature)."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.6,
            max_tokens=250,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Email generation failed for tier %s: %s", tier, exc)
        return _fallback_email(tier, candidate_name, req_title, company_name)


def _fallback_email(tier: str, name: str, role: str, company: str) -> str:
    name = name or "there"
    templates = {
        "A": (
            f"Hi {name},\n\nThank you for applying for {role} at {company}. "
            "We were impressed with your background and would love to connect. "
            "Please reply to schedule a time that works for you."
        ),
        "B": (
            f"Hi {name},\n\nThank you for applying for {role} at {company}. "
            "Your application is under active review and we expect to be in touch within 5-7 business days."
        ),
        "C": (
            f"Hi {name},\n\nThank you for applying for {role} at {company}. "
            "After careful review, we've decided to move forward with other candidates whose experience "
            "more closely matches our current needs. We appreciate you taking the time and wish you success."
        ),
        "D": (
            f"Hi {name},\n\nThank you for your interest in {role} at {company}. "
            "We appreciate you taking the time to apply and wish you the best in your search."
        ),
    }
    return templates.get(tier, templates["D"])

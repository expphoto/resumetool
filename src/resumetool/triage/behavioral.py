"""Stage 3: Behavioral signal weighting."""
import json
import logging

from openai import OpenAI

from resumetool.config import settings

logger = logging.getLogger(__name__)

# Source channel quality weights
SOURCE_WEIGHTS: dict[str, float] = {
    "referral": 1.0,
    "linkedin": 0.75,
    "indeed": 0.65,
    "ziprecruiter": 0.65,
    "glassdoor": 0.65,
    "direct": 0.80,
    "other": 0.55,
}


def compute_behavioral_score(
    cover_letter: str | None,
    source: str,
    days_since_posting: int | None,
    follow_up: bool,
    req_title: str,
) -> tuple[float, dict]:
    """Compute behavioral signal score and return (score, breakdown dict).

    Weights: cover_letter 40%, time_signal 30%, source 20%, follow_up 10%.
    """
    cover_score = _score_cover_letter(cover_letter, req_title)
    time_score = _time_signal(days_since_posting)
    source_score = SOURCE_WEIGHTS.get(source.lower(), 0.55)
    followup_score = 1.0 if follow_up else 0.0

    composite = (
        0.40 * cover_score
        + 0.30 * time_score
        + 0.20 * source_score
        + 0.10 * followup_score
    )

    breakdown = {
        "cover_letter_score": round(cover_score, 3),
        "time_signal": round(time_score, 3),
        "source_score": round(source_score, 3),
        "follow_up_bonus": round(followup_score, 3),
        "composite": round(composite, 4),
    }
    return round(composite, 4), breakdown


def _score_cover_letter(cover_letter: str | None, req_title: str) -> float:
    """Ask AI to score cover letter customization quality (0-1)."""
    if not cover_letter or len(cover_letter.strip()) < 50:
        return 0.2  # No or very short cover letter

    client = OpenAI(api_key=settings.openai_api_key)
    system = (
        "Score this cover letter's customization quality for the given role. "
        "0.0 = generic/template, 1.0 = highly specific, references role/company details, "
        "demonstrates genuine interest. "
        'Return ONLY valid JSON: {"score": <0.0-1.0>, "reason": "<10 words>"}'
    )
    user = f"ROLE: {req_title}\n\nCOVER LETTER:\n{cover_letter[:1000]}"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return max(0.0, min(1.0, float(data.get("score", 0.5))))
    except Exception as exc:
        logger.warning("Cover letter scoring failed: %s", exc)
        return 0.5


def _time_signal(days_since_posting: int | None) -> float:
    """Normalize days-since-posting to a 0-1 signal.

    Applying within 3 days = 1.0, after 21+ days = 0.2.
    """
    if days_since_posting is None:
        return 0.5
    d = max(0, days_since_posting)
    if d <= 3:
        return 1.0
    if d <= 7:
        return 0.85
    if d <= 14:
        return 0.60
    if d <= 21:
        return 0.40
    return 0.20

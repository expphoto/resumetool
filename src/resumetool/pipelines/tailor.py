"""Resume-to-JD tailoring pipeline.

The pipeline is intentionally synchronous and small so it can be wrapped
by a queue (Celery / RQ) without changing call sites. Stages:

    parse -> score -> llm_rewrite (redacted) -> render

The score stage and LLM rewrite stage both degrade gracefully: if no
LLM provider is configured we fall back to a deterministic keyword-based
match, and the rewrite stage simply returns a copy of the parsed resume.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from resumetool.analysis.resume_parser import ResumeParser
from resumetool.llm.guards import GapAnalysis
from resumetool.parsers import parse_any
from resumetool.render import render_docx, render_html
from resumetool.types import (
    JobDescription, JobExperience, MatchResult, Resume,
)

logger = logging.getLogger(__name__)


# --- Pipeline result types -------------------------------------------------

@dataclass
class TailoringResult:
    """All artifacts produced by a single :func:`tailor_resume` call."""

    output_path: str
    format: str
    score: float
    match: MatchResult
    tailored_resume: Resume
    gap_analysis: GapAnalysis
    timings_ms: dict[str, float] = field(default_factory=dict)
    intermediate: dict[str, str] = field(default_factory=dict)


# --- Main entry point ------------------------------------------------------

def tailor_resume(
    resume_path: str | Path,
    jd_path: str | Path,
    template: Optional[str] = None,
    provider: Optional[str] = None,
    output: Optional[str] = None,
    output_format: str = "html",
    redact_pii: bool = True,
) -> str:
    """Run the end-to-end tailoring pipeline.

    Parameters
    ----------
    resume_path
        Path to a resume file (PDF/DOCX/TXT) or to a structured-resume JSON.
    jd_path
        Path to a job-description text file (or a ``.json`` describing a
        :class:`JobDescription`).
    template
        Template name (subdirectory under ``resumetool/templates``).
    provider
        LLM provider identifier (e.g. ``"openai"``). When ``None`` or when
        the provider is not configured the pipeline runs offline.
    output
        Output file path. Defaults to ``./tailored.<ext>`` next to the
        resume.
    output_format
        One of ``"html"``, ``"docx"``, ``"pdf"``. ``pdf`` requires the
        optional WeasyPrint extra.
    redact_pii
        Strip emails/phones from the resume before any LLM call. Defaults
        to True (also enforced by ``resumetool.config.settings.redact_pii``).

    Returns
    -------
    str
        Absolute path of the rendered output file.
    """
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    source_resume = _load_resume(resume_path)
    jd = _load_jd(jd_path)
    timings["parse"] = _ms(t0)

    t0 = time.perf_counter()
    match = _score_resume_against_jd(source_resume, jd)
    timings["score"] = _ms(t0)

    t0 = time.perf_counter()
    gap = _build_gap_analysis(source_resume, jd, match, provider=provider)
    timings["gap_analysis"] = _ms(t0)

    t0 = time.perf_counter()
    tailored = _rewrite_resume(
        source_resume, jd, gap, provider=provider, redact_pii=redact_pii,
    )
    timings["rewrite"] = _ms(t0)

    t0 = time.perf_counter()
    out_path = _render(
        tailored,
        template=template,
        output=output,
        output_format=output_format,
    )
    timings["render"] = _ms(t0)

    logger.info(
        "tailor_resume done: score=%.3f format=%s output=%s timings=%s",
        match.score, output_format, out_path, timings,
    )
    return out_path


def tailor_resume_full(
    resume_path: str | Path,
    jd_path: str | Path,
    template: Optional[str] = None,
    provider: Optional[str] = None,
    output: Optional[str] = None,
    output_format: str = "html",
    redact_pii: bool = True,
) -> TailoringResult:
    """Same as :func:`tailor_resume` but returns the full :class:`TailoringResult`."""
    timings: dict[str, float] = {}
    intermediate: dict[str, str] = {}

    t0 = time.perf_counter()
    source_resume = _load_resume(resume_path)
    jd = _load_jd(jd_path)
    timings["parse"] = _ms(t0)

    t0 = time.perf_counter()
    match = _score_resume_against_jd(source_resume, jd)
    timings["score"] = _ms(t0)

    t0 = time.perf_counter()
    gap = _build_gap_analysis(source_resume, jd, match, provider=provider)
    timings["gap_analysis"] = _ms(t0)

    t0 = time.perf_counter()
    tailored = _rewrite_resume(source_resume, jd, gap, provider=provider, redact_pii=redact_pii)
    timings["rewrite"] = _ms(t0)

    t0 = time.perf_counter()
    out_path = _render(
        tailored,
        template=template,
        output=output,
        output_format=output_format,
    )
    timings["render"] = _ms(t0)

    return TailoringResult(
        output_path=out_path,
        format=output_format,
        score=match.score,
        match=match,
        tailored_resume=tailored,
        gap_analysis=gap,
        timings_ms=timings,
        intermediate=intermediate,
    )


# --- Stage 1: parse --------------------------------------------------------

def _load_resume(path: str | Path) -> Resume:
    """Load a resume from PDF/DOCX/TXT or a structured-resume JSON."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        try:
            return Resume.model_validate(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Resume JSON validation failed (%s); falling back to text parse", exc)
    text = parse_any(p)
    return _resume_from_text(text)


def _resume_from_text(text: str) -> Resume:
    """Convert raw text into a structured :class:`Resume`.

    The full :class:`ResumeParser` from ``resumetool.analysis`` gives us
    name/skills/experience; we adapt that into the simpler
    :class:`Resume` schema used by the tailoring pipeline.
    """
    parser = ResumeParser()
    analysis = parser.parse_text(text)
    skills = [s.name for s in analysis.skills]
    experience = [
        JobExperience(
            company=e.company or "Unknown company",
            title=e.title or "Unknown title",
            duration=e.duration or "",
            bullet_points=_bullets_from_description(e.description),
        )
        for e in analysis.experience
    ]
    return Resume(
        full_name=analysis.name,
        contact_info_redacted=True,
        summary=analysis.summary,
        skills=skills,
        experience=experience,
        education=analysis.education or [],
        certifications=analysis.certifications or [],
    )


def _bullets_from_description(desc: str) -> list[str]:
    """Split a job description into bullet points."""
    if not desc:
        return []
    parts = re.split(r"[\n•;]+", desc)
    return [p.strip(" .-") for p in parts if p.strip()]


def _load_jd(path: str | Path) -> JobDescription:
    """Load a :class:`JobDescription` from a JSON or text file."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        return JobDescription.model_validate(json.loads(p.read_text(encoding="utf-8")))
    return JobDescription(text=p.read_text(encoding="utf-8"))


# --- Stage 2: score --------------------------------------------------------

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has",
    "are", "was", "were", "will", "you", "your", "our", "their", "they",
    "them", "his", "her", "she", "him", "its", "all", "any", "but", "not",
    "can", "may", "must", "should", "would", "could", "able", "able", "etc",
    "via", "into", "onto", "over", "under", "across", "within", "without",
    "use", "using", "used", "work", "working", "role", "team", "company",
    "candidate", "candidates", "years", "year", "experience", "knowledge",
    "familiarity", "strong", "solid", "plus", "bonus", "ideal", "similar",
    "responsibilities", "requirements", "qualifications", "preferred",
    "required", "must", "nice", "to", "of", "in", "on", "a", "an", "as",
    "at", "be", "by", "or", "is", "it", "we",
}


def _extract_keywords(text: str) -> list[str]:
    """Cheap keyword extractor: lowercase word tokens, drop stopwords."""
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", text.lower())
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokens:
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _score_resume_against_jd(resume: Resume, jd: JobDescription) -> MatchResult:
    """Compute a 0..1 match score by keyword overlap."""
    resume_text = " ".join(
        [resume.summary or "", " ".join(resume.skills)]
        + [b for j in resume.experience for b in j.bullet_points]
        + [j.title for j in resume.experience]
    )
    jd_text = jd.text or " ".join(filter(None, [jd.title, jd.company]))
    jd_kw = set(_extract_keywords(jd_text))
    resume_kw = set(_extract_keywords(resume_text))
    if not jd_kw:
        return MatchResult(score=0.0, notes="Empty job description.")
    overlap = jd_kw & resume_kw
    missing = sorted(jd_kw - resume_kw)[:25]
    score = len(overlap) / max(len(jd_kw), 1)
    notes = (
        f"Matched {len(overlap)} of {len(jd_kw)} keywords. "
        f"Top gaps: {', '.join(missing[:5]) or 'none'}."
    )
    return MatchResult(score=round(score, 4), missing_keywords=missing, notes=notes)


# --- Stage 3: gap analysis (LLM or offline) --------------------------------

def _build_gap_analysis(
    resume: Resume,
    jd: JobDescription,
    match: MatchResult,
    provider: Optional[str] = None,
) -> GapAnalysis:
    """Build a :class:`GapAnalysis` from the JD + score.

    When an LLM is available we ask it to enrich the keyword-only gaps with
    qualitative suggestions. Otherwise we return a deterministic offline
    analysis so the pipeline can run end-to-end without any API keys.
    """
    offline = GapAnalysis(
        missing_keywords=match.missing_keywords,
        suggestions=_offline_suggestions(match.missing_keywords, jd),
    )
    if not provider or provider.lower() != "openai":
        return offline
    if not _openai_configured():
        return offline
    try:
        return _openai_gap_analysis(resume, jd, match)
    except Exception as exc:
        logger.warning("LLM gap analysis failed (%s); using offline analysis", exc)
        return offline


def _offline_suggestions(missing: list[str], jd: JobDescription) -> list[str]:
    """Generate template-based suggestions from the JD's missing keywords."""
    if not missing:
        return ["Resume already covers the JD keywords — consider emphasizing impact metrics."]
    suggestions = []
    for kw in missing[:5]:
        suggestions.append(
            f"Add a concrete example of using {kw} (action verb + scope + outcome)."
        )
    if jd.text and len(jd.text) < 400:
        suggestions.append("Job description is short — confirm scope with the recruiter.")
    return suggestions


def _openai_configured() -> bool:
    try:
        from resumetool.config import settings
        return bool(getattr(settings, "openai_api_key", None))
    except Exception:
        return False


def _openai_gap_analysis(resume: Resume, jd: JobDescription, match: MatchResult) -> GapAnalysis:
    """Use the configured OpenAI model to enrich the gap analysis."""
    from resumetool.llm import get_client

    client = get_client()
    if client is None:
        raise RuntimeError("OpenAI client unavailable")
    system = (
        "You are an expert technical recruiter. You will receive a resume and "
        "a job description and a list of already-detected missing keywords. "
        "Produce a concise gap analysis. "
        "Return ONLY valid JSON matching this schema: "
        '{"missing_keywords": [string, ...], "suggestions": [string, ...]}'
    )
    user = json.dumps({
        "resume": resume.model_dump(exclude={"contact_info_redacted"}),
        "job_description": jd.model_dump(),
        "existing_missing_keywords": match.missing_keywords,
    }, default=str)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    return GapAnalysis.model_validate(data)


# --- Stage 4: rewrite ------------------------------------------------------

_PII_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    re.compile(
        r"(?:\+?\d{1,2}[\s.-]?)?"
        r"(?:\(\d{3}\)|\d{3})"
        r"[\s.-]?\d{3}[\s.-]?\d{4}"
    ),
]


def _redact_pii(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _PII_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _rewrite_resume(
    resume: Resume,
    jd: JobDescription,
    gap: GapAnalysis,
    provider: Optional[str] = None,
    redact_pii: bool = True,
) -> Resume:
    """Return a tailored resume.

    Offline (no LLM): copy the parsed resume, redact PII, and emphasize any
    of the candidate's existing skills that overlap with the JD.

    Online: ask the LLM to produce a structured rewrite and validate it
    against the :class:`Resume` schema. Falls back to the offline path on
    any LLM error so the pipeline is never dead in the water.
    """
    safe_resume = _redact_resume(resume) if redact_pii else resume.model_copy(deep=True)

    if not provider or provider.lower() != "openai" or not _openai_configured():
        return _offline_rewrite(safe_resume, jd, gap)

    try:
        return _openai_rewrite(safe_resume, jd, gap)
    except Exception as exc:
        logger.warning("LLM rewrite failed (%s); using offline rewrite", exc)
        return _offline_rewrite(safe_resume, jd, gap)


def _redact_resume(resume: Resume) -> Resume:
    """Return a deep copy of the resume with PII removed from all string fields.

    The candidate's name is preserved — the candidate is sharing their own
    resume with the LLM, so the name is not PII in this context. We only
    strip contact channels (email, phone) and any PII patterns that appear
    in summary / bullet points.
    """
    data = resume.model_dump()
    for job in data.get("experience", []):
        for k, v in list(job.items()):
            if isinstance(v, str):
                job[k] = _redact_pii(v)
            elif isinstance(v, list):
                job[k] = [_redact_pii(item) if isinstance(item, str) else item for item in v]
    for string_field in ("summary",):
        if isinstance(data.get(string_field), str):
            data[string_field] = _redact_pii(data[string_field])
    for list_field in ("skills", "education", "certifications"):
        if isinstance(data.get(list_field), list):
            data[list_field] = [
                _redact_pii(item) if isinstance(item, str) else item
                for item in data[list_field]
            ]
    return Resume.model_validate(data)


def _offline_rewrite(resume: Resume, jd: JobDescription, gap: GapAnalysis) -> Resume:
    """Deterministic offline rewrite: reorder skills by JD overlap, tighten summary."""
    jd_text = (jd.text or "").lower()
    skills = list(resume.skills)
    if jd_text:
        scored = sorted(
            skills,
            key=lambda s: (s.lower() in jd_text, len(s)),
            reverse=True,
        )
        skills = scored
    summary = resume.summary
    if not summary and jd.title:
        summary = f"Targeted for {jd.title} role."
    return resume.model_copy(update={"skills": skills, "summary": summary})


def _openai_rewrite(resume: Resume, jd: JobDescription, gap: GapAnalysis) -> Resume:
    """Ask the configured OpenAI model to produce a tailored :class:`Resume`."""
    from resumetool.llm import get_client

    client = get_client()
    if client is None:
        raise RuntimeError("OpenAI client unavailable")
    schema = Resume.model_json_schema()
    system = (
        "You are an expert resume writer. You will receive a structured resume "
        "and a job description. Rewrite the resume to better match the JD, "
        "reordering skills by relevance, sharpening the summary, and rewording "
        "bullet points to emphasize impact. Do NOT fabricate experience. "
        f"Return ONLY valid JSON matching this schema: {schema}"
    )
    user = json.dumps({
        "resume": resume.model_dump(),
        "job_description": jd.model_dump(),
        "gap_analysis": gap.model_dump(),
    }, default=str)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    return Resume.model_validate(data)


# --- Stage 5: render -------------------------------------------------------

def _render(
    resume: Resume,
    template: Optional[str] = None,
    output: Optional[str] | None = None,
    output_format: str = "html",
) -> str:
    """Render the tailored resume to the requested format."""
    fmt = output_format.lower()
    if fmt not in {"html", "docx", "pdf"}:
        raise ValueError(f"Unsupported output format: {output_format!r}")

    out_path = Path(output) if output else Path("tailored." + fmt)
    if out_path.is_dir() or str(out_path).endswith("/"):
        out_path = out_path / f"tailored.{fmt}"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    json_tmp = out_path.with_suffix(".json")
    json_tmp.write_text(
        json.dumps(resume.model_dump(), indent=2), encoding="utf-8",
    )

    if fmt == "html":
        rendered = render_html(json_tmp, template=template, output_path=out_path)
    elif fmt == "docx":
        rendered = render_docx(json_tmp, output_path=out_path)
    else:
        rendered = _render_pdf_via_html(json_tmp, template=template, output_path=out_path)

    try:
        json_tmp.unlink()
    except OSError:
        pass
    return rendered


def _render_pdf_via_html(json_path: Path, template: Optional[str], output_path: Path) -> str:
    """Render PDF by first producing HTML then converting with WeasyPrint."""
    html_path = render_html(json_path, template=template, output_path=output_path.with_suffix(".html"))
    from resumetool.render.pdf import render_pdf
    return render_pdf(html_path, output_path=output_path)


# --- Helpers --------------------------------------------------------------

def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)

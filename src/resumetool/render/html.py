"""HTML rendering for structured resumes."""
from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from resumetool.types import Resume


def render_html(
    structured_resume_path: str | Path,
    template: str | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Render a structured resume JSON to HTML.

    Parameters
    ----------
    structured_resume_path
        Path to a JSON file containing a :class:`Resume` (or compatible dict).
    template
        Template name (subdirectory under ``resumetool/templates``). Defaults
        to ``"default"``.
    output_path
        Where to write the rendered HTML. Defaults to the resume path with a
        ``.html`` suffix.

    Returns
    -------
    str
        Absolute path of the rendered HTML file.
    """
    src = Path(structured_resume_path)
    if not src.exists():
        raise FileNotFoundError(f"Resume JSON not found: {src}")
    resume = _load_resume(src)

    out = Path(output_path) if output_path else src.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)

    env = _build_jinja_env(template or "default")
    tpl_name = _resolve_template_name(template or "default")
    html = env.get_template(tpl_name).render(**_resume_context(resume))

    out.write_text(html, encoding="utf-8")
    _copy_template_assets(template or "default", out.parent)
    return str(out.resolve())


def _load_resume(path: Path) -> Resume:
    """Load and validate a Resume from JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Resume.model_validate(raw)


def _build_jinja_env(template_name: str) -> Environment:
    """Build a Jinja2 environment for the given template directory."""
    template_dir = _template_dir(template_name)
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _template_dir(template_name: str) -> Path:
    """Locate a template directory inside the package."""
    try:
        ref = resources.files("resumetool") / "templates" / template_name
        if ref.is_dir():
            return Path(str(ref))
    except Exception:
        pass
    raise FileNotFoundError(f"Template not found: {template_name!r}")


def _resolve_template_name(template_name: str) -> str:
    """Map a template dir to its primary HTML template filename."""
    candidate = _template_dir(template_name) / "resume.html.j2"
    if candidate.exists():
        return "resume.html.j2"
    raise FileNotFoundError(f"No resume.html.j2 in template {template_name!r}")


def _resume_context(resume: Resume) -> dict[str, Any]:
    """Build the template context, deriving presentation helpers from Resume."""
    contact_line = None
    if not resume.contact_info_redacted and resume.full_name:
        contact_line = resume.full_name
    return {
        "full_name": resume.full_name,
        "summary": resume.summary,
        "skills": resume.skills,
        "experience": [je.model_dump() for je in resume.experience],
        "education": getattr(resume, "education", []) or [],
        "certifications": getattr(resume, "certifications", []) or [],
        "contact_line": contact_line,
        "contact_info_redacted": resume.contact_info_redacted,
    }


def _copy_template_assets(template_name: str, out_dir: Path) -> None:
    """Copy any sibling assets (CSS, fonts) to the output directory."""
    src_dir = _template_dir(template_name)
    for asset in src_dir.iterdir():
        if asset.name.endswith(".j2"):
            continue
        if asset.is_file():
            shutil.copy2(asset, out_dir / asset.name)

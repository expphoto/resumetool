from pathlib import Path
from typing import Optional


def tailor_resume(
    resume_path: str | Path,
    jd_path: str | Path,
    template: Optional[str] = None,
    provider: Optional[str] = None,
    output: Optional[str] = None,
) -> str:
    """Stub for end-to-end tailoring orchestrator.

    Returns the output path (str) where the tailored resume would be written.
    """
    # TODO: parse → score → LLM rewrite (redacted) → render
    return str(output or "tailored.docx")


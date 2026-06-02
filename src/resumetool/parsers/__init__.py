"""Resume/job-description file parsers.

Each parser returns a plain string. Use :func:`parse_any` to dispatch on the
file extension when you don't know the format up front.
"""
from __future__ import annotations

from pathlib import Path

from .pdf import parse_pdf
from .docx import parse_docx
from .txt import parse_txt

__all__ = ["parse_pdf", "parse_docx", "parse_txt", "parse_any"]


def parse_any(path: str | Path) -> str:
    """Dispatch to the correct parser based on file extension."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(p)
    if suffix == ".docx":
        return parse_docx(p)
    if suffix in {".txt", ".md", ""}:
        return parse_txt(p)
    raise ValueError(f"Unsupported file extension for parsing: {suffix!r}")

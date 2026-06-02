"""DOCX text extraction.

Walks the document body in order, collecting paragraph text and treating
list items as separate bullet lines so downstream parsers can preserve the
structure of the original resume.
"""
from __future__ import annotations

from pathlib import Path


def parse_docx(path: str | Path) -> str:
    """Extract text from a DOCX file.

    Each paragraph and list item is emitted on its own line. Bulleted/numbered
    list items are prefixed with "  - " to make them easy to identify.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"DOCX not found: {p}")
    if p.suffix.lower() != ".docx":
        raise ValueError(f"Expected .docx file, got {p.suffix}")

    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "python-docx is required for DOCX parsing. "
            "Install with: pip install python-docx"
        ) from exc

    doc = Document(str(p))
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style is not None else ""
        if "list" in style:
            lines.append(f"  - {text}")
        else:
            lines.append(text)
    return "\n".join(lines)

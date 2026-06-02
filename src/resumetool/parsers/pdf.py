"""PDF text extraction with layout-aware fallback.

Uses pdfminer.six as the primary extractor (best for layout-preserving text)
and falls back to pypdf for damaged or image-only PDFs that pdfminer cannot
parse cleanly.
"""
from __future__ import annotations

from pathlib import Path


def parse_pdf(path: str | Path) -> str:
    """Extract text from a PDF file.

    Returns the full document text with paragraph structure preserved. Empty
    sections and form-feed characters between pages are collapsed into single
    newlines for downstream parsing.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf file, got {p.suffix}")

    text = _extract_with_pdfminer(p)
    if not text.strip():
        text = _extract_with_pypdf(p)
    return _normalize(text)


def _extract_with_pdfminer(path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(path))
    except Exception:
        return ""


def _extract_with_pypdf(path: Path) -> str:
    try:
        import pypdf
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts)
    except Exception:
        return ""


def _normalize(text: str) -> str:
    """Collapse form feeds and excessive blank lines."""
    if not text:
        return ""
    out = text.replace("\f", "\n")
    lines = [ln.rstrip() for ln in out.splitlines()]
    cleaned: list[str] = []
    blank = 0
    for line in lines:
        if not line.strip():
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip()

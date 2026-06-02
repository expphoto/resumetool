"""Plain text file extraction."""
from __future__ import annotations

from pathlib import Path


def parse_txt(path: str | Path) -> str:
    """Read a UTF-8 text file and return its contents.

    Falls back to a lossy decode for non-UTF-8 source files so the pipeline
    never blows up on odd encodings; downstream redaction can still scrub
    whatever made it through.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Text file not found: {p}")
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="ignore")

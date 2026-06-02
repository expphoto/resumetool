"""HTML → PDF rendering for resumes via WeasyPrint.

WeasyPrint is an optional extra (``pip install '.[render]'``). When it is
not installed the renderer raises a clear, actionable error rather than
silently producing a broken file.
"""
from __future__ import annotations

from pathlib import Path


def render_pdf(html_path: str | Path, output_path: str | Path | None = None) -> str:
    """Render an HTML file to PDF using WeasyPrint.

    Returns the absolute path of the rendered PDF.
    """
    src = Path(html_path)
    if not src.exists():
        raise FileNotFoundError(f"HTML source not found: {src}")

    out = Path(output_path) if output_path else src.with_suffix(".pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "WeasyPrint is required for PDF rendering. "
            "Install with: pip install 'resumetool[render]' "
            "(macOS also needs the system pango/gdk libraries)."
        ) from exc

    HTML(filename=str(src)).write_pdf(str(out))
    return str(out.resolve())

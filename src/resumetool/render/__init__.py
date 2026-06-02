"""Resume renderers.

Each renderer takes a structured-resume JSON file (matching
:class:`resumetool.types.Resume`) and produces a document in a different
format. The HTML and DOCX renderers are always available; the PDF renderer
requires the optional ``weasyprint`` extra.
"""
from __future__ import annotations

from .docx import render_docx
from .html import render_html
from .pdf import render_pdf

__all__ = ["render_html", "render_docx", "render_pdf"]

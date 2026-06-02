"""End-to-end resume pipelines."""
from __future__ import annotations

from .tailor import tailor_resume, tailor_resume_full, TailoringResult

__all__ = ["tailor_resume", "tailor_resume_full", "TailoringResult"]

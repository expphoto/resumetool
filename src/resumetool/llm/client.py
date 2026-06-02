"""Lazy-initialized OpenAI client with offline fallback.

Centralizes OpenAI client construction so the rest of the codebase can
just call `get_client()` and get `None` when no API key is set. Callers
are expected to detect `None` and either skip the LLM call or fall back
to a heuristic.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_checked = False


def get_client():
    """Return an OpenAI client, or None if no API key is configured.

    Result is cached after the first call.
    """
    global _client, _checked
    if _checked:
        return _client
    _checked = True

    from openai import OpenAI  # local import to keep this module cheap

    try:
        # `OpenAI()` already reads OPENAI_API_KEY from env, but we also
        # check settings.openai_api_key so the user can set it via .env.
        from resumetool.config import settings

        api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.info("OPENAI_API_KEY not set; LLM features will use offline fallback")
            _client = None
            return _client
        _client = OpenAI(api_key=api_key)
        return _client
    except Exception as exc:
        logger.warning("Could not initialise OpenAI client: %s", exc)
        _client = None
        return _client


def reset_for_tests() -> None:
    """Drop the cached client (used by tests after monkey-patching env)."""
    global _client, _checked
    _client = None
    _checked = False

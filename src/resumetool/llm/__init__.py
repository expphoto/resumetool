"""LLM helpers (lazy clients, offline fallbacks)."""
from resumetool.llm.client import get_client, reset_for_tests

__all__ = ["get_client", "reset_for_tests"]

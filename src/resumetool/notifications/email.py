"""Email delivery services for triage response emails.

The pipeline always generates the response email body; *sending* is
delegated to an :class:`EmailService` so the system can run in three modes:

* **Resend** — real delivery via resend.com (needs ``RESUMETOOL_EMAIL_API_KEY``)
* **Dry-run** — captures everything but marks the event ``dry_run`` so a
  client demo never accidentally mails a real candidate
* **Console** — last-resort fallback that prints the email to stdout

Selection is automatic based on :mod:`resumetool.config` settings.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


logger = logging.getLogger(__name__)


# --- Result type ---------------------------------------------------------

@dataclass
class EmailResult:
    """Outcome of a single send attempt."""

    success: bool
    provider: str
    provider_id: str | None = None
    error: str | None = None
    dry_run: bool = False
    metadata: dict = field(default_factory=dict)


# --- Service protocol ----------------------------------------------------

class EmailService(Protocol):
    """Anything that can deliver a single response email."""

    name: str

    def send(self, to_email: str, subject: str, body: str) -> EmailResult: ...


# --- Dry-run implementation ----------------------------------------------

class DryRunEmailService:
    """Captures everything, marks the event as dry-run, never sends."""

    name = "dry_run"

    def send(self, to_email: str, subject: str, body: str) -> EmailResult:
        logger.info(
            "[dry_run] would send to=%s subject=%r body_chars=%d",
            to_email, subject, len(body or ""),
        )
        return EmailResult(
            success=True,
            provider=self.name,
            provider_id=f"dry_{uuid.uuid4().hex[:10]}",
            dry_run=True,
            metadata={"to": to_email, "subject": subject, "body_chars": len(body or "")},
        )


# --- Console implementation ----------------------------------------------

class ConsoleEmailService:
    """Last-resort fallback. Prints to stdout and logs success."""

    name = "console"

    def send(self, to_email: str, subject: str, body: str) -> EmailResult:
        sep = "=" * 60
        logger.warning(
            "EMAIL_API_KEY not set — printing email to stdout (no real delivery).\n%s\nTo: %s\nSubject: %s\n\n%s\n%s",
            sep, to_email, subject, body, sep,
        )
        print(sep)
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print()
        print(body)
        print(sep)
        return EmailResult(
            success=True,
            provider=self.name,
            provider_id=f"console_{uuid.uuid4().hex[:10]}",
            metadata={"to": to_email, "subject": subject, "body_chars": len(body or "")},
        )


# --- Resend implementation -----------------------------------------------

class ResendEmailService:
    """Real delivery via the resend.com API."""

    name = "resend"

    def __init__(self, api_key: str, from_address: str):
        try:
            import resend  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "The 'resend' package is required for real email delivery. "
                "Install with: pip install 'resend>=2.0'"
            ) from exc
        self._resend = resend
        self._resend.api_key = api_key
        self.from_address = from_address

    def send(self, to_email: str, subject: str, body: str) -> EmailResult:
        try:
            params = {
                "from": self.from_address,
                "to": [to_email],
                "subject": subject,
                "text": body,
            }
            resp = self._resend.Emails.send(params)
            provider_id = getattr(resp, "id", None) or (
                resp.get("id") if isinstance(resp, dict) else None
            )
            return EmailResult(
                success=True,
                provider=self.name,
                provider_id=provider_id,
                metadata={"to": to_email, "subject": subject},
            )
        except Exception as exc:
            logger.exception("Resend send failed for %s", to_email)
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(exc),
                metadata={"to": to_email, "subject": subject},
            )


# --- Factory -------------------------------------------------------------

def build_email_service(force_dry_run: bool | None = None) -> EmailService:
    """Return the configured :class:`EmailService`.

    Resolution order:

    1. ``force_dry_run=True``  → :class:`DryRunEmailService`
    2. ``force_dry_run=False`` → real provider (Resend if key set, else Console)
    3. ``force_dry_run=None``  → check ``RESUMETOOL_DRY_RUN_EMAIL`` env var
       (or the matching config setting) — defaults to True when the API key
       is missing so demos never accidentally mail real candidates.
    """
    # Re-read the live settings singleton so tests that mutate env vars
    # or replace `cfg.settings` see the new values.
    from resumetool.config import settings as _settings

    if force_dry_run is None:
        env_flag = os.getenv("RESUMETOOL_DRY_RUN_EMAIL", "").lower()
        if env_flag in {"1", "true", "yes", "on"}:
            force_dry_run = True
        elif env_flag in {"0", "false", "no", "off"}:
            force_dry_run = False
        else:
            force_dry_run = not bool(getattr(_settings, "email_api_key", None))

    if force_dry_run:
        return DryRunEmailService()

    api_key = getattr(_settings, "email_api_key", None)
    from_address = getattr(_settings, "email_from_address", None) or "hiring@example.com"
    if not api_key:
        return ConsoleEmailService()
    return ResendEmailService(api_key=api_key, from_address=from_address)


# --- Subject line derivation --------------------------------------------

_TIER_SUBJECTS = {
    "A": "Next steps: we'd love to chat",
    "B": "Your application is under active review",
    "C": "An update on your application",
    "D": "Thanks for applying",
}


def subject_for_tier(tier: str | None, req_title: str | None = None) -> str:
    """Return a tier-appropriate email subject line."""
    base = _TIER_SUBJECTS.get(str(tier) if tier else "", "An update on your application")
    if req_title:
        return f"{base} — {req_title}"
    return base


# --- Persistence helpers -------------------------------------------------

def log_email_event(
    db,
    application_id: str,
    tier: str | None,
    to_email: str,
    subject: str,
    body: str,
    status: str,
    provider: str | None = None,
    provider_id: str | None = None,
    error: str | None = None,
    sent_at: datetime | None = None,
):
    """Persist an :class:`EmailEvent` row and return it."""
    from resumetool.database.models import EmailEvent, EmailStatus, TriageResult

    event = EmailEvent(
        id=str(uuid.uuid4()),
        application_id=application_id,
        tier=tier,
        to_email=to_email,
        subject=subject,
        body=body,
        status=EmailStatus(status),
        provider=provider,
        provider_id=provider_id,
        error_message=error,
        sent_at=sent_at,
    )
    db.add(event)

    if status in ("sent", "dry_run") and tier:
        result = (
            db.query(TriageResult)
            .filter_by(application_id=application_id)
            .first()
        )
        if result and not result.response_sent_at:
            result.response_sent_at = sent_at or datetime.utcnow()

    db.commit()
    db.refresh(event)
    return event

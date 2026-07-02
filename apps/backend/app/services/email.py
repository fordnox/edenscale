"""SMTP email delivery + tokenized HTML template rendering.

Templates live in ``app/templates_email/{name}.html`` and use
``string.Template`` ``$token`` placeholders; rendering uses
``safe_substitute`` so missing params degrade gracefully instead of raising.

Sending is a blocking ``smtplib`` call — async callers (arq tasks, routes)
must go through :func:`send_email_async`, which runs the send in a thread.

When email delivery is disabled (``EMAIL_ENABLED`` false, or ``SMTP_HOST`` /
``EMAIL_FROM`` unset) the payload is logged at info level and the function
returns ``False`` — no send is attempted and nothing raises.
"""

import asyncio
import html
import logging
import smtplib
import string
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates_email"

# name -> raw template text, cached for the process lifetime.
_template_cache: dict[str, str] = {}


def render_template(name: str, **params: Any) -> str:
    """Render ``app/templates_email/{name}.html`` with ``$token`` substitution.

    File reads are cached in a module-level dict; unknown tokens are left
    intact (``safe_substitute``). Every substituted value is HTML-escaped —
    params carry user-entered content (titles, descriptions, names) that must
    never land in the markup as live HTML.
    """
    raw = _template_cache.get(name)
    if raw is None:
        raw = (_TEMPLATES_DIR / f"{name}.html").read_text(encoding="utf-8")
        _template_cache[name] = raw
    escaped = {
        key: html.escape(str(value), quote=True) for key, value in params.items()
    }
    return string.Template(raw).safe_substitute(escaped)


def _delivery_configured() -> bool:
    return bool(settings.EMAIL_ENABLED and settings.SMTP_HOST and settings.EMAIL_FROM)


def send_email(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    *,
    context: dict[str, Any] | None = None,
) -> bool:
    """Send one HTML email over SMTP. Blocking; returns ``True`` on success.

    ``context`` is only used for logging in disabled mode (the substituted
    template variables — never the full HTML body).
    """
    if not _delivery_configured():
        logger.info(
            "Email delivery disabled; skipping send (to=%s subject=%r context=%s)",
            to,
            subject,
            context or {},
        )
        return False

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(
        text or "This email is best viewed in an HTML-capable email client."
    )
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("Email sent (to=%s subject=%r)", to, subject)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Email send failed (to=%s subject=%r): %s", to, subject, exc)
        return False


async def send_email_async(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    *,
    context: dict[str, Any] | None = None,
) -> bool:
    """Async wrapper around :func:`send_email` using ``asyncio.to_thread``."""
    return await asyncio.to_thread(send_email, to, subject, html, text, context=context)

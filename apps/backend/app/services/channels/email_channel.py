import json
import logging
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import resend

from app.core.config import settings
from app.services.channels.base import NotificationChannel

logger = logging.getLogger(__name__)


# Resend rejects template variables longer than 2000 chars. Long fields are
# truncated rather than dropped so they remain referenceable in templates.
RESEND_MAX_VARIABLE_LENGTH = 2000

# Cheap shape checks so ``fromisoformat`` only runs on values that actually
# look like dates/datetimes; everything else (URLs, UUIDs, free text) skips
# the parse path entirely.
_ISO_DATETIME_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC = ZoneInfo("UTC")


def _truncate(value: str) -> str:
    return value[:RESEND_MAX_VARIABLE_LENGTH]


def _resolve_timezone(data: dict) -> ZoneInfo:
    """Pick the recipient's tz from the worker-attached ``organization`` block.

    edenscale organizations have no timezone column, so this falls back to UTC
    in practice — kept for parity with the shared architecture and so a future
    org.timezone field would be honoured automatically.
    """
    org = (
        data.get("organization") if isinstance(data.get("organization"), dict) else None
    )
    tz_name = (org or {}).get("timezone") or "UTC"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return _UTC


def _humanize_datetime(value: str, tz: ZoneInfo) -> str | None:
    """Render ISO date / datetime strings human-readably, else return None."""
    if _ISO_DATE_RE.match(value):
        try:
            d = date.fromisoformat(value)
        except ValueError:
            return None
        return d.strftime("%b %d, %Y")
    if _ISO_DATETIME_PREFIX_RE.match(value):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_UTC)
        local = dt.astimezone(tz)
        return local.strftime("%b %d, %Y · %H:%M %Z")
    return None


def _flatten_variables(
    data: dict, prefix: str = "", tz: ZoneInfo | None = None
) -> dict[str, str | int | float]:
    # Resend template variables only support string/number values, and its
    # Mustache parser treats ``{{{ a.b }}}`` as a nested lookup of ``a`` — which
    # fails validation because ``a`` isn't a scalar. Nested dicts are therefore
    # flattened with underscore-joined keys so every placeholder maps to a flat
    # scalar; lists are JSON-stringified. ISO date/datetime strings are
    # rendered so emails never show raw ``2026-05-17T07:37:17+00:00`` values.
    if tz is None:
        tz = _resolve_timezone(data)
    out: dict[str, str | int | float] = {}
    for key, value in data.items():
        full_key = f"{prefix}{key}"
        if value is None:
            out[full_key] = ""
        elif isinstance(value, bool):
            out[full_key] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            out[full_key] = value
        elif isinstance(value, str):
            formatted = _humanize_datetime(value, tz)
            out[full_key] = _truncate(formatted if formatted is not None else value)
        elif isinstance(value, dict):
            out.update(_flatten_variables(value, prefix=f"{full_key}_", tz=tz))
        elif isinstance(value, list):
            out[full_key] = _truncate(json.dumps(value, default=str))
        else:
            out[full_key] = _truncate(str(value))
    return out


class EmailChannel(NotificationChannel):
    channel_name: str = "email"

    async def send(
        self,
        recipient_email: str,
        title: str,
        message: str,
        event_type: str,
        data: dict,
    ) -> dict:
        if not recipient_email:
            return {"success": False, "error": "no recipient email"}
        if not settings.RESEND_API_KEY:
            # Email delivery is off (no key). The in-app notification still
            # persisted; surface a clear, non-alarming log status.
            logger.info(
                "Email delivery skipped for %s (RESEND_API_KEY not set): %s",
                recipient_email,
                event_type,
            )
            return {"success": False, "disabled": True, "error": "email delivery off"}

        # Resend template ids are the NotificationType value with all
        # non-alphanumerics stripped — e.g. ``customer.capital_call`` →
        # ``customercapitalcall`` (must match emails/scripts/push-templates.mts).
        template_id = re.sub(r"[^a-zA-Z0-9]", "", event_type)
        variables: dict[str, Any] = _flatten_variables(data or {})
        variables.setdefault("subject", title)
        variables.setdefault("preview", message)
        variables.setdefault("title", title)
        variables.setdefault("message", message)

        # Display the org name as the sender label:
        # "<Org Name> <notifications@…>" rather than the bare address.
        org_name = str(variables.get("organization_name") or "").strip()
        from_address = (
            f"{org_name} <{settings.NOTIFICATION_FROM_EMAIL}>"
            if org_name
            else settings.NOTIFICATION_FROM_EMAIL
        )

        params = {
            "from": from_address,
            "to": [recipient_email],
            "subject": title,
            "preview": message,
            "template": {"id": template_id, "variables": variables},
        }
        try:
            resend.api_key = settings.RESEND_API_KEY
            response = await resend.Emails.send_async(params)  # type: ignore[invalid-argument-type]
            return {"success": True, "provider_id": response["id"]}
        except Exception as e:  # noqa: BLE001 - never let a send break the worker
            logger.error("Email send failed for %s: %s", recipient_email, e)
            return {"success": False, "error": str(e)}

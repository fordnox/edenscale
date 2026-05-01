"""Hanko admin/public API client used by the invitation flow.

Hanko's API does not expose arbitrary transactional email sending — its only
mail surface is the authentication passcode flow plus the ``email.send``
webhook (which Hanko triggers when *Hanko* needs to send an auth email).

The invitation flow therefore uses Hanko as a sign-in trigger: we ensure the
invitee exists as a Hanko user (create via Admin API if missing), then
initialize a passcode login so Hanko mails them an authentication code. After
sign-in, the frontend reads ``/invitations/pending-for-me`` and surfaces the
pending invite via banner; the ``accept_url`` is recorded on the invitation
row for resend bookkeeping and for the future custom-email path.

Failures never raise to the caller — they are logged so the admin can resend.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class HankoServiceError(Exception):
    """Raised internally when the Hanko API returns an unrecoverable error."""


def _admin_base_url() -> str:
    return f"{settings.HANKO_API_URL.rstrip('/')}/admin"


def _public_base_url() -> str:
    return settings.HANKO_API_URL.rstrip("/")


def _admin_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.HANKO_API_KEY}",
        "Content-Type": "application/json",
    }


async def _find_user_by_email(
    client: httpx.AsyncClient, email: str
) -> dict[str, Any] | None:
    response = await client.get(
        f"{_admin_base_url()}/users",
        headers=_admin_headers(),
        params={"email": email, "per_page": 1},
    )
    response.raise_for_status()
    users = response.json() or []
    return users[0] if users else None


async def _create_user(client: httpx.AsyncClient, email: str) -> dict[str, Any]:
    response = await client.post(
        f"{_admin_base_url()}/users",
        headers=_admin_headers(),
        json={"emails": [{"address": email, "is_primary": True, "is_verified": False}]},
    )
    if response.status_code == 409:
        existing = await _find_user_by_email(client, email)
        if existing is None:
            raise HankoServiceError(
                f"Hanko reported 409 for {email} but lookup found no user"
            )
        return existing
    response.raise_for_status()
    return response.json()


def _extract_email_id(user: dict[str, Any], email: str) -> str | None:
    for entry in user.get("emails") or []:
        if (entry.get("address") or "").lower() == email.lower():
            email_id = entry.get("id")
            if isinstance(email_id, str):
                return email_id
    return None


async def _send_passcode(
    client: httpx.AsyncClient, user_id: str, email_id: str | None
) -> None:
    payload: dict[str, str] = {"user_id": user_id}
    if email_id:
        payload["email_id"] = email_id
    response = await client.post(
        f"{_public_base_url()}/passcode/login/initialize",
        headers={"Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()


async def send_invitation_email(
    email: str,
    accept_url: str,
    organization_name: str,
    inviter_name: str | None = None,
) -> bool:
    """Trigger a Hanko sign-in email for an invitee.

    Hanko cannot deliver arbitrary content, so the ``accept_url`` is recorded
    for bookkeeping and surfaced via ``/invitations/pending-for-me`` after the
    user signs in. The email Hanko sends contains the standard passcode.

    Returns ``True`` on success, ``False`` on any failure. Never raises.
    """
    if not settings.HANKO_API_URL or not settings.HANKO_API_KEY:
        logger.warning(
            "Hanko invitation email skipped: HANKO_API_URL/HANKO_API_KEY not configured "
            "(email=%s organization=%s accept_url=%s inviter=%s)",
            email,
            organization_name,
            accept_url,
            inviter_name or "<unknown>",
        )
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            user = await _find_user_by_email(client, email)
            if user is None:
                user = await _create_user(client, email)

            user_id = user.get("id")
            if not isinstance(user_id, str) or not user_id:
                raise HankoServiceError("Hanko user record missing 'id'")

            email_id = _extract_email_id(user, email)
            await _send_passcode(client, user_id, email_id)

        logger.info(
            "Hanko invitation email triggered (email=%s organization=%s "
            "accept_url=%s inviter=%s)",
            email,
            organization_name,
            accept_url,
            inviter_name or "<unknown>",
        )
        return True
    except (httpx.HTTPError, HankoServiceError) as exc:
        logger.exception(
            "Hanko invitation email failed (email=%s organization=%s): %s",
            email,
            organization_name,
            exc,
        )
        return False

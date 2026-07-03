"""Hanko admin API client used by the invitation flow.

The invitation flow only needs Hanko for account pre-provisioning: we ensure
the invitee exists as a Hanko user (create via Admin API if missing) so that
the sign-in flow works when they follow the invitation link. The invitation
email itself is delivered by the notification pipeline (see
``notify_invitation`` in ``app.services.notifications``).

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


async def ensure_hanko_user(email: str) -> bool:
    """Ensure a Hanko user exists for ``email`` (create via Admin API if missing).

    Returns ``True`` on success, ``False`` on any failure. Never raises.
    """
    if not settings.HANKO_API_URL or not settings.HANKO_API_KEY:
        logger.warning(
            "Hanko user provisioning skipped: HANKO_API_URL/HANKO_API_KEY "
            "not configured (email=%s)",
            email,
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

        logger.info("Hanko user ensured (email=%s hanko_id=%s)", email, user_id)
        return True
    except (httpx.HTTPError, HankoServiceError) as exc:
        logger.exception("Hanko user provisioning failed (email=%s): %s", email, exc)
        return False

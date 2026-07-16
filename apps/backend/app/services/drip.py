"""Investor onboarding drip — the Resend-automation side of onboarding.

This is deliberately *not* part of the ``notify_*`` pipeline. A ``notify_*``
helper renders one email from one template and sends it now; the drip is a
seven-day sequence whose schedule and copy live in a Resend automation
("Investor Drip"). All the backend does is fire the ``investor.signup`` event
that starts that automation — Resend owns the delays and the sends from there.

Flow mirrors notifications: the request path only enqueues
(:func:`fire_investor_signup`), and the worker does the HTTP call
(:func:`deliver_drip_event`), so a slow Resend never stalls an API request.

The event payload keys are the template variables the drip's seven templates
declare (``emails/drip/day_*.tsx``): recipient_name, app_url,
organization_name, organization_website. Adding a variable to a template means
adding it here too, or it renders empty.
"""

import logging

import resend

from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.tasks import enqueue_drip_event

logger = logging.getLogger(__name__)

# Must match the trigger event name on the "Investor Drip" automation in Resend.
INVESTOR_SIGNUP_EVENT = "investor.signup"


async def fire_investor_signup(*, user: User, organization: Organization) -> None:
    """Start the onboarding drip for an investor who has just joined.

    Fire-and-forget: wrapped in ``try/except`` so a drip failure never breaks
    the invitation-accept write, exactly like the ``notify_*`` helpers.
    """
    try:
        if not user.email:
            return
        await enqueue_drip_event(
            event=INVESTOR_SIGNUP_EVENT,
            email=str(user.email),
            payload={
                "recipient_name": (user.first_name or "").strip() or "there",
                "app_url": f"{settings.app_domain_url}/investor",
                "organization_name": organization.name,
                # Nullable column — the drip footer renders it as plain text.
                "organization_website": organization.website or "",
            },
        )
    except Exception:
        logger.exception("Investor signup drip failed for user %s", user.id)


async def deliver_drip_event(*, event: str, email: str, payload: dict) -> dict:
    """Send one event to Resend. Worker-side; never raises.

    Resend resolves ``email`` to a contact (creating a global one if it does not
    exist yet), so no contact bookkeeping is needed here.
    """
    if not settings.RESEND_API_KEY:
        # Parity with EmailChannel: no key means delivery is off, not broken.
        logger.info(
            "Drip event %s skipped for %s (RESEND_API_KEY not set)", event, email
        )
        return {"success": False, "disabled": True, "error": "email delivery off"}
    try:
        resend.api_key = settings.RESEND_API_KEY
        response = await resend.Events.send_async(
            {"event": event, "email": email, "payload": payload}
        )
        return {"success": True, "response": response}
    except Exception as e:  # noqa: BLE001 - never let a send break the worker
        logger.error("Drip event %s failed for %s: %s", event, email, e)
        return {"success": False, "error": str(e)}

"""Organization invitation email delivery.

Sends an invitee the link to accept their organization invitation.

The application does not yet have a transactional email provider wired up:
Neon Auth delivers *authentication* email (sign-in codes / magic links) but not
arbitrary content. Until a provider is configured, this module records the
invitation and logs the accept URL instead of delivering it. The invitee can
still sign in via Neon Auth and pick up the pending invite from
``GET /invitations/pending-for-me`` (the accept URL is persisted on the
invitation row for resend bookkeeping).

TODO: wire a real transactional email provider (e.g. Resend / SES / Postmark)
and replace the body of ``send_invitation_email`` with an actual send.

Failures never raise to the caller — they degrade to ``False`` and are logged.
"""

import logging

logger = logging.getLogger(__name__)


async def send_invitation_email(
    email: str,
    accept_url: str,
    organization_name: str,
    inviter_name: str | None = None,
) -> bool:
    """Deliver an organization invitation to ``email``.

    Returns ``True`` when the invite was handed off for delivery. Until a real
    email provider is configured this logs the accept URL and returns ``True``
    so the invitation flow (DB row + pending-invite pickup) is never blocked.
    Never raises.
    """
    try:
        logger.info(
            "Invitation email (no email provider configured — logging only): "
            "email=%s organization=%s accept_url=%s inviter=%s",
            email,
            organization_name,
            accept_url,
            inviter_name or "<unknown>",
        )
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Invitation email failed (email=%s organization=%s): %s",
            email,
            organization_name,
            exc,
        )
        return False

"""Notification fan-out.

Domain code never enqueues delivery jobs directly — it calls a ``notify_*``
helper in ``app.services.notifications``, which calls one of these publishers.
The publishers only enqueue arq jobs (``task_send_notification``); the worker
does the actual channel delivery.
"""

import logging

from sqlalchemy.orm import Session

from app.models.enums import (
    AdminNotificationType,
    CustomerNotificationType,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership
from app.tasks import enqueue_send_notification

logger = logging.getLogger(__name__)

# Roles that receive admin-facing (org-level) notifications. Mirrors the
# manager-app role gate — LPs are excluded.
_ADMIN_ROLES = (UserRole.superadmin, UserRole.admin, UserRole.fund_manager)


async def publish_admin_event(
    db: Session,
    *,
    organization_id: str,
    event_type: AdminNotificationType,
    title: str,
    message: str | None = None,
    data: dict | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> None:
    """Fan an org-level event out to every manager of the organization."""
    admin_links = (
        db.query(UserOrganizationMembership)
        .filter(
            UserOrganizationMembership.organization_id == organization_id,
            UserOrganizationMembership.role.in_(_ADMIN_ROLES),
        )
        .all()
    )
    if not admin_links:
        logger.warning(
            "Admin event %s for org %s has no manager recipients",
            event_type,
            organization_id,
        )
    for link in admin_links:
        await enqueue_send_notification(
            user_id=str(link.user_id),
            organization_id=organization_id,
            notification_type=event_type,
            title=title,
            message=message,
            data=data,
            reference_type=reference_type,
            reference_id=reference_id,
        )


async def publish_customer_event(
    *,
    user_id: str | None,
    organization_id: str | None,
    event_type: CustomerNotificationType,
    title: str,
    message: str | None = None,
    data: dict | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> None:
    """Send a customer-facing notification to a single recipient.

    ``user_id`` may be ``None`` for a recipient with no user account (e.g. an
    invitation to a not-yet-registered address). In that case the worker skips
    the in-app row and delivers email only, to ``data["recipient_email"]``.
    """
    await enqueue_send_notification(
        user_id=user_id,
        organization_id=organization_id,
        notification_type=event_type,
        title=title,
        message=message,
        data=data,
        reference_type=reference_type,
        reference_id=reference_id,
    )

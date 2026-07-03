"""Ad-hoc notification tester.

Fires any registered notification through the real event bus using the first
matching rows already in the database, so you can verify a template renders and
delivers without manufacturing the trigger condition (a real capital call, a
real invitation, …).

    uv run python -m app.scripts.try_notify --list
    uv run python -m app.scripts.try_notify customer.capital_call

The arq worker must be running (``make start-worker``) and ``RESEND_API_KEY``
set for the email to actually leave the box; otherwise the notification is
enqueued and the email channel logs a skipped delivery.
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.capital_call import CapitalCall
from app.models.commitment import Commitment
from app.models.communication import Communication
from app.models.distribution import Distribution
from app.models.document import Document
from app.models.enums import InvitationStatus
from app.models.fund import Fund
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.task import Task
from app.models.user import User
from app.services.notifications import (
    notify_capital_call,
    notify_commitment_status,
    notify_communication,
    notify_distribution,
    notify_document_uploaded,
    notify_invitation,
    notify_invitation_accepted,
    notify_task_assigned,
    notify_welcome,
)


class FixtureMissing(Exception):
    """Raised when the DB has no row to drive a given notification."""


# ===== fixture loaders =====


def _first(query, what: str):
    row = query.first()
    if row is None:
        raise FixtureMissing(f"No {what} found in the database")
    return row


def _first_organization(db: Session) -> Organization:
    return _first(
        db.query(Organization).order_by(Organization.created_at), "organization"
    )


def _first_user(db: Session) -> User:
    return _first(db.query(User).order_by(User.created_at), "user")


def _first_fund(db: Session) -> Fund:
    return _first(db.query(Fund).order_by(Fund.created_at), "fund")


def _first_capital_call(db: Session) -> CapitalCall:
    return _first(
        db.query(CapitalCall).order_by(CapitalCall.created_at), "capital call"
    )


def _first_distribution(db: Session) -> Distribution:
    return _first(
        db.query(Distribution).order_by(Distribution.created_at), "distribution"
    )


def _first_document(db: Session) -> Document:
    return _first(db.query(Document).order_by(Document.created_at), "document")


def _first_commitment(db: Session) -> Commitment:
    return _first(db.query(Commitment).order_by(Commitment.created_at), "commitment")


def _first_task(db: Session) -> Task:
    return _first(
        db.query(Task).filter(Task.assigned_to_user_id.is_not(None)),
        "task with an assignee",
    )


def _first_communication(db: Session) -> Communication:
    return _first(
        db.query(Communication).order_by(Communication.created_at), "communication"
    )


def _first_invitation(db: Session) -> OrganizationInvitation:
    return _first(
        db.query(OrganizationInvitation)
        .filter(OrganizationInvitation.status == InvitationStatus.pending)
        .order_by(OrganizationInvitation.created_at),
        "pending invitation",
    )


# ===== dispatchers =====


async def _send_welcome(db: Session) -> None:
    org = _first_organization(db)
    user = _first_user(db)
    await notify_welcome(db, user=user, organization=org)


async def _send_invitation(db: Session) -> None:
    await notify_invitation(db, invitation=_first_invitation(db))


async def _send_invitation_accepted(db: Session) -> None:
    await notify_invitation_accepted(
        db, invitation=_first_invitation(db), accepted_by=_first_user(db)
    )


async def _send_capital_call(db: Session) -> None:
    await notify_capital_call(db, call=_first_capital_call(db))


async def _send_distribution(db: Session) -> None:
    await notify_distribution(db, distribution=_first_distribution(db))


async def _send_document(db: Session) -> None:
    await notify_document_uploaded(db, document=_first_document(db))


async def _send_commitment_status(db: Session) -> None:
    commitment = _first_commitment(db)
    fund = db.query(Fund).filter(Fund.id == commitment.fund_id).first()
    if fund is None:
        raise FixtureMissing("Commitment has no fund")
    await notify_commitment_status(db, commitment=commitment, fund=fund)


async def _send_task_assigned(db: Session) -> None:
    task = _first_task(db)
    await notify_task_assigned(db, task=task, assignee_user_id=task.assigned_to_user_id)


async def _send_communication(db: Session) -> None:
    await notify_communication(
        db, communication=_first_communication(db), recipient_user_id=_first_user(db).id
    )


DISPATCH: dict[str, Callable[[Session], Awaitable[None]]] = {
    "customer.welcome": _send_welcome,
    "customer.invitation": _send_invitation,
    "admin.invitation_accepted": _send_invitation_accepted,
    "customer.capital_call": _send_capital_call,
    "customer.distribution": _send_distribution,
    "customer.document_uploaded": _send_document,
    "customer.commitment_status": _send_commitment_status,
    "customer.task_assigned": _send_task_assigned,
    "customer.communication": _send_communication,
}


async def _run(notification_type: str) -> None:
    handler = DISPATCH.get(notification_type)
    if handler is None:
        raise SystemExit(
            f"Unknown notification type '{notification_type}'. "
            f"Use --list to see the available types."
        )
    db = SessionLocal()
    try:
        await handler(db)
        print(f"✓ enqueued {notification_type}")
    except FixtureMissing as exc:
        raise SystemExit(f"✗ {exc}") from exc
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fire a test notification.")
    parser.add_argument(
        "type", nargs="?", help="notification type, e.g. customer.welcome"
    )
    parser.add_argument("--list", action="store_true", help="list available types")
    args = parser.parse_args()

    if args.list or not args.type:
        for key in sorted(DISPATCH):
            print(key)
        return

    asyncio.run(_run(args.type))


if __name__ == "__main__":
    main()

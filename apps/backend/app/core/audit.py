"""Audit-log machinery — manual ``record_audit`` plus ORM event listeners.

Every mutation on the entities listed in ``_ENTITY_TYPES`` triggers an
``after_insert`` / ``after_update`` / ``after_delete`` listener that writes a
row to ``audit_logs`` directly via the active DB connection. The actor and the
client identity (IP, country, user agent) are pulled from the request-scoped
``AuditContext`` populated by
``app.middleware.audit_context.AuditContextMiddleware``.

Listeners run inside the same transaction as the originating change, so a
rollback discards both the business write and its audit trail (which is the
correct behaviour — never log work that didn't actually persist).

``record_audit`` exists for the rare case where a route wants to log a
non-DB-mutation event (e.g. a successful login). It commits its own row.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, Session

from app.core.request_context import get_request_context
from app.middleware.audit_context import get_audit_context
from app.models.audit_log import AuditLog
from app.models.bank_payment_transaction import BankPaymentTransaction
from app.models.bank_statement_import import BankStatementImport
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.communication import Communication
from app.models.communication_recipient import CommunicationRecipient
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem
from app.models.document import Document
from app.models.email_ingest_message import EmailIngestMessage
from app.models.fund import Fund
from app.models.fund_group import FundGroup
from app.models.fund_valuation import FundValuation
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.notification import Notification
from app.models.notification_log import NotificationLog
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.task import Task
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership

# Every mapped model is audited. The test suite asserts this map (plus
# _UNAUDITED_MODELS) covers the full ORM registry, so adding a model without
# classifying it here fails loudly instead of silently skipping its trail.
_ENTITY_TYPES: dict[type, str] = {
    Organization: "organization",
    OrganizationInvitation: "invitation",
    User: "user",
    UserOrganizationMembership: "membership",
    Fund: "fund",
    FundGroup: "fund_group",
    FundValuation: "fund_valuation",
    Investor: "investor",
    InvestorContact: "investor_contact",
    Commitment: "commitment",
    CapitalCall: "capital_call",
    CapitalCallItem: "capital_call_item",
    BankStatementImport: "bank_statement_import",
    BankPaymentTransaction: "bank_payment_transaction",
    Distribution: "distribution",
    DistributionItem: "distribution_item",
    Document: "document",
    Communication: "communication",
    CommunicationRecipient: "communication_recipient",
    Task: "task",
    Notification: "notification",
}

# Deliberately not audited: the audit table itself (would recurse), the
# notification delivery log (pure telemetry, one row per send attempt), and
# the email-ingest idempotency log (pure bookkeeping — it has no
# organization_id to attribute an audit row to, and the Document rows it
# references are already audited via the Document listener above).
_UNAUDITED_MODELS: set[type] = {AuditLog, NotificationLog, EmailIngestMessage}

# Skip these columns from diffs — they're maintained by the ORM/db and add
# noise without telling the auditor anything useful.
_DIFF_SKIP_COLUMNS = {"created_at", "updated_at"}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _serialize_metadata(metadata: dict[str, Any] | None) -> str | None:
    if metadata is None:
        return None
    return json.dumps(metadata, default=_json_default)


def _build_diff(target: Any) -> dict[str, dict[str, Any]]:
    state = inspect(target)
    diff: dict[str, dict[str, Any]] = {}
    for attr in state.mapper.column_attrs:
        if attr.key in _DIFF_SKIP_COLUMNS:
            continue
        history = state.attrs[attr.key].history
        if not history.has_changes():
            continue
        before = history.deleted[0] if history.deleted else None
        after = history.added[0] if history.added else None
        diff[attr.key] = {"before": before, "after": after}
    return diff


# Child rows whose fund (and therefore organization) hangs off a parent row.
_FUND_VIA_PARENT = (
    ("capital_call_id", CapitalCall.__table__),
    ("distribution_id", Distribution.__table__),
    ("communication_id", Communication.__table__),
)


def _organization_id_for(connection: Connection, target: Any) -> uuid.UUID | None:
    """Best-effort organization id for the affected row.

    The org-scoped audit view only shows rows whose ``organization_id``
    matches the caller's membership, so attribution matters: rows without a
    direct column resolve through their parent FKs (item → call/distribution/
    communication → fund → organization) with Core selects on the flush
    connection. Rows with no org at all (users, notifications) stay None.
    """
    if isinstance(target, Organization):
        # Events on the organization itself belong to that organization.
        return target.id
    direct = getattr(target, "organization_id", None)
    if direct is not None:
        return direct

    fund_id = getattr(target, "fund_id", None)
    if fund_id is None:
        for parent_attr, parent_table in _FUND_VIA_PARENT:
            parent_id = getattr(target, parent_attr, None)
            if parent_id is not None:
                fund_id = connection.execute(
                    select(parent_table.c.fund_id).where(parent_table.c.id == parent_id)
                ).scalar()
                break
    if fund_id is not None:
        return connection.execute(
            select(Fund.__table__.c.organization_id).where(
                Fund.__table__.c.id == fund_id
            )
        ).scalar()

    investor_id = getattr(target, "investor_id", None)
    if investor_id is not None:
        return connection.execute(
            select(Investor.__table__.c.organization_id).where(
                Investor.__table__.c.id == investor_id
            )
        ).scalar()

    return None


def _entity_id(target: Any) -> uuid.UUID | None:
    return getattr(target, "id", None)


def _write_audit_via_connection(
    connection: Connection,
    *,
    user_id: uuid.UUID | None,
    organization_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    metadata: dict[str, Any] | None,
    ip_address: str | None,
    country: str | None,
    user_agent: str | None,
) -> None:
    # NB: the underlying column is named ``metadata`` (the attribute on the
    # ORM class is ``audit_metadata``, but Table.c.keys() exposes the SQL
    # column name). Pass values keyed by the column name to keep the Core
    # insert happy.
    connection.execute(
        AuditLog.__table__.insert().values(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=_serialize_metadata(metadata),
            ip_address=ip_address,
            country=country,
            user_agent=user_agent,
        )
    )


def record_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    organization_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request: Any = None,
) -> AuditLog:
    """Persist an audit row from non-listener code paths (commits its own row).

    Pull actor + client identity from the explicit ``user`` / ``request``
    arguments when given; otherwise fall back to whatever the request-scoped
    audit context holds. This makes the helper safe to call from background
    jobs that have set the context manually. Users belong to organizations
    only through memberships, so callers that want org attribution pass
    ``organization_id`` explicitly.
    """
    ctx = get_audit_context()
    user_id = user.id if user is not None else ctx.user_id
    ip_address = ctx.ip_address
    country = ctx.country
    user_agent = ctx.user_agent
    if request is not None:
        client = get_request_context(request)
        ip_address = client.ip or ip_address
        country = client.country or country
        user_agent = client.user_agent or user_agent

    log = AuditLog(
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        audit_metadata=_serialize_metadata(metadata),
        ip_address=ip_address,
        country=country,
        user_agent=user_agent,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _make_listener(action: str, with_diff: bool):
    def _listener(mapper: Mapper, connection: Connection, target: Any) -> None:
        entity_type = _ENTITY_TYPES.get(type(target))
        if entity_type is None:
            return
        ctx = get_audit_context()
        metadata: dict[str, Any] | None = None
        if with_diff:
            diff = _build_diff(target)
            if not diff:
                return
            metadata = {"changes": diff}
        _write_audit_via_connection(
            connection,
            user_id=ctx.user_id,
            organization_id=_organization_id_for(connection, target),
            action=action,
            entity_type=entity_type,
            entity_id=_entity_id(target),
            metadata=metadata,
            ip_address=ctx.ip_address,
            country=ctx.country,
            user_agent=ctx.user_agent,
        )

    return _listener


_LISTENERS_REGISTERED = False


def register_audit_listeners() -> None:
    """Idempotently attach SQLAlchemy listeners to the audited models."""
    global _LISTENERS_REGISTERED
    if _LISTENERS_REGISTERED:
        return
    insert_listener = _make_listener("create", with_diff=False)
    update_listener = _make_listener("update", with_diff=True)
    delete_listener = _make_listener("delete", with_diff=False)
    for model_cls in _ENTITY_TYPES:
        event.listen(model_cls, "after_insert", insert_listener)
        event.listen(model_cls, "after_update", update_listener)
        event.listen(model_cls, "after_delete", delete_listener)
    _LISTENERS_REGISTERED = True


register_audit_listeners()

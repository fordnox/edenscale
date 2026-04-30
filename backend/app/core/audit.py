"""Audit-log machinery — manual ``record_audit`` plus ORM event listeners.

Every mutation on the entities listed in ``_AUDITED_MODELS`` triggers an
``after_insert`` / ``after_update`` / ``after_delete`` listener that writes a
row to ``audit_logs`` directly via the active DB connection. The actor and
client IP are pulled from the request-scoped ``AuditContext`` populated by
``app.middleware.audit_context.AuditContextMiddleware``.

Listeners run inside the same transaction as the originating change, so a
rollback discards both the business write and its audit trail (which is the
correct behaviour — never log work that didn't actually persist).

``record_audit`` exists for the rare case where a route wants to log a
non-DB-mutation event (e.g. a successful login). It commits its own row.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, Session

from app.middleware.audit_context import get_audit_context
from app.models.audit_log import AuditLog
from app.models.capital_call import CapitalCall
from app.models.commitment import Commitment
from app.models.communication import Communication
from app.models.distribution import Distribution
from app.models.document import Document
from app.models.fund import Fund
from app.models.organization import Organization
from app.models.task import Task
from app.models.user import User

_ENTITY_TYPES: dict[type, str] = {
    Organization: "organization",
    User: "user",
    Fund: "fund",
    Commitment: "commitment",
    CapitalCall: "capital_call",
    Distribution: "distribution",
    Document: "document",
    Communication: "communication",
    Task: "task",
}

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


def _organization_id_for(target: Any) -> int | None:
    """Best-effort organization id for the affected row."""
    return getattr(target, "organization_id", None)


def _entity_id(target: Any) -> int | None:
    return getattr(target, "id", None)


def _write_audit_via_connection(
    connection: Connection,
    *,
    user_id: int | None,
    organization_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    metadata: dict[str, Any] | None,
    ip_address: str | None,
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
        )
    )


def record_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    metadata: dict[str, Any] | None = None,
    request: Any = None,
) -> AuditLog:
    """Persist an audit row from non-listener code paths (commits its own row).

    Pull actor + IP from the explicit ``user`` / ``request`` arguments when
    given; otherwise fall back to whatever the request-scoped audit context
    holds. This makes the helper safe to call from background jobs that have
    set the context manually.
    """
    ctx = get_audit_context()
    user_id = user.id if user is not None else ctx.user_id
    organization_id = user.organization_id if user is not None else None
    ip_address = ctx.ip_address
    if request is not None:
        client = getattr(request, "client", None)
        ip_address = client.host if client else ip_address

    log = AuditLog(
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        audit_metadata=_serialize_metadata(metadata),
        ip_address=ip_address,
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
            organization_id=_organization_id_for(target),
            action=action,
            entity_type=entity_type,
            entity_id=_entity_id(target),
            metadata=metadata,
            ip_address=ctx.ip_address,
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

"""Request-scoped context that the audit-log listener reads from.

The SQLAlchemy event listeners in ``app.core.audit`` need to know *who* is
making the change, and from *where*, without taking a hard dependency on the
request object. We expose the actor (``user_id``) and the client identity
(``ip_address``, ``country``, ``user_agent``) through a
``contextvars.ContextVar`` so the listener can pull them off the running
context regardless of the call site (HTTP request, worker job, CLI, etc.).

The middleware initialises a fresh ``AuditContext`` for each request from
``app.core.request_context`` (Cloudflare edge headers, falling back to the
socket peer); the user id is filled in later by ``get_current_user_record``
once auth has resolved the local user row.
"""

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.request_context import get_request_context


@dataclass
class AuditContext:
    user_id: uuid.UUID | None = None
    ip_address: str | None = None
    country: str | None = None
    user_agent: str | None = None


_EMPTY = AuditContext()
_audit_context: ContextVar[AuditContext] = ContextVar("_audit_context", default=_EMPTY)


def get_audit_context() -> AuditContext:
    """Return the current request's audit context (or an empty one)."""
    return _audit_context.get()


def set_audit_context(
    *,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    country: str | None = None,
    user_agent: str | None = None,
) -> Token:
    """Replace the current context. Returns a token suitable for ``reset``."""
    return _audit_context.set(
        AuditContext(
            user_id=user_id,
            ip_address=ip_address,
            country=country,
            user_agent=user_agent,
        )
    )


def set_audit_user(user_id: uuid.UUID | None) -> None:
    """Backfill the actor id on the current context (mutates in place)."""
    ctx = _audit_context.get()
    if ctx is _EMPTY:
        _audit_context.set(AuditContext(user_id=user_id))
        return
    ctx.user_id = user_id


def reset_audit_context(token: Token) -> None:
    _audit_context.reset(token)


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Set a fresh ``AuditContext`` for the duration of the request."""

    async def dispatch(self, request: Request, call_next):
        client = get_request_context(request)
        token = _audit_context.set(
            AuditContext(
                user_id=None,
                ip_address=client.ip,
                country=client.country,
                user_agent=client.user_agent,
            )
        )
        try:
            return await call_next(request)
        finally:
            _audit_context.reset(token)

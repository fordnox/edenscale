"""Request correlation id, propagated across the request -> worker boundary.

Mirrors the ``contextvars`` pattern in ``audit_context.py``: a per-request id
is read from (or generated for) the inbound request by ``RequestIdMiddleware``,
stashed in a ``ContextVar`` for the duration of the request, and echoed back on
the response. A logging filter (``RequestIdFilter``) stamps every log record
emitted while that context is active with the same id.

The same contextvar is reused on the worker side: ``app.tasks.enqueue_task``
copies ``get_request_id()`` into the arq job kwargs for jobs that opt in (see
``enqueue_draft_letter``), and the worker restores it via ``set_request_id``
before running the job body. That's what lets a log line emitted deep inside
an arq job be traced back to the HTTP request that enqueued it -- e.g. "why
didn't this LP get an email" starts from the request id on that request, not
from grepping timestamps.
"""

import logging
import uuid
from contextvars import ContextVar, Token

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_ID_HEADER = "X-Request-ID"

# Cap on an inbound id we didn't generate ourselves -- a request id is only
# ever logged and echoed back, never parsed, but an unbounded caller-supplied
# header is still a cheap thing to bound.
_MAX_LEN = 200

_request_id: ContextVar[str | None] = ContextVar("_request_id", default=None)


def get_request_id() -> str | None:
    """Return the current request/job's correlation id, or ``None``."""
    return _request_id.get()


def set_request_id(request_id: str | None) -> Token:
    """Set the current context's request id, generating one if absent/blank.

    Returns a token suitable for :func:`reset_request_id`.
    """
    value = (request_id or "").strip()[:_MAX_LEN] or str(uuid.uuid4())
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    """Stamp every log record with the current request id (or ``"-"``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Set a fresh request id for the duration of the request.

    Registered outermost (see ``app.main``) so the id is available before any
    other middleware or route code runs a log statement, and echoed back to
    the caller on ``X-Request-ID`` so client-side logs can be cross-referenced
    too.
    """

    async def dispatch(self, request: Request, call_next):
        token = set_request_id(request.headers.get(REQUEST_ID_HEADER))
        request_id = get_request_id()
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

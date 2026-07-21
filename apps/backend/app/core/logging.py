"""Root logging configuration.

Every module in this codebase calls ``logging.getLogger(__name__)``, but
nothing ever configured a handler/formatter -- log lines only appeared at all
because of whatever ambient config the process happened to have (uvicorn's,
or none). ``configure_logging`` sets up one root handler whose format includes
the request-correlation id from ``app.middleware.request_id``, so every line
emitted while a request (or a worker job carrying that request's id) is in
flight can be grepped by id.

Idempotent and additive: it only adds a handler to the root logger, it never
removes existing ones, so it can't clobber a handler pytest's own logging
plugin (or ``caplog``) has attached.
"""

import logging

from app.middleware.request_id import RequestIdFilter

_LOG_FORMAT = (
    "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s: %(message)s"
)

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once, with the request id on every line.

    Safe to call more than once (e.g. across test modules that re-import
    ``app.main``) -- only the first call has any effect.
    """
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    _configured = True

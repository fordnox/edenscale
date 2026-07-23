"""Per-request client context resolved from Cloudflare-injected headers.

Cloudflare adds these headers to every request that passes through its edge:

* ``CF-Connecting-IP`` — the original client IP
* ``CF-IPCountry`` — ISO 3166-1 alpha-2 country code (or ``XX`` / ``T1`` for
  unknown / Tor)

``api.newtaven.com`` is proxied through Cloudflare, so production traffic
always carries them. Local dev and tests bypass CF, so we fall back to
``request.client.host`` for the IP and leave the country empty.

Caveat worth knowing: these headers are only trustworthy because Cloudflare
overwrites them at the edge. A client that reaches the origin host directly
(bypassing the proxy) can set them to anything, which would poison the IP /
country on audit rows — it grants no additional access. Locking the origin
down to Cloudflare's IP ranges at the firewall is the fix if that matters.

Usage::

    from app.core.request_context import get_request_context

    ctx = get_request_context(request)
    record_audit(..., ip_address=ctx.ip, country=ctx.country)
"""

from dataclasses import dataclass

from starlette.requests import Request

# audit_logs.user_agent is capped at this width; truncate rather than let a
# pathological UA string blow up the insert.
_MAX_USER_AGENT = 400


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Client identity headers resolved for the current request."""

    ip: str | None
    country: str | None
    user_agent: str | None


def get_request_context(request: Request) -> RequestContext:
    """Read CF-Connecting-IP / CF-IPCountry / User-Agent from a request.

    Falls back to the direct socket peer when ``CF-Connecting-IP`` is absent
    (local dev, tests, or any traffic that did not transit Cloudflare).
    """
    ip = request.headers.get("CF-Connecting-IP")
    if not ip and request.client:
        ip = request.client.host
    country = request.headers.get("CF-IPCountry")
    user_agent = request.headers.get("user-agent")
    if user_agent:
        user_agent = user_agent[:_MAX_USER_AGENT]
    return RequestContext(
        ip=ip or None,
        country=country or None,
        user_agent=user_agent or None,
    )

"""Tests for the Cloudflare-header client context.

``app.core.request_context`` is the single place that decides what counts as
"the client" for audit rows: the CF edge headers when the request came through
Cloudflare, the socket peer otherwise.
"""

from starlette.datastructures import Address, Headers
from starlette.requests import Request

from app.core.request_context import get_request_context


def _request(headers: dict[str, str], *, client: tuple[str, int] | None = None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": Headers(headers).raw,
        "client": Address(*client) if client else None,
    }
    return Request(scope)


class TestGetRequestContext:
    def test_prefers_cloudflare_headers(self):
        ctx = get_request_context(
            _request(
                {
                    "cf-connecting-ip": "203.0.113.7",
                    "cf-ipcountry": "EE",
                    "user-agent": "Mozilla/5.0",
                },
                client=("10.0.0.1", 51234),
            )
        )
        assert ctx.ip == "203.0.113.7"
        assert ctx.country == "EE"
        assert ctx.user_agent == "Mozilla/5.0"

    def test_falls_back_to_socket_peer(self):
        ctx = get_request_context(_request({}, client=("10.0.0.1", 51234)))
        assert ctx.ip == "10.0.0.1"
        assert ctx.country is None
        assert ctx.user_agent is None

    def test_no_client_and_no_headers_is_all_none(self):
        ctx = get_request_context(_request({}))
        assert ctx.ip is None
        assert ctx.country is None
        assert ctx.user_agent is None

    def test_empty_headers_are_normalised_to_none(self):
        ctx = get_request_context(
            _request({"cf-connecting-ip": "", "cf-ipcountry": "", "user-agent": ""})
        )
        assert ctx.ip is None
        assert ctx.country is None
        assert ctx.user_agent is None

    def test_user_agent_is_truncated_to_column_width(self):
        ctx = get_request_context(_request({"user-agent": "u" * 900}))
        assert ctx.user_agent is not None
        assert len(ctx.user_agent) == 400

    def test_tor_country_code_passes_through(self):
        # Cloudflare uses T1 for Tor exit nodes and XX when it cannot resolve
        # the country; both are legitimate two-letter values to store.
        ctx = get_request_context(_request({"cf-ipcountry": "T1"}))
        assert ctx.country == "T1"

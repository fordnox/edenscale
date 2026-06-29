"""Unit tests for the Hanko invitation email service.

The service must never raise; failures degrade to ``False`` and are logged so
the admin can resend. We patch ``httpx.AsyncClient`` at the service-module
boundary to avoid hitting the real Hanko API.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import hanko


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeResponse:
    def __init__(
        self, status_code: int = 200, json_data: Any = None, raise_exc: bool = False
    ):
        self.status_code = status_code
        self._json_data = json_data
        self._raise_exc = raise_exc

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self._raise_exc or self.status_code >= 400:
            request = httpx.Request("POST", "https://example.invalid")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=request, response=response
            )


class _FakeAsyncClient:
    """Drop-in replacement for httpx.AsyncClient that hands back queued responses."""

    def __init__(self, get_response=None, post_responses=None):
        self.get_response = get_response
        self.post_responses = list(post_responses or [])
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, url, headers=None, params=None):
        self.get_calls.append((url, {"headers": headers, "params": params}))
        return self.get_response

    async def post(self, url, headers=None, json=None):
        self.post_calls.append((url, {"headers": headers, "json": json}))
        if not self.post_responses:
            raise AssertionError(f"unexpected POST {url}")
        return self.post_responses.pop(0)


@pytest.fixture
def hanko_settings(monkeypatch):
    monkeypatch.setattr(hanko.settings, "HANKO_API_URL", "https://tenant.hanko.io")
    monkeypatch.setattr(hanko.settings, "HANKO_API_KEY", "test-secret")


def test_returns_false_when_unconfigured(monkeypatch, caplog):
    monkeypatch.setattr(hanko.settings, "HANKO_API_URL", "")
    monkeypatch.setattr(hanko.settings, "HANKO_API_KEY", "")

    with caplog.at_level("WARNING"):
        result = _run(
            hanko.send_invitation_email(
                email="invitee@example.com",
                accept_url="https://app.example.com/invitations/accept?token=t",
                organization_name="Acme",
                inviter_name="Alice",
            )
        )

    assert result is False
    assert any("not configured" in record.message for record in caplog.records)


def test_existing_user_triggers_passcode(hanko_settings):
    user = {
        "id": "user-uuid",
        "emails": [{"id": "email-uuid", "address": "Invitee@Example.com"}],
    }
    fake = _FakeAsyncClient(
        get_response=_FakeResponse(json_data=[user]),
        post_responses=[_FakeResponse(json_data={"id": "passcode"})],
    )

    with patch.object(hanko.httpx, "AsyncClient", return_value=fake):
        result = _run(
            hanko.send_invitation_email(
                email="invitee@example.com",
                accept_url="https://app/invitations/accept?token=tok",
                organization_name="Acme",
            )
        )

    assert result is True
    assert len(fake.post_calls) == 1
    passcode_url, passcode_kwargs = fake.post_calls[0]
    assert passcode_url == "https://tenant.hanko.io/passcode/login/initialize"
    assert passcode_kwargs["json"] == {
        "user_id": "user-uuid",
        "email_id": "email-uuid",
    }
    get_url, get_kwargs = fake.get_calls[0]
    assert get_url == "https://tenant.hanko.io/admin/users"
    assert get_kwargs["params"] == {"email": "invitee@example.com", "per_page": 1}
    assert get_kwargs["headers"]["Authorization"] == "Bearer test-secret"


def test_missing_user_is_created_then_passcode_sent(hanko_settings):
    created_user = {
        "id": "new-user-uuid",
        "emails": [{"id": "new-email-uuid", "address": "new@example.com"}],
    }
    fake = _FakeAsyncClient(
        get_response=_FakeResponse(json_data=[]),
        post_responses=[
            _FakeResponse(status_code=200, json_data=created_user),
            _FakeResponse(status_code=200, json_data={}),
        ],
    )

    with patch.object(hanko.httpx, "AsyncClient", return_value=fake):
        result = _run(
            hanko.send_invitation_email(
                email="new@example.com",
                accept_url="https://app/invitations/accept?token=t2",
                organization_name="Acme",
                inviter_name="Bob",
            )
        )

    assert result is True
    assert len(fake.post_calls) == 2
    create_url, create_kwargs = fake.post_calls[0]
    assert create_url == "https://tenant.hanko.io/admin/users"
    assert create_kwargs["json"] == {
        "emails": [
            {"address": "new@example.com", "is_primary": True, "is_verified": False}
        ]
    }


def test_create_409_falls_back_to_lookup(hanko_settings):
    existing_user = {
        "id": "existing-uuid",
        "emails": [{"id": "existing-email", "address": "race@example.com"}],
    }
    # First GET (initial lookup) returns empty, then POST /admin/users 409s,
    # then a second GET returns the existing record.
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.get = AsyncMock(
        side_effect=[
            _FakeResponse(json_data=[]),
            _FakeResponse(json_data=[existing_user]),
        ]
    )
    fake.post = AsyncMock(
        side_effect=[
            _FakeResponse(status_code=409),
            _FakeResponse(status_code=200, json_data={}),
        ]
    )

    with patch.object(hanko.httpx, "AsyncClient", return_value=fake):
        result = _run(
            hanko.send_invitation_email(
                email="race@example.com",
                accept_url="https://app/invitations/accept?token=t3",
                organization_name="Acme",
            )
        )

    assert result is True
    assert fake.get.await_count == 2
    assert fake.post.await_count == 2


def test_http_error_returns_false(hanko_settings, caplog):
    fake = _FakeAsyncClient(
        get_response=_FakeResponse(status_code=500, raise_exc=True)
    )

    with patch.object(hanko.httpx, "AsyncClient", return_value=fake):
        with caplog.at_level("ERROR"):
            result = _run(
                hanko.send_invitation_email(
                    email="boom@example.com",
                    accept_url="https://app/invitations/accept?token=t4",
                    organization_name="Acme",
                )
            )

    assert result is False
    assert any("Hanko invitation email failed" in r.message for r in caplog.records)


def test_request_error_returns_false(hanko_settings, caplog):
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.get = AsyncMock(side_effect=httpx.ConnectError("boom"))

    with patch.object(hanko.httpx, "AsyncClient", return_value=fake):
        with caplog.at_level("ERROR"):
            result = _run(
                hanko.send_invitation_email(
                    email="net@example.com",
                    accept_url="https://app/invitations/accept?token=t5",
                    organization_name="Acme",
                )
            )

    assert result is False
    assert any("Hanko invitation email failed" in r.message for r in caplog.records)

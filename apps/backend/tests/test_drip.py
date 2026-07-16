"""Tests for the investor onboarding drip (``app.services.drip``).

The drip fires a Resend ``investor.signup`` event; Resend's "Investor Drip"
automation owns the seven-day schedule. These tests never reach the network:
``RESEND_API_KEY`` is empty in tests (see conftest), and the enqueue is patched
inline, so what's asserted is the payload we hand Resend and who gets it.
"""

import asyncio
import uuid

import pytest

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.models import Organization, OrganizationType, User
from app.services.drip import (
    INVESTOR_SIGNUP_EVENT,
    deliver_drip_event,
    fire_investor_signup,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed(first_name: str = "Priya", website: str | None = "https://nt.example"):
    db = SessionLocal()
    try:
        org = Organization(
            name="NewTaven Capital",
            slug=slugify(f"NewTaven Capital {uuid.uuid4()}"),
            type=OrganizationType.fund_manager_firm,
            website=website,
        )
        db.add(org)
        db.flush()
        user = User(
            email="lp@example.com",
            first_name=first_name,
            last_name="Anand",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(org)
        db.refresh(user)
        db.expunge_all()
        return org, user
    finally:
        db.close()


@pytest.fixture
def captured(monkeypatch):
    """Capture what would be enqueued, instead of running it inline."""
    calls: list[dict] = []

    async def _capture(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.services.drip.enqueue_drip_event", _capture, raising=True)
    return calls


class TestFireInvestorSignup:
    def test_enqueues_event_with_template_variables(self, captured, monkeypatch):
        monkeypatch.setattr(settings, "APP_DOMAIN", "localhost")
        org, user = _seed()

        _run(fire_investor_signup(user=user, organization=org))

        assert len(captured) == 1
        assert captured[0]["event"] == INVESTOR_SIGNUP_EVENT
        assert captured[0]["email"] == "lp@example.com"
        # Exactly the variables the day_*.tsx templates declare — a missing key
        # renders as an empty placeholder in the sent email.
        assert captured[0]["payload"] == {
            "recipient_name": "Priya",
            "app_url": "http://localhost:3000/investor",
            "organization_name": "NewTaven Capital",
            "organization_website": "https://nt.example",
        }

    def test_falls_back_when_name_and_website_are_missing(self, captured):
        # first_name is NOT NULL, so blank is the real-world empty case.
        org, user = _seed(first_name="  ", website=None)

        _run(fire_investor_signup(user=user, organization=org))

        payload = captured[0]["payload"]
        assert payload["recipient_name"] == "there"
        # Nullable column: the footer renders the empty string, not "None".
        assert payload["organization_website"] == ""

    def test_never_raises_when_enqueue_fails(self, monkeypatch):
        """A drip failure must not break the invitation-accept write."""
        org, user = _seed()

        async def _boom(**kwargs):
            raise RuntimeError("redis is down")

        monkeypatch.setattr("app.services.drip.enqueue_drip_event", _boom, raising=True)

        _run(fire_investor_signup(user=user, organization=org))

    def test_skips_user_without_email(self, captured):
        org, user = _seed()
        user.email = None

        _run(fire_investor_signup(user=user, organization=org))

        assert captured == []


class TestDeliverDripEvent:
    def test_does_not_send_without_api_key(self):
        """Email delivery off (no key) is a skip, not a failure."""
        result = _run(
            deliver_drip_event(
                event=INVESTOR_SIGNUP_EVENT, email="lp@example.com", payload={}
            )
        )
        assert result == {
            "success": False,
            "disabled": True,
            "error": "email delivery off",
        }

    def test_reports_provider_failure_without_raising(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")

        async def _boom(_params):
            raise RuntimeError("resend is down")

        monkeypatch.setattr("resend.Events.send_async", _boom, raising=True)

        result = _run(
            deliver_drip_event(
                event=INVESTOR_SIGNUP_EVENT, email="lp@example.com", payload={}
            )
        )
        assert result["success"] is False
        assert "resend is down" in result["error"]

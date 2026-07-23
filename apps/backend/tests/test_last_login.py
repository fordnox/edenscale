"""Tests for last-login tracking.

Auth is stateless Hanko JWTs — there is no login endpoint — so
``get_current_user`` (app/core/auth.py) stamps ``User.last_login_at`` on
every authenticated request via ``UserRepository.touch_last_login``, which
throttles the write to at most one per ``min_interval``. These tests cover:

* First touch sets the timestamp.
* A touch within the interval is read-only (timestamp unchanged).
* A stale timestamp is refreshed.
* The full request path — ``get_current_user`` with a (faked) verified JWT —
  persists the stamp, since route tests elsewhere override the dependency
  and never exercise this.
* A moved stamp writes exactly one ``login`` audit row carrying the client's
  Cloudflare-resolved IP, country and user agent.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core import auth as auth_module
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog, User
from app.repositories.user_repository import UserRepository


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_user(
    subject_id: str = "hanko-touch",
    *,
    email: str = "touch@example.com",
    last_login_at: datetime | None = None,
) -> str:
    db = SessionLocal()
    try:
        user = User(
            first_name="First",
            last_name="Last",
            email=email,
            hanko_subject_id=subject_id,
            last_login_at=last_login_at,
        )
        db.add(user)
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _load_last_login(user_id: str) -> datetime | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).one()
        return user.last_login_at
    finally:
        db.close()


class TestTouchLastLogin:
    def test_first_touch_sets_timestamp(self):
        user_id = _seed_user()
        assert _load_last_login(user_id) is None

        db = SessionLocal()
        try:
            repo = UserRepository(db)
            user = repo.get_by_id(uuid.UUID(user_id))
            repo.touch_last_login(user)
        finally:
            db.close()

        assert _load_last_login(user_id) is not None

    def test_within_interval_is_read_only(self):
        recent = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        user_id = _seed_user(last_login_at=recent)

        db = SessionLocal()
        try:
            repo = UserRepository(db)
            user = repo.get_by_id(uuid.UUID(user_id))
            repo.touch_last_login(user, min_interval=timedelta(minutes=15))
        finally:
            db.close()

        assert _load_last_login(user_id) == recent

    def test_stale_timestamp_is_refreshed(self):
        stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        user_id = _seed_user(last_login_at=stale)

        db = SessionLocal()
        try:
            repo = UserRepository(db)
            user = repo.get_by_id(uuid.UUID(user_id))
            repo.touch_last_login(user, min_interval=timedelta(minutes=15))
        finally:
            db.close()

        refreshed = _load_last_login(user_id)
        assert refreshed is not None
        assert refreshed > stale


class TestGetCurrentUserStampsLastLogin:
    def test_authenticated_request_persists_last_login(self, monkeypatch):
        user_id = _seed_user(subject_id="hanko-live", email="live@example.com")
        assert _load_last_login(user_id) is None

        async def _fake_verify(token: str) -> dict:
            return {"sub": "hanko-live", "email": "live@example.com"}

        monkeypatch.setattr(auth_module, "verify_hanko_token", _fake_verify)

        client = TestClient(app)
        response = client.get(
            "/users/me", headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200
        assert response.json()["last_login_at"] is not None

        assert _load_last_login(user_id) is not None


class TestLoginAuditTrail:
    """A moved ``last_login_at`` stamp is the sign-in edge — it writes one
    audit row carrying the Cloudflare-resolved IP and country."""

    def _sign_in(self, monkeypatch, *, headers: dict[str, str]) -> None:
        async def _fake_verify(token: str) -> dict:
            return {"sub": "hanko-trail", "email": "trail@example.com"}

        monkeypatch.setattr(auth_module, "verify_hanko_token", _fake_verify)
        client = TestClient(app)
        response = client.get(
            "/users/me",
            headers={"Authorization": "Bearer test-token", **headers},
        )
        assert response.status_code == 200

    def _login_rows(self) -> list[AuditLog]:
        db = SessionLocal()
        try:
            return (
                db.query(AuditLog)
                .filter(AuditLog.action == "login")
                .order_by(AuditLog.created_at)
                .all()
            )
        finally:
            db.close()

    def test_sign_in_records_ip_and_country(self, monkeypatch):
        user_id = _seed_user(subject_id="hanko-trail", email="trail@example.com")
        self._sign_in(
            monkeypatch,
            headers={
                "CF-Connecting-IP": "203.0.113.7",
                "CF-IPCountry": "EE",
                "User-Agent": "Mozilla/5.0 (Macintosh)",
            },
        )

        rows = self._login_rows()
        assert len(rows) == 1
        assert str(rows[0].user_id) == user_id
        assert rows[0].entity_type == "user"
        assert rows[0].ip_address == "203.0.113.7"
        assert rows[0].country == "EE"
        assert rows[0].user_agent == "Mozilla/5.0 (Macintosh)"

    def test_second_request_in_window_does_not_duplicate(self, monkeypatch):
        _seed_user(subject_id="hanko-trail", email="trail@example.com")
        self._sign_in(monkeypatch, headers={"CF-IPCountry": "EE"})
        self._sign_in(monkeypatch, headers={"CF-IPCountry": "EE"})

        assert len(self._login_rows()) == 1

    def test_new_window_records_a_fresh_login(self, monkeypatch):
        stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        _seed_user(
            subject_id="hanko-trail",
            email="trail@example.com",
            last_login_at=stale,
        )
        self._sign_in(monkeypatch, headers={"CF-IPCountry": "DE"})

        rows = self._login_rows()
        assert len(rows) == 1
        assert rows[0].country == "DE"

"""Pytest bootstrap.

Rewrites ``APP_DATABASE_DSN`` so tests always run against a sibling database
named ``<db>_test`` instead of whatever ``.env`` points at. This runs at
conftest import time — before any ``app.*`` module is imported — so
``pydantic-settings`` picks up the overridden env var when ``Settings`` is
first instantiated (env vars take precedence over ``.env``).
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url


def _load_env_dsn() -> str:
    """Read ``APP_DATABASE_DSN`` without importing ``app.core.config``."""
    if "APP_DATABASE_DSN" in os.environ:
        return os.environ["APP_DATABASE_DSN"]
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "APP_DATABASE_DSN":
                return value.strip().strip('"').strip("'")
    # PostgreSQL is required — fail loudly at collection time instead of
    # silently falling back to a SQLite DSN that produces a confusing wall of
    # unrelated test failures (SQLite's stricter binder rejects the plain
    # ``str`` values many fixtures pass into ``Uuid(as_uuid=True)`` columns).
    raise RuntimeError(
        "APP_DATABASE_DSN is not set. PostgreSQL is required to run the test "
        "suite: set APP_DATABASE_DSN in your environment, or copy "
        "apps/backend/.env.example to apps/backend/.env and fill it in."
    )


def _rewrite_to_test(dsn: str) -> str:
    url = make_url(dsn)
    db = url.database
    if not db:
        return dsn
    new_db = db if db.endswith("_test") else f"{db}_test"
    return url.set(database=new_db).render_as_string(hide_password=False)


_TEST_DSN = _rewrite_to_test(_load_env_dsn())
os.environ["APP_DATABASE_DSN"] = _TEST_DSN

# Superadmins are config-defined (SUPERADMIN_EMAIL); force the set empty so a
# developer's .env can't leak superadmin powers into tests. Tests opt in by
# monkeypatching ``settings.SUPERADMIN_EMAIL``.
os.environ["SUPERADMIN_EMAIL"] = ""

# Email delivery is meant to be off in tests (the channel no-ops without a key,
# and the drip fires no Resend events). A developer's .env has a real key, which
# without this made the suite send live mail to @example.com recipients — hard
# bounces that damage the sending domain's reputation. Tests that assert on
# delivery opt in by monkeypatching ``settings.RESEND_API_KEY``.
os.environ["RESEND_API_KEY"] = ""

# The Settings validator refuses to construct in a production-shaped config
# (DEBUG=false and APP_DOMAIN not localhost) with certain settings unset —
# see app/core/config.py. Environments with no .env (CI, a fresh git
# worktree) have no APP_DOMAIN at all, which defaults to "example.com" and
# trips that validator. Force localhost so the suite is self-contained.
os.environ["APP_DOMAIN"] = "localhost"


def _ensure_test_database() -> None:
    """Create the ``_test`` database if it does not yet exist."""
    url = make_url(_TEST_DSN)
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


_ensure_test_database()


# ---------------------------------------------------------------------------
# Shared fixtures. Imported below the env rewrite above so ``app.*`` modules
# pick up the overridden ``APP_DATABASE_DSN`` when first imported.
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from fastapi import HTTPException, status  # noqa: E402

from app.core.auth import get_current_user  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402


@pytest.fixture
def override_user():
    """Override the auth dependency so routes resolve a real local ``User``.

    ``get_current_user`` returns the provisioned ``User`` row (not a JWT
    payload), so this resolves — or auto-provisions on first sign-in — the user
    for the given Hanko subject through the same repository path production
    uses. An explicit ``email`` is honoured (and may bind a pre-seeded,
    subject-less row); otherwise a new subject is provisioned with a synthetic
    address while existing rows are returned untouched. The backing session is
    kept open until teardown so the returned instance stays attached while the
    request is served.
    """
    sessions: list = []

    def _set(subject_id: str | None, *, email: str | None = None) -> None:
        if subject_id is None:

            def _missing() -> User:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            app.dependency_overrides[get_current_user] = _missing
            return

        def _resolve() -> User:
            db = SessionLocal()
            sessions.append(db)
            existing = (
                db.query(User).filter(User.hanko_subject_id == subject_id).first()
            )
            resolved_email = email
            if existing is None and resolved_email is None:
                resolved_email = f"{subject_id}@example.com"
            user, _ = UserRepository(db).get_or_provision_by_hanko_id(
                hanko_id=subject_id,
                email=resolved_email,
            )
            return user

        app.dependency_overrides[get_current_user] = _resolve

    yield _set
    app.dependency_overrides.clear()
    for db in sessions:
        db.close()


@pytest.fixture(autouse=True)
def deliver_notifications_inline(monkeypatch):
    """Deliver enqueued notifications synchronously in tests.

    In production a ``notify_*`` helper enqueues ``task_send_notification`` and
    the arq worker writes the in-app row + delivery log. There is no worker or
    Redis in tests, so patch the event bus's enqueue to run the worker task
    inline — the pipeline (fan-out → in-app row → email channel → log) is
    exercised end-to-end, and the email channel no-ops without a Resend key.
    """
    from app import worker

    async def _inline(**kwargs):
        kwargs["notification_type"] = str(kwargs["notification_type"])
        await worker.task_send_notification({}, **kwargs)
        return None

    monkeypatch.setattr(
        "app.core.event_bus.enqueue_send_notification", _inline, raising=True
    )


@pytest.fixture(autouse=True)
def deliver_drip_events_inline(monkeypatch):
    """Run enqueued drip events synchronously in tests.

    Same reasoning as :func:`deliver_notifications_inline`: there is no Redis in
    tests, and without this the request-path enqueue would burn its timeout on
    every LP invitation-accept. Patched where ``app.services.drip`` imported the
    name, so the service's own payload-building still runs.
    """
    from app import worker

    async def _inline(**kwargs):
        await worker.task_fire_drip_event({}, **kwargs)
        return None

    monkeypatch.setattr("app.services.drip.enqueue_drip_event", _inline, raising=True)

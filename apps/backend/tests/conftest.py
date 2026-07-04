"""Pytest bootstrap.

Rewrites ``APP_DATABASE_DSN`` so tests always run against a sibling database
named ``<db>_test`` instead of whatever ``.env`` points at. This runs at
conftest import time — before any ``app.*`` module is imported — so
``pydantic-settings`` picks up the overridden env var when ``Settings`` is
first instantiated (env vars take precedence over ``.env``).
"""

import os
from pathlib import Path, PurePath

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
    return "sqlite:////tmp/database.db"


def _rewrite_to_test(dsn: str) -> str:
    url = make_url(dsn)
    db = url.database
    if not db:
        return dsn
    if url.drivername.startswith("sqlite"):
        # /tmp/database.db -> /tmp/database_test.db
        p = PurePath(db)
        stem = p.stem
        if stem.endswith("_test"):
            new_db = db
        else:
            new_db = str(p.with_name(f"{stem}_test{p.suffix}"))
    else:
        new_db = db if db.endswith("_test") else f"{db}_test"
    return url.set(database=new_db).render_as_string(hide_password=False)


_TEST_DSN = _rewrite_to_test(_load_env_dsn())
os.environ["APP_DATABASE_DSN"] = _TEST_DSN

# Superadmins are config-defined (SUPERADMIN_EMAIL); force the set empty so a
# developer's .env can't leak superadmin powers into tests. Tests opt in by
# monkeypatching ``settings.SUPERADMIN_EMAIL``.
os.environ["SUPERADMIN_EMAIL"] = ""


def _ensure_test_database() -> None:
    """Create the ``_test`` database if it does not yet exist (Postgres only)."""
    url = make_url(_TEST_DSN)
    if not url.drivername.startswith("postgresql"):
        return
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

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

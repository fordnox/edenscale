"""Tests for the local dev storage backend and its ``/dev-storage`` routes.

Modeled on ``tests/test_storage_s3.py``. The load-bearing assertions are the
traversal-key cases: ``LocalDevStorage`` must *raise* rather than silently
return ``None`` (a ``None`` return would look like a pass while leaving the
underlying ``path.exists()`` check reachable outside the storage root).
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.storage import LocalDevStorage, reset_storage


@pytest.fixture
def local_storage(tmp_path):
    """A ``LocalDevStorage`` rooted at a throwaway ``tmp_path`` directory.

    Never touches the real ``dev_storage`` directory on disk.
    """
    return LocalDevStorage(base_dir=tmp_path, base_url="http://testserver")


class TestLocalDevStorageRoundTrip:
    def test_write_read_delete_round_trip(self, local_storage):
        local_storage.write("documents/abc/report.pdf", b"%PDF-1.7")

        assert local_storage.read("documents/abc/report.pdf") == b"%PDF-1.7"

        local_storage.delete("documents/abc/report.pdf")
        assert local_storage.read("documents/abc/report.pdf") is None

    def test_read_missing_key_returns_none(self, local_storage):
        assert local_storage.read("documents/nope/missing.pdf") is None

    def test_delete_missing_key_is_a_no_op(self, local_storage):
        # Deletes are best-effort cleanup after the DB row is gone — must not
        # raise for an object that was never written.
        local_storage.delete("documents/nope/missing.pdf")


class TestLocalDevStorageTraversal:
    """Regression tests for the path-traversal vulnerability.

    ``pathlib`` does not normalize ``..`` segments, so a bare
    ``self.base_dir / key`` join lets a key like ``../../etc/passwd`` resolve
    outside the storage root. ``_resolve`` must reject that by raising, not
    by returning ``None`` — a ``None`` return still exercises the vulnerable
    ``path.exists()`` call underneath and would only *look* like a fix.
    """

    def test_read_with_traversal_key_raises(self, local_storage):
        with pytest.raises(ValueError):
            local_storage.read("../../etc/passwd")

    def test_write_with_traversal_key_raises(self, local_storage):
        with pytest.raises(ValueError):
            local_storage.write("../../etc/passwd", b"pwned")

    def test_delete_with_traversal_key_raises(self, local_storage):
        with pytest.raises(ValueError):
            local_storage.delete("../../etc/passwd")

    def test_absolute_path_key_raises(self, local_storage):
        with pytest.raises(ValueError):
            local_storage.read("/etc/passwd")


@pytest.fixture(autouse=True)
def dev_storage_backend(tmp_path, monkeypatch):
    """Point the process-wide storage singleton at a throwaway directory.

    Also gives ``DEV_STORAGE_TOKEN`` a non-empty value: it defaults to ``""``
    (fail closed — see app/core/config.py), and the empty default always
    denies, so the router-level tests below need a real token configured to
    exercise the "wrong/missing token" cases meaningfully.
    """
    monkeypatch.setattr(settings, "DEV_STORAGE_TOKEN", "test-dev-storage-token")
    reset_storage()
    import app.services.storage as storage_module

    storage_module._storage_singleton = LocalDevStorage(
        base_dir=tmp_path, base_url="http://testserver"
    )
    try:
        yield
    finally:
        reset_storage()


@pytest.fixture
def client():
    return TestClient(app)


class TestDevStorageDownloadRoute:
    def test_traversal_key_returns_400_and_no_bytes(self, client):
        # Percent-encoded so the HTTP client/layer does not normalize the
        # ``..`` away before it reaches the route — this deterministically
        # exercises the handler's own ``_reject_unsafe_key`` check.
        resp = client.get("/dev-storage/%2e%2e/%2e%2e/etc/passwd")

        assert resp.status_code == 400
        assert b"root:" not in resp.content

    def test_plain_traversal_key_never_returns_file_bytes(self, client):
        # A plain ``../`` may get normalized away by the HTTP layer before
        # routing (404 — no such route) rather than reach the handler (400);
        # either way it must never return file bytes.
        resp = client.get("/dev-storage/../../etc/passwd")

        assert resp.status_code in (400, 404)
        assert b"root:" not in resp.content

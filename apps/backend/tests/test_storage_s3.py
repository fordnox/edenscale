"""Tests for the S3 storage backend (presigned direct-to-bucket uploads).

Presigning is local signing only — no network — so these run against fake
credentials and a fake endpoint.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import settings
from app.services.storage import (
    S3Storage,
    get_storage,
    key_from_file_url,
    reset_storage,
)


@pytest.fixture(autouse=True)
def s3_settings(monkeypatch):
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://fake.r2.example.com")
    monkeypatch.setattr(settings, "S3_ACCESS_KEY_ID", "test-key")
    monkeypatch.setattr(settings, "S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "uploads")
    monkeypatch.setattr(settings, "S3_REGION", "auto")
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "https://cdn.example.com")
    monkeypatch.setattr(settings, "S3_PREFIX", "")
    reset_storage()
    yield
    reset_storage()


class TestS3Storage:
    def test_presign_put_returns_signed_url_and_canonical_file_url(self):
        storage = S3Storage()
        upload_url, file_url, expires_at = storage.presign_put(
            "documents/abc/report.pdf", "application/pdf"
        )

        parsed = urlparse(upload_url)
        assert parsed.scheme == "https"
        assert "documents/abc/report.pdf" in parsed.path
        query = parse_qs(parsed.query)
        assert "X-Amz-Signature" in query
        # Signed ContentType forces the client to send exactly that header.
        assert "content-type" in query["X-Amz-SignedHeaders"][0]

        assert file_url == "https://cdn.example.com/documents/abc/report.pdf"
        remaining = expires_at - datetime.now(timezone.utc)
        assert timedelta(minutes=13) < remaining <= timedelta(minutes=15)

    def test_presign_put_without_mime_type_leaves_content_type_unsigned(self):
        storage = S3Storage()
        upload_url, _, _ = storage.presign_put("documents/abc/blob")
        query = parse_qs(urlparse(upload_url).query)
        assert "content-type" not in query["X-Amz-SignedHeaders"][0]

    def test_file_url_falls_back_to_endpoint_when_no_public_base(self, monkeypatch):
        monkeypatch.setattr(settings, "S3_PUBLIC_URL", "")
        storage = S3Storage()
        _, file_url, _ = storage.presign_put("documents/abc/report.pdf")
        assert file_url == (
            "https://fake.r2.example.com/uploads/documents/abc/report.pdf"
        )

    def test_presign_get_signs_a_get_for_the_key(self):
        storage = S3Storage()
        url = storage.presign_get("documents/abc/report.pdf")
        parsed = urlparse(url)
        assert "documents/abc/report.pdf" in parsed.path
        assert "X-Amz-Signature" in parse_qs(parsed.query)

    def test_canonical_url_percent_encodes_key(self):
        storage = S3Storage()
        _, file_url, _ = storage.presign_put("documents/abc/Q2 report.pdf")
        assert file_url == "https://cdn.example.com/documents/abc/Q2%20report.pdf"
        assert key_from_file_url(file_url) == "documents/abc/Q2 report.pdf"


class TestS3Prefix:
    def test_uploads_land_under_the_prefix(self, monkeypatch):
        monkeypatch.setattr(settings, "S3_PREFIX", "taven")
        storage = S3Storage()
        upload_url, file_url, _ = storage.presign_put("documents/abc/report.pdf")

        assert "/taven/documents/abc/report.pdf" in urlparse(upload_url).path
        assert file_url == "https://cdn.example.com/taven/documents/abc/report.pdf"

    def test_prefix_is_applied_exactly_once_on_read_back(self, monkeypatch):
        monkeypatch.setattr(settings, "S3_PREFIX", "/taven/")
        storage = S3Storage()
        _, file_url, _ = storage.presign_put("documents/abc/report.pdf")

        # The round trip a document read performs: recover the key from the
        # persisted file_url, then presign a GET for it.
        key = key_from_file_url(file_url)
        assert key == "taven/documents/abc/report.pdf"
        get_url = storage.presign_get(key)
        path = urlparse(get_url).path
        assert path.endswith("/taven/documents/abc/report.pdf")
        assert "taven/taven" not in path

class TestKeyFromFileUrl:
    def test_public_base_form(self):
        assert (
            key_from_file_url("https://cdn.example.com/documents/a/b.pdf")
            == "documents/a/b.pdf"
        )

    def test_endpoint_bucket_form(self):
        assert (
            key_from_file_url(
                "https://fake.r2.example.com/uploads/documents/a/b.pdf"
            )
            == "documents/a/b.pdf"
        )

    def test_dev_storage_form_still_works(self):
        assert (
            key_from_file_url("http://localhost:8000/dev-storage/documents/a/b.pdf")
            == "documents/a/b.pdf"
        )


class TestGetStorageSelection:
    def test_s3_backend_selects_s3_storage(self, monkeypatch):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
        reset_storage()
        assert isinstance(get_storage(), S3Storage)

    def test_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "gcs")
        reset_storage()
        with pytest.raises(ValueError):
            get_storage()

"""Integration tests for the /documents router and the dev-storage round-trip.

These exercise the full upload-init -> client PUT -> POST /documents flow
using the LocalDevStorage backend, plus RBAC checks on listing and access.
"""

import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.slugs import slugify

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Fund,
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership
from app.services import storage as storage_module


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_local_storage():
    """Each test gets its own temp dir so files do not leak across runs."""
    with tempfile.TemporaryDirectory() as tmp:
        storage_module.reset_storage()
        storage_module._storage_singleton = storage_module.LocalDevStorage(
            base_dir=Path(tmp), base_url="http://testserver"
        )
        try:
            yield
        finally:
            storage_module.reset_storage()


@pytest.fixture
def client():
    return TestClient(app)


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return str(org.id)
    finally:
        db.close()


def _seed_user(
    subject_id: str,
    role: UserRole,
    *,
    email: str | None = None,
    organization_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        user = User(
            first_name="First",
            last_name="Last",
            email=email or f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        if organization_id is not None:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=organization_id,
                    role=role,
                )
            )
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _seed_fund(organization_id: int, *, name: str = "NewTaven Fund I") -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name, slug=slugify(name))
        db.add(fund)
        db.commit()
        return str(fund.id)
    finally:
        db.close()


def _seed_investor(organization_id: int, *, name: str = "Acme LP") -> int:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name)
        db.add(investor)
        db.commit()
        return str(investor.id)
    finally:
        db.close()


def _seed_contact(investor_id: int, user_id: int) -> int:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name="Lp",
            last_name="Contact",
        )
        db.add(contact)
        db.commit()
        return str(contact.id)
    finally:
        db.close()


class TestDocumentUploadFlow:
    def test_upload_init_then_create_then_get_round_trip(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        init = client.post(
            "/documents/upload-init",
            json={
                "file_name": "side-letter.pdf",
                "mime_type": "application/pdf",
                "file_size": 11,
            },
        )
        assert init.status_code == 201
        body = init.json()
        upload_url = body["upload_url"]
        file_url = body["file_url"]
        assert "/dev-storage/documents/" in upload_url

        # Simulate the client uploading bytes to the presigned URL.
        upload = client.put(
            upload_url.replace("http://testserver", ""),
            content=b"hello world",
            headers={"x-dev-storage-token": settings.DEV_STORAGE_TOKEN},
        )
        assert upload.status_code == 204

        create = client.post(
            "/documents",
            json={
                "fund_id": fund_id,
                "document_type": "legal",
                "title": "Side Letter v1",
                "file_name": "side-letter.pdf",
                "file_url": file_url,
                "mime_type": "application/pdf",
                "file_size": 11,
                "is_confidential": True,
            },
        )
        assert create.status_code == 201, create.text
        document = create.json()
        assert document["title"] == "Side Letter v1"
        assert document["fund_id"] == fund_id
        assert document["uploaded_by_user_id"] is not None

        detail = client.get(f"/documents/{document['id']}")
        assert detail.status_code == 200
        assert detail.json()["download_url"] is not None

        download = client.get(detail.json()["download_url"].replace("http://testserver", ""))
        assert download.status_code == 200
        assert download.content == b"hello world"

    def test_dev_storage_rejects_missing_token(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        init = client.post(
            "/documents/upload-init",
            json={"file_name": "f.bin", "mime_type": "application/octet-stream"},
        )
        upload_url = init.json()["upload_url"].replace("http://testserver", "")
        unauth = client.put(upload_url, content=b"abc")
        assert unauth.status_code == 401


class TestUploadProxyEndpoint:
    """PUT /documents/upload/{key} — the S3-backend upload proxy (the browser
    never talks to the bucket, so no bucket CORS is needed)."""

    def test_writes_bytes_through_the_storage_backend(
        self, client, override_user
    ):
        _seed_user("hanko-any", UserRole.lp, email="any@example.com")
        override_user("hanko-any")

        resp = client.put(
            "/documents/upload/documents/tok/report.pdf",
            content=b"%PDF-1.7",
            headers={"Content-Type": "application/pdf"},
        )

        assert resp.status_code == 204
        stored = storage_module.get_storage().read("documents/tok/report.pdf")
        assert stored == b"%PDF-1.7"

    def test_requires_authentication(self, client, override_user):
        override_user(None)
        resp = client.put(
            "/documents/upload/documents/tok/report.pdf", content=b"x"
        )
        assert resp.status_code == 401

    def test_rejects_path_traversal_keys(self, client, override_user):
        _seed_user("hanko-any", UserRole.lp, email="any@example.com")
        override_user("hanko-any")
        resp = client.put(
            "/documents/upload/documents/../../etc/passwd", content=b"x"
        )
        # The HTTP layer normalizes ../ away before routing (404); the
        # handler's own key check (400) backstops anything that gets past it.
        assert resp.status_code in (400, 404)


class TestUploadGrantVerification:
    """PUT /documents/upload/{key} must also carry the expires/sig grant that
    upload-init issued to the calling user — plain authentication is not
    enough, since storage keys are recoverable from file_url by anyone who
    can view a document (see plans/004-bind-upload-key-to-caller.md).

    Verification only activates when UPLOAD_SIGNING_SECRET is set (it is
    empty, and therefore bypassed, in every other test in this module) —
    otherwise these assertions would be vacuous. The S3 backend is used
    (with a fake boto3 client) because it is the only backend whose
    upload_url is the /documents/upload/{key} proxy this guard protects.
    """

    @pytest.fixture(autouse=True)
    def s3_backend(self, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_SIGNING_SECRET", "test-signing-secret")
        monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://fake.r2.example.com")
        monkeypatch.setattr(settings, "S3_ACCESS_KEY_ID", "test-key")
        monkeypatch.setattr(settings, "S3_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setattr(settings, "S3_BUCKET_NAME", "uploads")
        monkeypatch.setattr(settings, "S3_PREFIX", "")
        storage_module.reset_storage()
        storage = storage_module.S3Storage()
        self.put_calls: list[dict] = []
        put_calls = self.put_calls
        storage._client = type(
            "FakeClient", (), {"put_object": lambda self, **kw: put_calls.append(kw)}
        )()
        storage_module._storage_singleton = storage
        yield
        storage_module.reset_storage()

    def _init_upload(self, client, file_name: str = "report.pdf") -> dict:
        resp = client.post(
            "/documents/upload-init",
            json={"file_name": file_name, "mime_type": "application/pdf"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["upload_url"].startswith("/documents/upload/")
        assert "sig=" in body["upload_url"] and "expires=" in body["upload_url"]
        return body

    def test_upload_with_valid_grant_succeeds(self, client, override_user):
        _seed_user("hanko-a", UserRole.lp, email="a@example.com")
        override_user("hanko-a")

        body = self._init_upload(client)
        resp = client.put(body["upload_url"], content=b"%PDF-1.7")

        assert resp.status_code == 204
        assert self.put_calls, "storage.write should have reached the backend"

    def test_cross_user_put_is_rejected(self, client, override_user):
        """The regression test: B cannot use A's upload grant, even though B
        is a distinct, validly authenticated user."""
        _seed_user("hanko-a", UserRole.lp, email="a@example.com")
        _seed_user("hanko-b", UserRole.lp, email="b@example.com")

        override_user("hanko-a")
        body = self._init_upload(client)

        override_user("hanko-b")
        resp = client.put(body["upload_url"], content=b"%PDF-1.7")

        assert resp.status_code == 403
        assert not self.put_calls

    def test_tampered_signature_is_rejected(self, client, override_user):
        _seed_user("hanko-a", UserRole.lp, email="a@example.com")
        override_user("hanko-a")
        body = self._init_upload(client)

        last_char = body["upload_url"][-1]
        flipped = "0" if last_char != "0" else "1"
        tampered_url = body["upload_url"][:-1] + flipped

        resp = client.put(tampered_url, content=b"%PDF-1.7")

        assert resp.status_code == 403
        assert not self.put_calls

    def test_expired_grant_is_rejected(self, client, override_user):
        _seed_user("hanko-a", UserRole.lp, email="a@example.com")
        override_user("hanko-a")
        body = self._init_upload(client)

        parsed = urlsplit(body["upload_url"])
        query = dict(parse_qsl(parsed.query))
        query["expires"] = str(int(query["expires"]) - 3600)
        expired_url = urlunsplit(parsed._replace(query=urlencode(query)))

        resp = client.put(expired_url, content=b"%PDF-1.7")

        assert resp.status_code == 403
        assert not self.put_calls

    def test_missing_grant_is_rejected(self, client, override_user):
        _seed_user("hanko-a", UserRole.lp, email="a@example.com")
        override_user("hanko-a")
        body = self._init_upload(client)

        bare_url = body["upload_url"].split("?")[0]
        resp = client.put(bare_url, content=b"%PDF-1.7")

        assert resp.status_code == 403
        assert not self.put_calls


class TestDocumentRbac:
    def test_lp_cannot_see_confidential_doc_outside_their_investor(
        self, client, override_user
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        other_investor = _seed_investor(org_id, name="Other LP")

        init = client.post(
            "/documents/upload-init",
            json={"file_name": "secret.pdf", "mime_type": "application/pdf"},
        ).json()
        client.put(
            init["upload_url"].replace("http://testserver", ""),
            content=b"secret",
            headers={"x-dev-storage-token": settings.DEV_STORAGE_TOKEN},
        )
        confidential = client.post(
            "/documents",
            json={
                "fund_id": fund_id,
                "investor_id": other_investor,
                "document_type": "legal",
                "title": "Confidential other-LP doc",
                "file_name": "secret.pdf",
                "file_url": init["file_url"],
                "mime_type": "application/pdf",
                "is_confidential": True,
            },
        ).json()

        # Now switch to an LP that has no contact for that investor.
        own_investor = _seed_investor(org_id, name="Own LP")
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id)
        override_user("hanko-lp")

        listing = client.get("/documents")
        assert listing.status_code == 200
        ids = [row["id"] for row in listing.json()]
        assert confidential["id"] not in ids

        detail = client.get(f"/documents/{confidential['id']}")
        assert detail.status_code == 403

    def test_lp_cannot_create_document(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        override_user("hanko-lp")
        fund_id = _seed_fund(org_id)

        init = client.post(
            "/documents/upload-init",
            json={"file_name": "x.pdf", "mime_type": "application/pdf"},
        )
        assert init.status_code == 201

        create = client.post(
            "/documents",
            json={
                "fund_id": fund_id,
                "document_type": "legal",
                "title": "Tries to upload",
                "file_name": "x.pdf",
                "file_url": init.json()["file_url"],
            },
        )
        assert create.status_code == 403

    def test_fund_manager_cannot_attach_to_other_org_fund(self, client, override_user):
        own_org = _seed_org("Own FM Firm")
        other_org = _seed_org("Other FM Firm")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=own_org,
        )
        override_user("hanko-fm")
        other_fund = _seed_fund(other_org, name="Outsider Fund")

        init = client.post(
            "/documents/upload-init",
            json={"file_name": "x.pdf", "mime_type": "application/pdf"},
        ).json()

        create = client.post(
            "/documents",
            json={
                "fund_id": other_fund,
                "document_type": "legal",
                "title": "Trespass",
                "file_name": "x.pdf",
                "file_url": init["file_url"],
            },
        )
        assert create.status_code == 403


class TestDocumentMutations:
    def test_patch_and_delete_lifecycle(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        init = client.post(
            "/documents/upload-init",
            json={"file_name": "report.pdf", "mime_type": "application/pdf"},
        ).json()
        client.put(
            init["upload_url"].replace("http://testserver", ""),
            content=b"report",
            headers={"x-dev-storage-token": settings.DEV_STORAGE_TOKEN},
        )
        created = client.post(
            "/documents",
            json={
                "fund_id": fund_id,
                "document_type": "report",
                "title": "Q1 Report",
                "file_name": "report.pdf",
                "file_url": init["file_url"],
                "mime_type": "application/pdf",
            },
        ).json()

        patched = client.patch(
            f"/documents/{created['id']}",
            json={"title": "Q1 Report (Final)", "is_confidential": False},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Q1 Report (Final)"
        assert patched.json()["is_confidential"] is False

        # The uploaded bytes exist in storage until the delete.
        storage = storage_module.get_storage()
        key = storage_module.key_from_file_url(init["file_url"])
        assert storage.read(key) == b"report"  # type: ignore[attr-defined]

        deleted = client.delete(f"/documents/{created['id']}")
        assert deleted.status_code == 204

        gone = client.get(f"/documents/{created['id']}")
        assert gone.status_code == 404
        # Deleting the document also removes the stored file.
        assert storage.read(key) is None  # type: ignore[attr-defined]

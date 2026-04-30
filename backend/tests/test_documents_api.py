"""Integration tests for the /documents router and the dev-storage round-trip.

These exercise the full upload-init -> client PUT -> POST /documents flow
using the LocalDevStorage backend, plus RBAC checks on listing and access.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
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


@pytest.fixture
def override_user():
    def _set(subject_id: str | None) -> None:
        app.dependency_overrides[get_current_user] = lambda: (
            {"sub": subject_id} if subject_id is not None else {}
        )

    yield _set
    app.dependency_overrides.clear()


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
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
            organization_id=organization_id,
            role=role,
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
        return user.id
    finally:
        db.close()


def _seed_fund(organization_id: int, *, name: str = "Eden Fund I") -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name)
        db.add(fund)
        db.commit()
        return fund.id
    finally:
        db.close()


def _seed_investor(organization_id: int, *, name: str = "Acme LP") -> int:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name)
        db.add(investor)
        db.commit()
        return investor.id
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
        return contact.id
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

        deleted = client.delete(f"/documents/{created['id']}")
        assert deleted.status_code == 204

        gone = client.get(f"/documents/{created['id']}")
        assert gone.status_code == 404

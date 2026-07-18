"""Integration tests for the /email-ingest router.

Exercise the shared-secret auth, sender→org resolution, and the drop paths for
unknown/ambiguous senders, using the LocalDevStorage backend end-to-end.
"""

import base64
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Document, Organization, OrganizationType, User, UserRole
from app.models.user_organization_membership import UserOrganizationMembership
from app.core.slugs import slugify
from app.services import storage as storage_module

_TOKEN = "test-ingest-secret"


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_local_storage():
    with tempfile.TemporaryDirectory() as tmp:
        storage_module.reset_storage()
        storage_module._storage_singleton = storage_module.LocalDevStorage(
            base_dir=Path(tmp), base_url="http://testserver"
        )
        try:
            yield
        finally:
            storage_module.reset_storage()


@pytest.fixture(autouse=True)
def enable_ingest(monkeypatch):
    """Feature on by default; the disabled test overrides this."""
    monkeypatch.setattr(settings, "EMAIL_INGEST_TOKEN", _TOKEN)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_org(name: str) -> str:
    db = SessionLocal()
    try:
        org = Organization(
            name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
        )
        db.add(org)
        db.commit()
        return str(org.id)
    finally:
        db.close()


def _seed_user(email: str, *, memberships: list[tuple[str, UserRole]] = ()) -> str:
    db = SessionLocal()
    try:
        user = User(first_name="First", last_name="Last", email=email)
        db.add(user)
        db.flush()
        for organization_id, role in memberships:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id, organization_id=organization_id, role=role
                )
            )
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _payload(sender: str, *, subject: str = "Q3 report", content: bytes = b"%PDF-1.4"):
    return {
        "sender_email": sender,
        "subject": subject,
        "attachments": [
            {
                "file_name": "q3-report.pdf",
                "mime_type": "application/pdf",
                "content_base64": base64.b64encode(content).decode(),
            }
        ],
    }


def _headers(token: str = _TOKEN) -> dict:
    return {"x-email-ingest-token": token}


def _documents() -> list[Document]:
    db = SessionLocal()
    try:
        return db.query(Document).all()
    finally:
        db.close()


def test_feature_disabled_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INGEST_TOKEN", "")
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test"),
        headers=_headers(),
    )
    assert resp.status_code == 404


def test_bad_token_returns_403(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test"),
        headers=_headers("wrong"),
    )
    assert resp.status_code == 403
    assert _documents() == []


def test_missing_token_returns_403(client):
    resp = client.post("/email-ingest/documents", json=_payload("jane@acme.test"))
    assert resp.status_code == 403


def test_unknown_sender_is_dropped(client):
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("nobody@acme.test"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dropped"
    assert "unknown sender" in body["reason"]
    assert _documents() == []


def test_lp_only_sender_is_dropped(client):
    org = _seed_org("Acme Capital")
    _seed_user("lp@acme.test", memberships=[(org, UserRole.lp)])
    resp = client.post(
        "/email-ingest/documents", json=_payload("lp@acme.test"), headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert _documents() == []


def test_ambiguous_membership_is_dropped(client):
    org_a = _seed_org("Acme Capital")
    org_b = _seed_org("Beta Partners")
    _seed_user(
        "multi@acme.test",
        memberships=[(org_a, UserRole.admin), (org_b, UserRole.fund_manager)],
    )
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("multi@acme.test"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert _documents() == []


def test_undecodable_attachment_is_dropped(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    payload = _payload("jane@acme.test")
    payload["attachments"][0]["content_base64"] = "!!!not-base64!!!"
    resp = client.post(
        "/email-ingest/documents", json=payload, headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert _documents() == []


def test_happy_path_creates_document(client):
    org = _seed_org("Acme Capital")
    user_id = _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    content = b"%PDF-1.4 pretend pdf bytes"
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test", subject="Quarterly", content=content),
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert len(body["document_ids"]) == 1

    docs = _documents()
    assert len(docs) == 1
    doc = docs[0]
    assert str(doc.organization_id) == org
    assert str(doc.uploaded_by_user_id) == user_id
    assert doc.document_type.value == "other"
    assert doc.title == "Quarterly"
    assert doc.file_name == "q3-report.pdf"
    assert doc.mime_type == "application/pdf"
    assert doc.file_size == len(content)
    assert doc.is_confidential is True

    # Blob was actually written to storage and round-trips.
    stored = storage_module.get_storage().read(
        storage_module.key_from_file_url(doc.file_url)
    )
    assert stored == content


def test_title_falls_back_to_filename_when_no_subject(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test", subject="   "),
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert _documents()[0].title == "q3-report.pdf"

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
from app.core.slugs import slugify
from app.main import app
from app.models import Document, Organization, OrganizationType, User, UserRole
from app.models.user_organization_membership import UserOrganizationMembership
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


def _payload(
    sender: str,
    *,
    recipient: str | None = None,
    subject: str = "Q3 report",
    content: bytes = b"%PDF-1.4",
    message_id: str | None = None,
):
    payload = {
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
    if recipient is not None:
        payload["recipient"] = recipient
    if message_id is not None:
        payload["message_id"] = message_id
    return payload


def _multi_payload(sender: str, *, count: int) -> dict:
    """A payload with ``count`` distinct attachments, for testing the
    all-or-nothing write path."""
    return {
        "sender_email": sender,
        "subject": "Batch",
        "attachments": [
            {
                "file_name": f"doc-{i}.pdf",
                "mime_type": "application/pdf",
                "content_base64": base64.b64encode(
                    f"%PDF-1.4 doc {i}".encode()
                ).decode(),
            }
            for i in range(count)
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


def test_ambiguous_membership_without_tag_is_dropped(client):
    org_a = _seed_org("Acme Capital")
    org_b = _seed_org("Beta Partners")
    _seed_user(
        "multi@acme.test",
        memberships=[(org_a, UserRole.admin), (org_b, UserRole.fund_manager)],
    )
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("multi@acme.test", recipient="cc@newtaven.com"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dropped"
    assert "ingest+" in body["reason"]  # tells the sender how to disambiguate
    assert _documents() == []


def test_plus_tag_routes_multi_org_sender_to_named_org(client):
    org_a = _seed_org("Acme Capital")
    org_b = _seed_org("Beta Partners")
    _seed_user(
        "multi@acme.test",
        memberships=[(org_a, UserRole.admin), (org_b, UserRole.fund_manager)],
    )
    resp = client.post(
        "/email-ingest/documents",
        json=_payload(
            "multi@acme.test", recipient=f"cc+{slugify('Beta Partners')}@newtaven.com"
        ),
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "created"
    docs = _documents()
    assert len(docs) == 1
    assert str(docs[0].organization_id) == org_b


def test_plus_tag_unknown_org_is_dropped(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test", recipient="cc+ghost-org@newtaven.com"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dropped"
    assert "unknown organization tag" in body["reason"]
    assert _documents() == []


def test_plus_tag_org_without_membership_is_dropped(client):
    # Sender is admin of Acme but tags Beta, where they hold no membership:
    # a valid tag must never fall back to the sender's own org.
    org_a = _seed_org("Acme Capital")
    _seed_org("Beta Partners")
    _seed_user("jane@acme.test", memberships=[(org_a, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload(
            "jane@acme.test", recipient=f"cc+{slugify('Beta Partners')}@newtaven.com"
        ),
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dropped"
    assert "not authorized" in body["reason"]
    assert _documents() == []


def test_plus_tag_lp_membership_is_dropped(client):
    # Membership exists in the tagged org, but only as an LP — not eligible.
    org = _seed_org("Acme Capital")
    _seed_user("lp@acme.test", memberships=[(org, UserRole.lp)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload(
            "lp@acme.test", recipient=f"cc+{slugify('Acme Capital')}@newtaven.com"
        ),
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert _documents() == []


def test_plain_recipient_with_no_tag_uses_sole_org(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents",
        json=_payload("jane@acme.test", recipient="cc@newtaven.com"),
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "created"
    assert str(_documents()[0].organization_id) == org


def test_undecodable_attachment_is_dropped(client):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    payload = _payload("jane@acme.test")
    payload["attachments"][0]["content_base64"] = "!!!not-base64!!!"
    resp = client.post("/email-ingest/documents", json=payload, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert _documents() == []


@pytest.fixture
def capture_draft(monkeypatch):
    """Feature ON + capture every enqueued draft-letter job."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    calls: list[dict] = []

    async def _capture(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.services.email_ingest.enqueue_draft_letter", _capture, raising=True
    )
    return calls


def test_ingested_pdf_enqueues_letter_draft(client, capture_draft):
    org = _seed_org("Acme Capital")
    user_id = _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents", json=_payload("jane@acme.test"), headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert len(capture_draft) == 1
    assert capture_draft[0] == {
        "document_id": str(_documents()[0].id),
        "user_id": user_id,
    }


def test_non_pdf_attachment_does_not_enqueue_draft(client, capture_draft):
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    payload = _payload("jane@acme.test")
    payload["attachments"][0]["file_name"] = "notes.txt"
    payload["attachments"][0]["mime_type"] = "text/plain"
    payload["attachments"][0]["content_base64"] = base64.b64encode(b"hi").decode()
    resp = client.post("/email-ingest/documents", json=payload, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert capture_draft == []


def test_pdf_ingest_without_feature_does_not_enqueue(client, monkeypatch):
    # Feature OFF (no OPENROUTER_API_KEY): documents still land, no draft queued.
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    called = False

    async def _boom(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.services.email_ingest.enqueue_draft_letter", _boom, raising=True
    )
    org = _seed_org("Acme Capital")
    _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
    resp = client.post(
        "/email-ingest/documents", json=_payload("jane@acme.test"), headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert called is False


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


class TestMessageIdIdempotency:
    """Plan 020(a): a message_id, once seen, must not be reprocessed. Must
    FAIL pre-fix — pre-fix, ``EmailIngestRequest`` has no ``message_id``
    field at all, so passing one is simply ignored by pydantic and every
    repost creates a fresh Document; see the plan 020 report for the
    before/after."""

    def test_repeat_message_id_is_a_noop(self, client, capture_draft):
        org = _seed_org("Acme Capital")
        _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
        payload = _payload("jane@acme.test", message_id="<abc123@mail.example>")

        first = client.post("/email-ingest/documents", json=payload, headers=_headers())
        assert first.status_code == 200
        assert first.json()["status"] == "created"
        assert len(_documents()) == 1
        assert len(capture_draft) == 1

        second = client.post(
            "/email-ingest/documents", json=payload, headers=_headers()
        )
        assert second.status_code == 200
        # Exact same result handed back, not a fresh document.
        assert second.json() == first.json()
        assert len(_documents()) == 1, "repeat message_id created a second document"
        assert len(capture_draft) == 1, "repeat message_id re-enqueued a draft"

    def test_absent_message_id_never_dedupes(self, client):
        """The Worker doesn't send message_id yet — every ingest without one
        must keep being processed fresh, exactly as before this field
        existed."""
        org = _seed_org("Acme Capital")
        _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
        payload = _payload("jane@acme.test")

        for _ in range(2):
            resp = client.post(
                "/email-ingest/documents", json=payload, headers=_headers()
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "created"
        assert len(_documents()) == 2


class TestAtomicIngest:
    """Plan 020(a): a failure partway through the attachment loop must leave
    nothing committed. Must FAIL pre-fix — pre-fix, ``storage.write`` then
    ``documents.create`` (which commits) run per attachment inside the loop,
    so a failure on attachment 3 leaves attachments 1-2 already committed;
    see the plan 020 report for the before/after."""

    def test_failure_on_third_attachment_commits_nothing(self, client):
        org = _seed_org("Acme Capital")
        _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])

        storage = storage_module.get_storage()
        original_write = storage.write
        calls = {"n": 0}

        def flaky_write(key, content, mime_type=None):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("storage boom on attachment 3")
            return original_write(key, content, mime_type)

        storage.write = flaky_write

        payload = _multi_payload("jane@acme.test", count=5)
        with pytest.raises(RuntimeError, match="storage boom on attachment 3"):
            client.post("/email-ingest/documents", json=payload, headers=_headers())

        assert calls["n"] == 3, "the flaky write should have been reached exactly once"
        assert _documents() == [], (
            "attachments 1-2, written before the failure, must not have been "
            "committed as Documents"
        )


class TestRequestIdCorrelation:
    """Plan 020(c): the request id round-trips through the middleware
    contextvar and is echoed on the response."""

    def test_absent_request_id_is_generated(self, client):
        org = _seed_org("Acme Capital")
        _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])
        resp = client.post(
            "/email-ingest/documents",
            json=_payload("jane@acme.test"),
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert resp.headers.get("x-request-id")

    def test_supplied_request_id_is_echoed_and_reaches_the_contextvar(
        self, client, monkeypatch
    ):
        from app.middleware.request_id import get_request_id

        org = _seed_org("Acme Capital")
        _seed_user("jane@acme.test", memberships=[(org, UserRole.admin)])

        seen: dict = {}

        async def _capture(**kwargs):
            seen["request_id"] = get_request_id()

        monkeypatch.setattr(
            "app.services.email_ingest.enqueue_draft_letter", _capture, raising=True
        )
        monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")

        headers = _headers()
        headers["X-Request-ID"] = "corr-abc-123"
        resp = client.post(
            "/email-ingest/documents", json=_payload("jane@acme.test"), headers=headers
        )
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "corr-abc-123"
        assert seen["request_id"] == "corr-abc-123"

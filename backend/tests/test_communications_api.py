"""Integration tests for the /communications router and the nested
/funds/{id}/communications route."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Commitment,
    CommitmentStatus,
    Fund,
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
    User,
    UserRole,
)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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


def _seed_commitment(
    fund_id: int,
    investor_id: int,
    *,
    committed_amount: Decimal = Decimal("1000.00"),
    status: CommitmentStatus = CommitmentStatus.approved,
) -> int:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=committed_amount,
            commitment_date=date(2026, 1, 1),
            status=status,
        )
        db.add(commitment)
        db.commit()
        return commitment.id
    finally:
        db.close()


def _seed_contact(
    investor_id: int,
    user_id: int | None,
    *,
    is_primary: bool = True,
) -> int:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name="Lp",
            last_name="Contact",
            is_primary=is_primary,
        )
        db.add(contact)
        db.commit()
        return contact.id
    finally:
        db.close()


class TestCommunicationLifecycle:
    def test_draft_send_resolves_primary_contacts_with_approved_commitments(
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
        # Approved investor with primary contact -> should receive
        approved_investor = _seed_investor(org_id, name="Approved LP")
        _seed_commitment(
            fund_id, approved_investor, status=CommitmentStatus.approved
        )
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        primary_contact_id = _seed_contact(
            approved_investor, lp_user_id, is_primary=True
        )
        # Non-primary contact on the same investor -> should NOT receive
        _seed_contact(approved_investor, None, is_primary=False)
        # Pending investor -> should NOT receive
        pending_investor = _seed_investor(org_id, name="Pending LP")
        _seed_commitment(
            fund_id, pending_investor, status=CommitmentStatus.pending
        )
        _seed_contact(pending_investor, None, is_primary=True)

        create_resp = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Q1 Update",
                "body": "Hello LPs",
            },
        )
        assert create_resp.status_code == 201
        comm = create_resp.json()
        assert comm["sent_at"] is None
        assert comm["recipients"] == []
        comm_id = comm["id"]

        send_resp = client.post(f"/communications/{comm_id}/send")
        assert send_resp.status_code == 200
        sent = send_resp.json()
        assert sent["sent_at"] is not None
        assert len(sent["recipients"]) == 1
        recipient = sent["recipients"][0]
        assert recipient["investor_contact_id"] == primary_contact_id
        assert recipient["user_id"] == lp_user_id
        assert recipient["delivered_at"] is not None
        assert recipient["read_at"] is None

    def test_send_with_explicit_recipients_overrides_default_resolution(
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
        target_user_id = _seed_user(
            "hanko-target",
            UserRole.lp,
            email="target@example.com",
            organization_id=org_id,
        )

        create_resp = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "message",
                "subject": "Direct",
                "body": "Just for you",
            },
        )
        comm_id = create_resp.json()["id"]
        send_resp = client.post(
            f"/communications/{comm_id}/send",
            json={"recipients": [{"user_id": target_user_id}]},
        )
        assert send_resp.status_code == 200
        recipients = send_resp.json()["recipients"]
        assert len(recipients) == 1
        assert recipients[0]["user_id"] == target_user_id

    def test_send_already_sent_returns_409(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        _seed_commitment(fund_id, investor_id, status=CommitmentStatus.approved)
        _seed_contact(investor_id, None, is_primary=True)

        comm_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Hi",
                "body": "B",
            },
        ).json()["id"]

        first = client.post(f"/communications/{comm_id}/send")
        assert first.status_code == 200
        retry = client.post(f"/communications/{comm_id}/send")
        assert retry.status_code == 409

    def test_send_without_recipients_returns_409(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        comm_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Empty",
                "body": "No LPs",
            },
        ).json()["id"]

        resp = client.post(f"/communications/{comm_id}/send")
        assert resp.status_code == 409

    def test_update_after_send_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        _seed_commitment(fund_id, investor_id, status=CommitmentStatus.approved)
        _seed_contact(investor_id, None, is_primary=True)

        comm_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Hi",
                "body": "B",
            },
        ).json()["id"]
        client.post(f"/communications/{comm_id}/send")

        resp = client.patch(
            f"/communications/{comm_id}",
            json={"subject": "Edited"},
        )
        assert resp.status_code == 409

    def test_recipient_can_mark_read(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        _seed_commitment(fund_id, investor_id, status=CommitmentStatus.approved)
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(investor_id, lp_user_id, is_primary=True)

        comm_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Hi",
                "body": "B",
            },
        ).json()["id"]
        sent = client.post(f"/communications/{comm_id}/send").json()
        recipient_id = sent["recipients"][0]["id"]

        override_user("hanko-lp")
        read_resp = client.post(
            f"/communications/{comm_id}/recipients/{recipient_id}/read"
        )
        assert read_resp.status_code == 200
        assert read_resp.json()["read_at"] is not None


class TestCommunicationRbac:
    def test_lp_cannot_create(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        override_user("hanko-lp")
        fund_id = _seed_fund(org_id)

        response = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "x",
                "body": "y",
            },
        )
        assert response.status_code == 403

    def test_fund_manager_cannot_create_on_other_org_fund(
        self, client, override_user
    ):
        org_a = _seed_org(name="Org A")
        org_b = _seed_org(name="Org B")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_a,
        )
        override_user("hanko-fm")
        fund_in_b = _seed_fund(org_b, name="Other Org Fund")

        response = client.post(
            "/communications",
            json={
                "fund_id": fund_in_b,
                "type": "announcement",
                "subject": "x",
                "body": "y",
            },
        )
        assert response.status_code == 403

    def test_lp_only_sees_communications_they_received(
        self, client, override_user
    ):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        _seed_commitment(fund_id, own_investor, status=CommitmentStatus.approved)
        _seed_commitment(
            fund_id, other_investor, status=CommitmentStatus.approved
        )
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        # Two primary contacts: only one points at our LP user.
        _seed_contact(own_investor, lp_user_id, is_primary=True)
        _seed_contact(other_investor, None, is_primary=True)

        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        own_comm = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "All",
                "body": "Visible",
            },
        ).json()["id"]
        client.post(f"/communications/{own_comm}/send")

        unsent_comm = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Draft",
                "body": "Hidden",
            },
        ).json()["id"]

        override_user("hanko-lp")
        listing = client.get("/communications")
        assert listing.status_code == 200
        ids = [row["id"] for row in listing.json()]
        assert own_comm in ids
        assert unsent_comm not in ids

    def test_lp_cannot_mark_other_recipient_read(self, client, override_user):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        _seed_commitment(fund_id, own_investor, status=CommitmentStatus.approved)
        _seed_commitment(
            fund_id, other_investor, status=CommitmentStatus.approved
        )
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        other_user_id = _seed_user(
            "hanko-other",
            UserRole.lp,
            email="other@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id, is_primary=True)
        _seed_contact(other_investor, other_user_id, is_primary=True)

        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        comm_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "All",
                "body": "Hello",
            },
        ).json()["id"]
        sent = client.post(f"/communications/{comm_id}/send").json()
        recipients = sent["recipients"]
        other_recipient = next(
            r for r in recipients if r["user_id"] == other_user_id
        )

        override_user("hanko-lp")
        resp = client.post(
            f"/communications/{comm_id}/recipients/{other_recipient['id']}/read"
        )
        assert resp.status_code == 403


class TestNestedFundRoute:
    def test_lists_communications_under_fund(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        other_fund = _seed_fund(org_id, name="Sibling Fund")

        for subject, fund in (("First", fund_id), ("Second", fund_id), ("Out", other_fund)):
            client.post(
                "/communications",
                json={
                    "fund_id": fund,
                    "type": "announcement",
                    "subject": subject,
                    "body": "x",
                },
            )

        response = client.get(f"/funds/{fund_id}/communications")
        assert response.status_code == 200
        subjects = sorted(row["subject"] for row in response.json())
        assert subjects == ["First", "Second"]

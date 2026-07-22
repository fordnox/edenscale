"""Integration tests for the /capital-calls router and the nested
/funds/{id}/capital-calls route."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    CommitmentStatus,
    Fund,
    FundStatus,
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.capital_call_repository import CapitalCallRepository


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_org(name: str = "NewTaven Capital") -> int:
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
        fund = Fund(
            organization_id=organization_id,
            name=name,
            slug=slugify(name),
            status=FundStatus.active,
        )
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
        return str(commitment.id)
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


class TestCapitalCallLifecycle:
    """End-to-end: draft → items → sent → partial pay → fully paid,
    while commitment.called_amount tracks the per-item amount_paid sum."""

    def test_full_lifecycle_partial_then_full_payment(self, client, override_user):
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
        commitment_id = _seed_commitment(
            fund_id,
            investor_id,
            committed_amount=Decimal("1000.00"),
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        assert create_resp.status_code == 201
        call = create_resp.json()
        call_id = call["id"]
        assert call["status"] == "draft"
        assert call["fund"]["id"] == fund_id

        items_resp = client.post(
            f"/capital-calls/{call_id}/items",
            json={
                "items": [
                    {"commitment_id": commitment_id, "amount_due": "1000.00"},
                ]
            },
        )
        assert items_resp.status_code == 201
        items = items_resp.json()
        assert len(items) == 1
        item_id = items[0]["id"]
        assert Decimal(items[0]["amount_due"]) == Decimal("1000.00")
        assert Decimal(items[0]["amount_paid"]) == Decimal("0")

        send_resp = client.post(f"/capital-calls/{call_id}/send")
        assert send_resp.status_code == 200
        sent = send_resp.json()
        assert sent["status"] == "sent"
        assert sent["call_date"] is not None

        partial_resp = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "400.00"},
        )
        assert partial_resp.status_code == 200
        assert Decimal(partial_resp.json()["amount_paid"]) == Decimal("400.00")

        get_after_partial = client.get(f"/capital-calls/{call_id}")
        assert get_after_partial.status_code == 200
        assert get_after_partial.json()["status"] == "partially_paid"

        # Commitment.called_amount must mirror the per-item amount_paid sum.
        db = SessionLocal()
        try:
            commitment = db.get(Commitment, commitment_id)
            assert commitment.called_amount == Decimal("400.00")
        finally:
            db.close()

        full_resp = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "1000.00"},
        )
        assert full_resp.status_code == 200
        assert Decimal(full_resp.json()["amount_paid"]) == Decimal("1000.00")

        get_after_full = client.get(f"/capital-calls/{call_id}")
        assert get_after_full.status_code == 200
        assert get_after_full.json()["status"] == "paid"

        db = SessionLocal()
        try:
            commitment = db.get(Commitment, commitment_id)
            assert commitment.called_amount == Decimal("1000.00")
            paid_sum = sum(
                (i.amount_paid for i in commitment.capital_call_items),
                start=Decimal("0"),
            )
            assert commitment.called_amount == paid_sum
        finally:
            db.close()

    def test_partial_paid_when_one_item_paid_other_outstanding(
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
        investor_a = _seed_investor(org_id, name="LP A")
        investor_b = _seed_investor(org_id, name="LP B")
        commitment_a = _seed_commitment(
            fund_id, investor_a, committed_amount=Decimal("1000.00")
        )
        commitment_b = _seed_commitment(
            fund_id, investor_b, committed_amount=Decimal("500.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1500.00",
            },
        )
        assert create_resp.status_code == 201
        call_id = create_resp.json()["id"]

        items_resp = client.post(
            f"/capital-calls/{call_id}/items",
            json={
                "items": [
                    {"commitment_id": commitment_a, "amount_due": "1000.00"},
                    {"commitment_id": commitment_b, "amount_due": "500.00"},
                ]
            },
        )
        assert items_resp.status_code == 201
        items = {item["commitment_id"]: item["id"] for item in items_resp.json()}

        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200

        # Only LP A pays in full — call should be partially_paid, not paid.
        pay_a = client.patch(
            f"/capital-calls/{call_id}/items/{items[commitment_a]}",
            json={"amount_paid": "1000.00"},
        )
        assert pay_a.status_code == 200

        detail = client.get(f"/capital-calls/{call_id}").json()
        assert detail["status"] == "partially_paid"

        db = SessionLocal()
        try:
            assert db.get(Commitment, commitment_a).called_amount == Decimal("1000.00")
            assert db.get(Commitment, commitment_b).called_amount == Decimal("0.00")
        finally:
            db.close()


class TestCapitalCallStatusUnwind:
    """plans/017-status-machine-and-dedupe.md: recompute_status must be able
    to unwind out of partially_paid/paid when a payment is corrected back
    down, instead of getting stuck, and every status write it performs must
    go through the checked `_ALLOWED_TRANSITIONS` table."""

    def test_correction_to_zero_unwinds_partially_paid_to_sent(
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
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(
            fund_id, investor_id, committed_amount=Decimal("1000.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2099-06-01",  # far future: never overdue
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        item_id = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        ).json()[0]["id"]
        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200

        # A mis-keyed payment is recorded, then corrected back to zero.
        pay = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "400.00"},
        )
        assert pay.status_code == 200
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == (
            "partially_paid"
        )

        correction = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "0.00"},
        )
        assert correction.status_code == 200

        # Must unwind back to `sent`, not stay stuck at `partially_paid`
        # forever with nothing actually paid.
        detail = client.get(f"/capital-calls/{call_id}").json()
        assert detail["status"] == "sent"

    def test_correction_to_zero_unwinds_to_overdue_when_past_due(
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
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(
            fund_id, investor_id, committed_amount=Decimal("1000.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2020-01-01",  # long past
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        item_id = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        ).json()[0]["id"]
        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200

        client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "400.00"},
        )
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == (
            "partially_paid"
        )

        correction = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "0.00"},
        )
        assert correction.status_code == 200

        detail = client.get(f"/capital-calls/{call_id}").json()
        assert detail["status"] == "overdue"

    def test_paid_call_reduced_payment_moves_to_partially_paid(
        self, client, override_user
    ):
        """paid -> partially_paid must go through the checked helper without
        raising: _ALLOWED_TRANSITIONS must be widened (not bypassed) to
        declare this move legal."""
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
        commitment_id = _seed_commitment(
            fund_id, investor_id, committed_amount=Decimal("1000.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2099-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        item_id = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        ).json()[0]["id"]
        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200

        full = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "1000.00"},
        )
        assert full.status_code == 200
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == "paid"

        reduced = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "600.00"},
        )
        assert reduced.status_code == 200

        detail = client.get(f"/capital-calls/{call_id}").json()
        assert detail["status"] == "partially_paid"

    def test_draft_call_with_items_not_promoted(self, client, override_user):
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
        commitment_id = _seed_commitment(
            fund_id, investor_id, committed_amount=Decimal("1000.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "draft"

        # Allocating items (which triggers recompute_status internally) must
        # not promote a draft call to `sent` — only `send()` may do that.
        items = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        )
        assert items.status_code == 201
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == "draft"

    def test_scheduled_call_with_items_not_promoted(self):
        """No API route drives a call into `scheduled`, so this exercises the
        repository directly, matching the pattern in
        tests/test_payment_matching.py."""
        db = SessionLocal()
        try:
            org = Organization(
                name="Repo Direct Org",
                slug=slugify("Repo Direct Org" + uuid.uuid4().hex[:6]),
                type=OrganizationType.fund_manager_firm,
            )
            db.add(org)
            db.flush()
            fund = Fund(
                organization_id=org.id,
                name="Fund",
                slug=slugify("Fund" + uuid.uuid4().hex[:6]),
                currency_code="USD",
            )
            db.add(fund)
            db.flush()
            investor = Investor(organization_id=org.id, name="Acme LP")
            db.add(investor)
            db.flush()
            commitment = Commitment(
                fund_id=fund.id,
                investor_id=investor.id,
                committed_amount=Decimal("1000.00"),
                commitment_date=date(2026, 1, 1),
                status=CommitmentStatus.approved,
            )
            db.add(commitment)
            db.flush()
            call = CapitalCall(
                fund_id=fund.id,
                title="Scheduled Call",
                due_date=date(2026, 6, 1),
                amount=Decimal("1000.00"),
                status=CapitalCallStatus.scheduled,
            )
            db.add(call)
            db.flush()
            item = CapitalCallItem(
                capital_call_id=call.id,
                commitment_id=commitment.id,
                amount_due=Decimal("1000.00"),
                amount_paid=Decimal("0"),
            )
            db.add(item)
            db.commit()

            CapitalCallRepository(db).recompute_status(call.id)
            db.refresh(call)
            assert call.status == CapitalCallStatus.scheduled
        finally:
            db.close()


class TestCapitalCallValidation:
    def test_create_with_unknown_fund_returns_404(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.post(
            "/capital-calls",
            json={
                "fund_id": str(uuid.uuid4()),
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        assert response.status_code == 404

    def test_create_zero_amount_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        response = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Bad Call",
                "due_date": "2026-06-01",
                "amount": "0",
            },
        )
        assert response.status_code == 422

    def test_add_item_with_cross_fund_commitment_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_a = _seed_fund(org_id, name="Fund A")
        fund_b = _seed_fund(org_id, name="Fund B")
        investor_id = _seed_investor(org_id)
        commitment_other_fund = _seed_commitment(
            fund_b, investor_id, committed_amount=Decimal("1000.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_a,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]

        response = client.post(
            f"/capital-calls/{call_id}/items",
            json={
                "items": [
                    {
                        "commitment_id": commitment_other_fund,
                        "amount_due": "1000.00",
                    }
                ]
            },
        )
        assert response.status_code == 400

    def test_duplicate_allocation_rejected(self, client, override_user):
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
        commitment_id = _seed_commitment(fund_id, investor_id)

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]

        first = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "500.00"}]},
        )
        assert first.status_code == 201

        second = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "500.00"}]},
        )
        assert second.status_code == 400

    def test_add_item_to_paid_call_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_a = _seed_investor(org_id, name="LP A")
        investor_b = _seed_investor(org_id, name="LP B")
        commitment_a = _seed_commitment(
            fund_id, investor_a, committed_amount=Decimal("1000.00")
        )
        commitment_b = _seed_commitment(
            fund_id, investor_b, committed_amount=Decimal("500.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]

        items_resp = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_a, "amount_due": "1000.00"}]},
        )
        item_id = items_resp.json()[0]["id"]
        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200

        pay_resp = client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "1000.00"},
        )
        assert pay_resp.status_code == 200
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == "paid"

        # Adding a new allocation to a fully-paid call would push total_due
        # above total_paid while the row still reads `paid` — reject outright
        # rather than letting the call silently disagree with its own totals.
        rejected = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_b, "amount_due": "500.00"}]},
        )
        assert rejected.status_code == 400

    def test_add_item_to_cancelled_call_rejected(self, client, override_user):
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
        commitment_id = _seed_commitment(fund_id, investor_id)

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        assert client.post(f"/capital-calls/{call_id}/cancel").status_code == 200

        # Adding to a call explicitly withdrawn from collection would inflate
        # committed/called aggregates for money no longer being pursued.
        response = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        )
        assert response.status_code == 400

    def test_add_item_to_sent_call_succeeds_and_recomputes_status(
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
        investor_a = _seed_investor(org_id, name="LP A")
        investor_b = _seed_investor(org_id, name="LP B")
        commitment_a = _seed_commitment(
            fund_id, investor_a, committed_amount=Decimal("1000.00")
        )
        commitment_b = _seed_commitment(
            fund_id, investor_b, committed_amount=Decimal("500.00")
        )

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                # Far in the future so recompute_status's zero-paid unwind
                # (plan 017) resolves to `sent`, not `overdue` — this test is
                # about add_items not corrupting status into paid/partially_paid,
                # not about overdue detection.
                "due_date": "2099-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]

        first_items = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_a, "amount_due": "1000.00"}]},
        )
        assert first_items.status_code == 201
        assert client.post(f"/capital-calls/{call_id}/send").status_code == 200
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == "sent"

        second_items = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_b, "amount_due": "500.00"}]},
        )
        assert second_items.status_code == 201
        # Still unpaid — recompute_status must preserve `sent`, not corrupt it.
        assert client.get(f"/capital-calls/{call_id}").json()["status"] == "sent"


class TestCapitalCallSendCancel:
    def test_cancel_from_draft(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Cancellable Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]

        cancel_resp = client.post(f"/capital-calls/{call_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

    def test_send_from_paid_rejected(self, client, override_user):
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
        commitment_id = _seed_commitment(fund_id, investor_id)

        create_resp = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        call_id = create_resp.json()["id"]
        item_id = client.post(
            f"/capital-calls/{call_id}/items",
            json={"items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]},
        ).json()[0]["id"]
        client.post(f"/capital-calls/{call_id}/send")
        client.patch(
            f"/capital-calls/{call_id}/items/{item_id}",
            json={"amount_paid": "1000.00"},
        )

        retry_send = client.post(f"/capital-calls/{call_id}/send")
        assert retry_send.status_code == 409


class TestCapitalCallRbac:
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
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Q1 Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        assert response.status_code == 403

    def test_fund_manager_cannot_create_for_other_org(self, client, override_user):
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
            "/capital-calls",
            json={
                "fund_id": fund_in_b,
                "title": "Cross-org Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        )
        assert response.status_code == 403

    def test_lp_only_sees_calls_with_their_commitments(self, client, override_user):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        own_commitment = _seed_commitment(fund_id, own_investor)
        other_commitment = _seed_commitment(fund_id, other_investor)

        # Seed two calls via the fund_manager so both have items.
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        own_call = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Own Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        ).json()["id"]
        client.post(
            f"/capital-calls/{own_call}/items",
            json={
                "items": [{"commitment_id": own_commitment, "amount_due": "1000.00"}]
            },
        )
        other_call = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Other Call",
                "due_date": "2026-06-01",
                "amount": "1000.00",
            },
        ).json()["id"]
        client.post(
            f"/capital-calls/{other_call}/items",
            json={
                "items": [{"commitment_id": other_commitment, "amount_due": "1000.00"}]
            },
        )
        # Both sent — this test isolates investor scoping, not send state.
        client.post(f"/capital-calls/{own_call}/send")
        client.post(f"/capital-calls/{other_call}/send")

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id)
        override_user("hanko-lp")

        response = client.get("/capital-calls")
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert ids == [own_call]


class TestNestedFundRoute:
    def test_lists_capital_calls_under_fund(self, client, override_user):
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

        for title, fund in (
            ("First", fund_id),
            ("Second", fund_id),
            ("Out", other_fund),
        ):
            client.post(
                "/capital-calls",
                json={
                    "fund_id": fund,
                    "title": title,
                    "due_date": "2026-06-01",
                    "amount": "1000.00",
                },
            )

        response = client.get(f"/funds/{fund_id}/capital-calls")
        assert response.status_code == 200
        titles = sorted(row["title"] for row in response.json())
        assert titles == ["First", "Second"]


class TestLpItemScoping:
    """An LP who can view a call (they hold an item) must not see other
    investors' allocation items in the payload."""

    def _seed_two_lp_call(self, client, override_user):
        org_id = _seed_org()
        investor_a = _seed_investor(org_id, name="LP A")
        investor_b = _seed_investor(org_id, name="LP B")
        fund_id = _seed_fund(org_id)
        commitment_a = _seed_commitment(fund_id, investor_a)
        commitment_b = _seed_commitment(fund_id, investor_b)

        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        call_id = client.post(
            "/capital-calls",
            json={
                "fund_id": fund_id,
                "title": "Shared Call",
                "due_date": "2026-06-01",
                "amount": "2000.00",
            },
        ).json()["id"]
        client.post(
            f"/capital-calls/{call_id}/items",
            json={
                "items": [
                    {"commitment_id": commitment_a, "amount_due": "1000.00"},
                    {"commitment_id": commitment_b, "amount_due": "1000.00"},
                ]
            },
        )
        # Send it: these tests are about per-item scoping, and LPs only ever
        # see calls that have actually gone out.
        client.post(f"/capital-calls/{call_id}/send")
        return org_id, fund_id, investor_a, commitment_a, call_id

    def test_lp_sees_only_own_items_on_detail(self, client, override_user):
        org_id, fund_id, investor_a, commitment_a, call_id = self._seed_two_lp_call(
            client, override_user
        )

        # GP sees both items.
        gp_detail = client.get(f"/capital-calls/{call_id}")
        assert gp_detail.status_code == 200
        assert len(gp_detail.json()["items"]) == 2

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(investor_a, lp_user_id)
        override_user("hanko-lp")

        lp_detail = client.get(f"/capital-calls/{call_id}")
        assert lp_detail.status_code == 200
        items = lp_detail.json()["items"]
        assert len(items) == 1
        assert items[0]["commitment_id"] == commitment_a
        # Fund-level total remains the full call amount.
        assert Decimal(lp_detail.json()["amount"]) == Decimal("2000.00")

    def test_lp_sees_only_own_items_on_lists(self, client, override_user):
        org_id, fund_id, investor_a, commitment_a, call_id = self._seed_two_lp_call(
            client, override_user
        )
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(investor_a, lp_user_id)
        override_user("hanko-lp")

        for url in ("/capital-calls", f"/funds/{fund_id}/capital-calls"):
            resp = client.get(url)
            assert resp.status_code == 200
            rows = resp.json()
            assert len(rows) == 1
            assert len(rows[0]["items"]) == 1
            assert rows[0]["items"][0]["commitment_id"] == commitment_a

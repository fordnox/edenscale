"""Integration tests for the /distributions router and the nested
/funds/{id}/distributions route, including pro-rata allocation."""

from datetime import date
from decimal import Decimal
from app.core.slugs import slugify

import pytest
from fastapi.testclient import TestClient

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
from app.models.user_organization_membership import UserOrganizationMembership


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


class TestDistributionLifecycle:
    """End-to-end: draft → items → sent → partial pay → fully paid,
    while commitment.distributed_amount tracks the per-item amount_paid sum."""

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
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1 Distribution",
                "distribution_date": "2026-06-01",
                "amount": "500.00",
            },
        )
        assert create_resp.status_code == 201
        dist = create_resp.json()
        dist_id = dist["id"]
        assert dist["status"] == "draft"
        assert dist["fund"]["id"] == fund_id

        items_resp = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [
                    {"commitment_id": commitment_id, "amount_due": "500.00"},
                ]
            },
        )
        assert items_resp.status_code == 201
        item_id = items_resp.json()[0]["id"]

        send_resp = client.post(f"/distributions/{dist_id}/send")
        assert send_resp.status_code == 200
        assert send_resp.json()["status"] == "sent"
        assert send_resp.json()["record_date"] is not None

        partial = client.patch(
            f"/distributions/{dist_id}/items/{item_id}",
            json={"amount_paid": "200.00"},
        )
        assert partial.status_code == 200

        detail = client.get(f"/distributions/{dist_id}").json()
        assert detail["status"] == "partially_paid"

        db = SessionLocal()
        try:
            assert (
                db.get(Commitment, commitment_id).distributed_amount
                == Decimal("200.00")
            )
        finally:
            db.close()

        full = client.patch(
            f"/distributions/{dist_id}/items/{item_id}",
            json={"amount_paid": "500.00"},
        )
        assert full.status_code == 200

        detail = client.get(f"/distributions/{dist_id}").json()
        assert detail["status"] == "paid"

        db = SessionLocal()
        try:
            commitment = db.get(Commitment, commitment_id)
            assert commitment.distributed_amount == Decimal("500.00")
            paid_sum = sum(
                (i.amount_paid for i in commitment.distribution_items),
                start=Decimal("0"),
            )
            assert commitment.distributed_amount == paid_sum
        finally:
            db.close()


class TestDistributionProRata:
    def test_pro_rata_splits_across_approved_commitments(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        inv_a = _seed_investor(org_id, name="LP A")
        inv_b = _seed_investor(org_id, name="LP B")
        inv_pending = _seed_investor(org_id, name="Pending LP")
        commitment_a = _seed_commitment(
            fund_id, inv_a, committed_amount=Decimal("750.00")
        )
        commitment_b = _seed_commitment(
            fund_id, inv_b, committed_amount=Decimal("250.00")
        )
        # A pending commitment must be excluded from the pro-rata split.
        _seed_commitment(
            fund_id,
            inv_pending,
            committed_amount=Decimal("1000.00"),
            status=CommitmentStatus.pending,
        )

        create_resp = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Pro-rata Distribution",
                "distribution_date": "2026-06-01",
                "amount": "100.00",
            },
        )
        dist_id = create_resp.json()["id"]

        items_resp = client.post(
            f"/distributions/{dist_id}/items?mode=pro-rata",
            json={"items": []},
        )
        assert items_resp.status_code == 201
        items = items_resp.json()
        assert len(items) == 2
        amounts = {item["commitment_id"]: Decimal(item["amount_due"]) for item in items}
        # 100 split 750:250 → 75.00 / 25.00, exact reconcile, no remainder sweep.
        assert amounts[commitment_a] == Decimal("75.00")
        assert amounts[commitment_b] == Decimal("25.00")
        assert sum(amounts.values()) == Decimal("100.00")

    def test_pro_rata_with_no_approved_commitments_returns_400(
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
        # Only a pending commitment exists — pro-rata should reject.
        _seed_commitment(
            fund_id,
            investor_id,
            committed_amount=Decimal("1000.00"),
            status=CommitmentStatus.pending,
        )

        create_resp = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Empty Pro-rata",
                "distribution_date": "2026-06-01",
                "amount": "100.00",
            },
        )
        dist_id = create_resp.json()["id"]
        response = client.post(
            f"/distributions/{dist_id}/items?mode=pro-rata",
            json={"items": []},
        )
        assert response.status_code == 400


class TestDistributionValidation:
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
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Bad",
                "distribution_date": "2026-06-01",
                "amount": "0",
            },
        )
        assert response.status_code == 422

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

        dist_id = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1",
                "distribution_date": "2026-06-01",
                "amount": "500.00",
            },
        ).json()["id"]
        first = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_id, "amount_due": "500.00"}]
            },
        )
        assert first.status_code == 201
        dup = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_id, "amount_due": "500.00"}]
            },
        )
        assert dup.status_code == 400

    def test_add_item_to_paid_distribution_rejected(self, client, override_user):
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

        dist_id = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1",
                "distribution_date": "2026-06-01",
                "amount": "1000.00",
            },
        ).json()["id"]

        items_resp = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_a, "amount_due": "1000.00"}]
            },
        )
        item_id = items_resp.json()[0]["id"]
        assert client.post(f"/distributions/{dist_id}/send").status_code == 200

        pay_resp = client.patch(
            f"/distributions/{dist_id}/items/{item_id}",
            json={"amount_paid": "1000.00"},
        )
        assert pay_resp.status_code == 200
        assert client.get(f"/distributions/{dist_id}").json()["status"] == "paid"

        # Adding a new allocation to a fully-paid distribution would push
        # total_due above total_paid while the row still reads `paid` —
        # reject outright.
        rejected = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_b, "amount_due": "500.00"}]
            },
        )
        assert rejected.status_code == 400

    def test_add_item_to_cancelled_distribution_rejected(self, client, override_user):
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

        dist_id = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1",
                "distribution_date": "2026-06-01",
                "amount": "1000.00",
            },
        ).json()["id"]
        assert client.post(f"/distributions/{dist_id}/cancel").status_code == 200

        response = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_id, "amount_due": "1000.00"}]
            },
        )
        assert response.status_code == 400

    def test_add_item_to_sent_distribution_succeeds_and_recomputes_status(
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

        dist_id = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1",
                "distribution_date": "2026-06-01",
                "amount": "1000.00",
            },
        ).json()["id"]

        first_items = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_a, "amount_due": "1000.00"}]
            },
        )
        assert first_items.status_code == 201
        assert client.post(f"/distributions/{dist_id}/send").status_code == 200
        assert client.get(f"/distributions/{dist_id}").json()["status"] == "sent"

        second_items = client.post(
            f"/distributions/{dist_id}/items",
            json={
                "items": [{"commitment_id": commitment_b, "amount_due": "500.00"}]
            },
        )
        assert second_items.status_code == 201
        # Still unpaid — recompute_status must preserve `sent`, not corrupt it.
        assert client.get(f"/distributions/{dist_id}").json()["status"] == "sent"


class TestDistributionRbac:
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
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Q1",
                "distribution_date": "2026-06-01",
                "amount": "100.00",
            },
        )
        assert response.status_code == 403

    def test_lp_only_sees_distributions_with_their_commitments(
        self, client, override_user
    ):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        own_commitment = _seed_commitment(fund_id, own_investor)
        other_commitment = _seed_commitment(fund_id, other_investor)

        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        own_dist = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Own",
                "distribution_date": "2026-06-01",
                "amount": "100.00",
            },
        ).json()["id"]
        client.post(
            f"/distributions/{own_dist}/items",
            json={
                "items": [{"commitment_id": own_commitment, "amount_due": "100.00"}]
            },
        )
        other_dist = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Other",
                "distribution_date": "2026-06-01",
                "amount": "100.00",
            },
        ).json()["id"]
        client.post(
            f"/distributions/{other_dist}/items",
            json={
                "items": [{"commitment_id": other_commitment, "amount_due": "100.00"}]
            },
        )

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id)
        override_user("hanko-lp")

        response = client.get("/distributions")
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert ids == [own_dist]


class TestNestedFundRoute:
    def test_lists_distributions_under_fund(self, client, override_user):
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

        for title, fund in (("First", fund_id), ("Second", fund_id), ("Out", other_fund)):
            client.post(
                "/distributions",
                json={
                    "fund_id": fund,
                    "title": title,
                    "distribution_date": "2026-06-01",
                    "amount": "100.00",
                },
            )

        response = client.get(f"/funds/{fund_id}/distributions")
        assert response.status_code == 200
        titles = sorted(row["title"] for row in response.json())
        assert titles == ["First", "Second"]


class TestLpItemScoping:
    """An LP who can view a distribution must not see other investors'
    allocation items in the payload."""

    def test_lp_sees_only_own_items(self, client, override_user):
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
        distribution_id = client.post(
            "/distributions",
            json={
                "fund_id": fund_id,
                "title": "Shared Distribution",
                "distribution_date": "2026-06-01",
                "amount": "2000.00",
            },
        ).json()["id"]
        client.post(
            f"/distributions/{distribution_id}/items",
            json={
                "items": [
                    {"commitment_id": commitment_a, "amount_due": "1000.00"},
                    {"commitment_id": commitment_b, "amount_due": "1000.00"},
                ]
            },
        )

        gp_detail = client.get(f"/distributions/{distribution_id}")
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

        lp_detail = client.get(f"/distributions/{distribution_id}")
        assert lp_detail.status_code == 200
        items = lp_detail.json()["items"]
        assert len(items) == 1
        assert items[0]["commitment_id"] == commitment_a

        for url in ("/distributions", f"/funds/{fund_id}/distributions"):
            resp = client.get(url)
            assert resp.status_code == 200
            rows = resp.json()
            assert len(rows) == 1
            assert len(rows[0]["items"]) == 1
            assert rows[0]["items"][0]["commitment_id"] == commitment_a

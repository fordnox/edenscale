"""Integration tests for the /investor portal namespace.

Portal access is derived from contact links, never membership rows: staff
(admin/fund_manager) with links get their personal investor view; users with
no links get nothing, membership or not.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
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


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_org(name: str = "NewTaven Capital") -> str:
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
    organization_id: str | None = None,
) -> str:
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


def _seed_investor(organization_id: str, *, name: str = "Acme LP") -> str:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name)
        db.add(investor)
        db.commit()
        return str(investor.id)
    finally:
        db.close()


def _seed_contact(investor_id: str, *, user_id: str | None = None) -> str:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name="Pat",
            last_name="Lp",
        )
        db.add(contact)
        db.commit()
        return str(contact.id)
    finally:
        db.close()


def _seed_fund(organization_id: str, *, name: str = "NewTaven Fund I") -> str:
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


def _seed_commitment(fund_id: str, investor_id: str) -> str:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=Decimal("250000.00"),
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.commit()
        return str(commitment.id)
    finally:
        db.close()


class TestInvestorOrganizations:
    def test_lists_orgs_via_contact_links_without_membership(
        self, client, override_user
    ):
        """A user with a contact link but NO membership row still gets the org
        — links, not membership, grant portal access."""
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        user_id = _seed_user("hanko-inv", UserRole.lp)  # no membership anywhere
        _seed_contact(_seed_investor(org_a), user_id=user_id)
        override_user("hanko-inv")

        response = client.get("/investor/organizations")

        assert response.status_code == 200
        rows = response.json()
        assert [r["organization_id"] for r in rows] == [org_a]
        assert rows[0]["organization"]["name"] == "Org A"
        assert org_b not in [r["organization_id"] for r in rows]

    def test_membership_without_links_grants_nothing(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        override_user("hanko-admin")

        assert client.get("/investor/organizations").json() == []
        response = client.get("/investor/funds", headers={"X-Organization-Id": org_id})
        assert response.status_code == 403


class TestInvestorScopedReads:
    def test_admin_sees_only_their_linked_investor_data(self, client, override_user):
        """A fund admin who personally invested sees their own slice in the
        portal, not the org-wide view their staff role would grant."""
        org_id = _seed_org()
        admin_id = _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        own = _seed_investor(org_id, name="Admin Family LP")
        other = _seed_investor(org_id, name="Other LP")
        _seed_contact(own, user_id=admin_id)
        own_fund = _seed_fund(org_id, name="Fund One")
        other_fund = _seed_fund(org_id, name="Fund Two")
        _seed_commitment(own_fund, own)
        _seed_commitment(other_fund, other)
        override_user("hanko-admin")
        headers = {"X-Organization-Id": org_id}

        investors = client.get("/investor/investors", headers=headers).json()
        assert [r["name"] for r in investors] == ["Admin Family LP"]

        funds = client.get("/investor/funds", headers=headers).json()
        assert [f["name"] for f in funds] == ["Fund One"]

        commitments = client.get("/investor/commitments", headers=headers).json()
        assert len(commitments) == 1

        overview = client.get("/investor/dashboard/overview", headers=headers).json()
        assert overview["investors_total"] == 1

    def test_admin_does_not_see_own_draft_in_the_portal(self, client, override_user):
        """Staff who are also investors must not see drafts they authored.

        In the portal the caller acts as an LP, so a draft they wrote wearing
        their staff hat is still an unsent letter here. This is the realistic
        leak: the same person composes and previews, so the sender match fires.
        """
        org_id = _seed_org()
        admin_id = _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        own = _seed_investor(org_id, name="Admin Family LP")
        _seed_contact(own, user_id=admin_id)
        fund_id = _seed_fund(org_id)
        _seed_commitment(fund_id, own)
        override_user("hanko-admin")
        headers = {"X-Organization-Id": org_id}

        draft_id = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Not ready",
                "body": "Unreviewed",
            },
            headers=headers,
        ).json()["id"]

        listing = client.get("/investor/communications", headers=headers)
        assert listing.status_code == 200
        assert draft_id not in [row["id"] for row in listing.json()]

        # Their staff role still shows it in the manager-side view.
        manager_listing = client.get("/communications", headers=headers).json()
        assert draft_id in [row["id"] for row in manager_listing]

    def test_org_header_without_links_in_that_org_is_403(self, client, override_user):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        user_id = _seed_user("hanko-inv", UserRole.lp)
        _seed_contact(_seed_investor(org_a), user_id=user_id)
        override_user("hanko-inv")

        response = client.get("/investor/funds", headers={"X-Organization-Id": org_b})
        assert response.status_code == 403

    def test_single_linked_org_resolves_without_header(self, client, override_user):
        org_id = _seed_org()
        user_id = _seed_user("hanko-inv", UserRole.lp)
        investor = _seed_investor(org_id)
        _seed_contact(investor, user_id=user_id)
        fund = _seed_fund(org_id)
        _seed_commitment(fund, investor)
        override_user("hanko-inv")

        response = client.get("/investor/funds")
        assert response.status_code == 200
        assert len(response.json()) == 1

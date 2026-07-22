"""LP-visibility regression suite.

Each test here pins a leak that was live in production and confirmed by
reproduction before being fixed. Two bug classes are covered:

* an owner/creator shortcut (``uploaded_by_user_id``) evaluated on the LP
  path, which carries no organization predicate and so crosses tenants;
* internal lifecycle state (draft funds / capital calls / distributions)
  not filtered out of LP-facing queries.

Staff who are also linked investor contacts enter the portal with a
transient ``role=lp`` membership, which is what makes both classes
reachable. See app/core/investor_access.py.
"""

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
    Distribution,
    DistributionItem,
    DistributionStatus,
    Document,
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


def _org(name):
    db = SessionLocal()
    try:
        o = Organization(
            name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
        )
        db.add(o)
        db.commit()
        return str(o.id)
    finally:
        db.close()


def _user(subject, role=None, org=None):
    db = SessionLocal()
    try:
        u = User(
            first_name="A",
            last_name="B",
            email=f"{subject}@x.com",
            hanko_subject_id=subject,
        )
        db.add(u)
        db.flush()
        if org is not None:
            db.add(
                UserOrganizationMembership(user_id=u.id, organization_id=org, role=role)
            )
        db.commit()
        return str(u.id)
    finally:
        db.close()


def _fund(org, name="Fund I", status=FundStatus.active):
    db = SessionLocal()
    try:
        f = Fund(organization_id=org, name=name, slug=slugify(name), status=status)
        db.add(f)
        db.commit()
        return str(f.id)
    finally:
        db.close()


def _investor(org, name="LP"):
    db = SessionLocal()
    try:
        i = Investor(organization_id=org, name=name)
        db.add(i)
        db.commit()
        return str(i.id)
    finally:
        db.close()


def _contact(investor, user_id):
    db = SessionLocal()
    try:
        c = InvestorContact(
            investor_id=investor,
            user_id=user_id,
            first_name="L",
            last_name="C",
            is_primary=True,
        )
        db.add(c)
        db.commit()
        return str(c.id)
    finally:
        db.close()


def _commitment(fund, investor):
    db = SessionLocal()
    try:
        c = Commitment(
            fund_id=fund,
            investor_id=investor,
            committed_amount=Decimal("100000.00"),
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(c)
        db.commit()
        return str(c.id)
    finally:
        db.close()


class TestLpVisibilityRegressions:
    def test_draft_capital_call_hidden_from_lp(self, client, override_user):
        org = _org("Org A")
        admin = _user("hanko-admin", UserRole.admin, org)
        inv = _investor(org)
        _contact(inv, admin)
        fund = _fund(org)
        comm_id = _commitment(fund, inv)

        db = SessionLocal()
        try:
            call = CapitalCall(
                fund_id=fund,
                title="Unsent Call",
                amount=Decimal("50000.00"),
                due_date=date(2026, 3, 1),
                status=CapitalCallStatus.draft,
                created_by_user_id=admin,
            )
            db.add(call)
            db.flush()
            db.add(
                CapitalCallItem(
                    capital_call_id=call.id,
                    commitment_id=comm_id,
                    amount_due=Decimal("20000.00"),
                )
            )
            db.commit()
            call_id = str(call.id)
        finally:
            db.close()

        override_user("hanko-admin")
        rows = client.get(
            "/investor/capital-calls", headers={"X-Organization-Id": org}
        ).json()
        assert call_id not in [r["id"] for r in rows], "draft capital call leaked to LP"

    def test_draft_distribution_hidden_from_lp(self, client, override_user):
        org = _org("Org A")
        admin = _user("hanko-admin", UserRole.admin, org)
        inv = _investor(org)
        _contact(inv, admin)
        fund = _fund(org)
        comm_id = _commitment(fund, inv)

        db = SessionLocal()
        try:
            dist = Distribution(
                fund_id=fund,
                title="Unsent Dist",
                amount=Decimal("50000.00"),
                distribution_date=date(2026, 3, 1),
                status=DistributionStatus.draft,
                created_by_user_id=admin,
            )
            db.add(dist)
            db.flush()
            db.add(
                DistributionItem(
                    distribution_id=dist.id,
                    commitment_id=comm_id,
                    amount_due=Decimal("20000.00"),
                )
            )
            db.commit()
            dist_id = str(dist.id)
        finally:
            db.close()

        override_user("hanko-admin")
        rows = client.get(
            "/investor/distributions", headers={"X-Organization-Id": org}
        ).json()
        assert dist_id not in [r["id"] for r in rows], "draft distribution leaked to LP"

    def test_draft_fund_hidden_from_lp(self, client, override_user):
        org = _org("Org A")
        admin = _user("hanko-admin", UserRole.admin, org)
        inv = _investor(org)
        _contact(inv, admin)
        fund = _fund(org, name="Secret Fund", status=FundStatus.draft)
        _commitment(fund, inv)

        override_user("hanko-admin")
        rows = client.get("/investor/funds", headers={"X-Organization-Id": org}).json()
        assert fund not in [r["id"] for r in rows], "draft fund leaked to LP"

    def test_lp_cannot_see_another_investors_fund_document(self, client, override_user):
        """Clause 3 matches on fund alone, ignoring investor_id."""
        org = _org("Org A")
        fund = _fund(org)
        inv_a = _investor(org, name="Investor A")
        inv_b = _investor(org, name="Investor B")
        user_b = _user("hanko-b", UserRole.lp, org)
        uploader = _user("hanko-staff", UserRole.admin, org)
        _contact(inv_b, user_b)
        _commitment(fund, inv_a)
        _commitment(fund, inv_b)

        db = SessionLocal()
        try:
            doc = Document(
                organization_id=org,
                fund_id=fund,
                investor_id=inv_a,  # belongs to A, not B
                title="Investor A side letter",
                document_type="other",
                file_name="f.pdf",
                file_url="local://k",
                is_confidential=False,
                uploaded_by_user_id=uploader,  # NOT the caller
            )
            db.add(doc)
            db.commit()
            doc_id = str(doc.id)
        finally:
            db.close()

        override_user("hanko-b")
        rows = client.get(
            "/investor/documents", headers={"X-Organization-Id": org}
        ).json()
        leaked = [r for r in rows if r["id"] == doc_id]
        assert not leaked, "investor B received investor A's document" + (
            f" WITH download url: {leaked[0].get('download_url')}" if leaked else ""
        )

    def test_uploader_shortcut_does_not_cross_tenants(self, client, override_user):
        """The severe one: the LP document filter's uploader arm is org-blind."""
        org_a = _org("Org A")
        org_b = _org("Org B")
        # Staff in BOTH orgs, and an investor contact only in Org A.
        user = _user("hanko-multi", UserRole.admin, org_a)
        db = SessionLocal()
        try:
            db.add(
                UserOrganizationMembership(
                    user_id=user, organization_id=org_b, role=UserRole.admin
                )
            )
            db.commit()
        finally:
            db.close()
        inv_a = _investor(org_a, name="My LP")
        _contact(inv_a, user)

        # A confidential Org B document this user uploaded as staff there.
        other_inv_b = _investor(org_b, name="Someone Else LP")
        fund_b = _fund(org_b, name="Fund B")
        db = SessionLocal()
        try:
            doc = Document(
                organization_id=org_b,
                fund_id=fund_b,
                investor_id=other_inv_b,
                title="Org B confidential",
                document_type="other",
                file_name="f.pdf",
                file_url="local://k",
                is_confidential=True,
                uploaded_by_user_id=user,
            )
            db.add(doc)
            db.commit()
            doc_id = str(doc.id)
        finally:
            db.close()

        override_user("hanko-multi")
        rows = client.get(
            "/investor/documents", headers={"X-Organization-Id": org_a}
        ).json()
        assert doc_id not in [
            r["id"] for r in rows
        ], "cross-tenant confidential document leaked into Org A portal"

"""Integration tests for the /funds/{fund_id}/team routes."""

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
    Fund,
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
    first_name: str = "First",
    last_name: str = "Last",
) -> str:
    db = SessionLocal()
    try:
        user = User(
            organization_id=organization_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
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


def _seed_fund(organization_id: str, *, name: str = "NewTaven Fund I") -> str:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name, slug=slugify(name))
        db.add(fund)
        db.commit()
        return str(fund.id)
    finally:
        db.close()


class TestFundTeamMembers:
    def test_add_list_update_remove_with_user_summary(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        analyst_id = _seed_user(
            "hanko-analyst",
            UserRole.fund_manager,
            email="analyst@example.com",
            organization_id=org_id,
            first_name="Ana",
            last_name="Lyst",
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        create_resp = client.post(
            f"/funds/{fund_id}/team",
            json={"user_id": analyst_id, "title": "Analyst"},
        )
        assert create_resp.status_code == 201
        member = create_resp.json()
        assert member["user_id"] == analyst_id
        assert member["title"] == "Analyst"
        assert member["user"]["first_name"] == "Ana"
        assert member["user"]["last_name"] == "Lyst"
        assert member["user"]["email"] == "analyst@example.com"

        list_resp = client.get(f"/funds/{fund_id}/team")
        assert list_resp.status_code == 200
        roster = list_resp.json()
        assert len(roster) == 1
        assert roster[0]["user"]["email"] == "analyst@example.com"

        update_resp = client.patch(
            f"/funds/{fund_id}/team/{member['id']}",
            json={"title": "Senior Analyst"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Senior Analyst"
        assert update_resp.json()["user"]["first_name"] == "Ana"

        delete_resp = client.delete(f"/funds/{fund_id}/team/{member['id']}")
        assert delete_resp.status_code == 200
        assert client.get(f"/funds/{fund_id}/team").json() == []

    def test_add_rejects_user_outside_fund_org(self, client, override_user):
        org_id = _seed_org()
        other_org = _seed_org("Other Firm")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        outsider_id = _seed_user(
            "hanko-outsider",
            UserRole.fund_manager,
            email="outsider@example.com",
            organization_id=other_org,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        resp = client.post(
            f"/funds/{fund_id}/team",
            json={"user_id": outsider_id, "title": "Analyst"},
        )
        assert resp.status_code == 400
        assert "not a member" in resp.json()["detail"]

    def test_duplicate_member_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        analyst_id = _seed_user(
            "hanko-analyst",
            UserRole.fund_manager,
            email="analyst@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        first = client.post(f"/funds/{fund_id}/team", json={"user_id": analyst_id})
        assert first.status_code == 201
        second = client.post(f"/funds/{fund_id}/team", json={"user_id": analyst_id})
        assert second.status_code == 409

    def test_lp_cannot_add_team_member(self, client, override_user):
        org_id = _seed_org()
        analyst_id = _seed_user(
            "hanko-analyst",
            UserRole.fund_manager,
            email="analyst@example.com",
            organization_id=org_id,
        )
        _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        override_user("hanko-lp")
        fund_id = _seed_fund(org_id)

        resp = client.post(f"/funds/{fund_id}/team", json={"user_id": analyst_id})
        assert resp.status_code == 403

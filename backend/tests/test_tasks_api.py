"""Integration tests for the /tasks router and the nested
/funds/{id}/tasks route."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Fund,
    Organization,
    OrganizationType,
    Task,
    TaskStatus,
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


def _seed_task(
    *,
    fund_id: int | None = None,
    assigned_to_user_id: int | None = None,
    created_by_user_id: int | None = None,
    title: str = "Do the thing",
    status: TaskStatus = TaskStatus.open,
    due_date: date | None = None,
) -> int:
    db = SessionLocal()
    try:
        task = Task(
            fund_id=fund_id,
            assigned_to_user_id=assigned_to_user_id,
            created_by_user_id=created_by_user_id,
            title=title,
            status=status,
            due_date=due_date,
        )
        db.add(task)
        db.commit()
        return task.id
    finally:
        db.close()


class TestTaskLifecycle:
    def test_fm_can_create_task(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        resp = client.post(
            "/tasks",
            json={
                "fund_id": fund_id,
                "title": "Draft Q1 letter",
                "description": "Send to LPs by Friday",
                "due_date": "2026-05-10",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "open"
        assert body["fund_id"] == fund_id
        assert body["title"] == "Draft Q1 letter"
        assert body["due_date"] == "2026-05-10"
        assert body["completed_at"] is None

    def test_complete_sets_status_done_and_timestamp(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )

        resp = client.post(f"/tasks/{task_id}/complete")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["completed_at"] is not None

    def test_complete_idempotent(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )

        first = client.post(f"/tasks/{task_id}/complete")
        assert first.status_code == 200
        second = client.post(f"/tasks/{task_id}/complete")
        assert second.status_code == 200
        assert second.json()["status"] == "done"

    def test_complete_cancelled_returns_409(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
            status=TaskStatus.cancelled,
        )

        resp = client.post(f"/tasks/{task_id}/complete")
        assert resp.status_code == 409

    def test_patch_to_done_stamps_completed_at(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )

        resp = client.patch(
            f"/tasks/{task_id}",
            json={"status": "done"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["completed_at"] is not None


class TestTaskListing:
    def test_default_lists_tasks_assigned_to_current_user(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        other_fm_id = _seed_user(
            "hanko-other-fm",
            UserRole.fund_manager,
            email="other-fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        my_task = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
            title="Mine",
        )
        _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=other_fm_id,
            created_by_user_id=other_fm_id,
            title="Theirs",
        )

        resp = client.get("/tasks")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert my_task in ids
        assert len(ids) == 1

    def test_fund_id_filter_disables_default_assignee_scope(
        self, client, override_user
    ):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        other_fm_id = _seed_user(
            "hanko-other-fm",
            UserRole.fund_manager,
            email="other-fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        mine = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
            title="Mine",
        )
        theirs = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=other_fm_id,
            created_by_user_id=fm_id,
            title="Theirs",
        )

        resp = client.get(f"/tasks?fund_id={fund_id}")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert mine in ids
        assert theirs in ids

    def test_assignee_filter_for_fund_manager(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        other_fm_id = _seed_user(
            "hanko-other-fm",
            UserRole.fund_manager,
            email="other-fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
            title="Mine",
        )
        theirs = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=other_fm_id,
            created_by_user_id=fm_id,
            title="Theirs",
        )

        resp = client.get(f"/tasks?assignee={other_fm_id}")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert ids == [theirs]

    def test_nested_fund_route_lists_tasks(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        other_fund_id = _seed_fund(org_id, name="Sibling Fund")
        in_fund = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )
        _seed_task(
            fund_id=other_fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )

        resp = client.get(f"/funds/{fund_id}/tasks")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert ids == [in_fund]


class TestTaskRbac:
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

        resp = client.post(
            "/tasks",
            json={"fund_id": fund_id, "title": "Hi"},
        )
        assert resp.status_code == 403

    def test_fm_cannot_create_on_other_org_fund(self, client, override_user):
        org_a = _seed_org(name="Org A")
        org_b = _seed_org(name="Org B")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_a,
        )
        override_user("hanko-fm")
        other_fund = _seed_fund(org_b, name="Other Org Fund")

        resp = client.post(
            "/tasks",
            json={"fund_id": other_fund, "title": "Trespass"},
        )
        assert resp.status_code == 403

    def test_lp_can_complete_assigned_task(self, client, override_user):
        org_id = _seed_org()
        lp_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=lp_id,
            created_by_user_id=fm_id,
            title="Sign docs",
        )

        override_user("hanko-lp")
        resp = client.post(f"/tasks/{task_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_lp_cannot_complete_other_users_task(self, client, override_user):
        org_id = _seed_org()
        lp_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        other_lp_id = _seed_user(
            "hanko-other-lp",
            UserRole.lp,
            email="other-lp@example.com",
            organization_id=org_id,
        )
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=other_lp_id,
            created_by_user_id=fm_id,
        )
        # silence unused warning (lp_id seeded for symmetry)
        assert lp_id != other_lp_id

        override_user("hanko-lp")
        resp = client.post(f"/tasks/{task_id}/complete")
        assert resp.status_code == 403

    def test_lp_cannot_view_unassigned_task(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        fund_id = _seed_fund(org_id)
        task_id = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
        )

        override_user("hanko-lp")
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 403

    def test_lp_listing_only_returns_their_tasks(self, client, override_user):
        org_id = _seed_org()
        lp_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        fund_id = _seed_fund(org_id)
        own = _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=lp_id,
            created_by_user_id=fm_id,
            title="Mine",
        )
        _seed_task(
            fund_id=fund_id,
            assigned_to_user_id=fm_id,
            created_by_user_id=fm_id,
            title="Theirs",
        )

        override_user("hanko-lp")
        resp = client.get("/tasks")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert ids == [own]

    def test_fm_cannot_edit_other_org_task(self, client, override_user):
        org_a = _seed_org(name="Org A")
        org_b = _seed_org(name="Org B")
        fm_a_id = _seed_user(
            "hanko-fm-a",
            UserRole.fund_manager,
            email="fm-a@example.com",
            organization_id=org_a,
        )
        fm_b_id = _seed_user(
            "hanko-fm-b",
            UserRole.fund_manager,
            email="fm-b@example.com",
            organization_id=org_b,
        )
        fund_b_id = _seed_fund(org_b, name="Other Fund")
        task_id = _seed_task(
            fund_id=fund_b_id,
            assigned_to_user_id=fm_b_id,
            created_by_user_id=fm_b_id,
        )
        # silence unused warning
        assert fm_a_id != fm_b_id

        override_user("hanko-fm-a")
        resp = client.patch(f"/tasks/{task_id}", json={"title": "Hijack"})
        assert resp.status_code == 403

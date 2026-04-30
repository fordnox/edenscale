"""Unit tests for the ``promote_superadmin`` CLI.

The CLI flips a user's role to ``superadmin`` and clears their
``organization_id`` (superadmins are global, not scoped to a single org).
We invoke ``main(email)`` directly so we don't shell out from the test.
"""

import pytest

from app.core.database import Base, SessionLocal, engine
from app.models import Organization, OrganizationType, User, UserRole
from scripts.promote_superadmin import main


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_user(
    email: str,
    role: UserRole = UserRole.fund_manager,
    organization_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        user = User(
            organization_id=organization_id,
            role=role,
            first_name="First",
            last_name="Last",
            email=email,
            hanko_subject_id=email,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


class TestPromoteSuperadmin:
    def test_flips_role_and_clears_organization_id(self, capsys):
        org_id = _seed_org()
        user_id = _seed_user(
            "candidate@example.com",
            role=UserRole.fund_manager,
            organization_id=org_id,
        )

        main("candidate@example.com")

        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            assert user.role is UserRole.superadmin
            assert user.organization_id is None
        finally:
            db.close()

        out = capsys.readouterr().out
        assert "candidate@example.com" in out
        assert "superadmin" in out

    def test_idempotent_on_already_superadmin(self):
        _seed_user(
            "already@example.com",
            role=UserRole.superadmin,
            organization_id=None,
        )

        main("already@example.com")

        db = SessionLocal()
        try:
            user = (
                db.query(User).filter(User.email == "already@example.com").one()
            )
            assert user.role is UserRole.superadmin
            assert user.organization_id is None
        finally:
            db.close()

    def test_raises_system_exit_for_unknown_user(self):
        with pytest.raises(SystemExit) as excinfo:
            main("nobody@example.com")
        assert "nobody@example.com" in str(excinfo.value)

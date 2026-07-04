"""Unit tests for the ``promote_superadmin`` CLI.

The CLI flips a user's global role to ``superadmin`` (superadmins are
global, not scoped to a single org). We invoke ``main(email)`` directly so
we don't shell out from the test.
"""

import pytest

from app.core.database import Base, SessionLocal, engine
from app.models import User, UserRole
from scripts.promote_superadmin import main


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_user(
    email: str,
    role: UserRole = UserRole.fund_manager,
) -> int:
    db = SessionLocal()
    try:
        user = User(
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


class TestPromoteSuperadmin:
    def test_flips_role_to_superadmin(self, capsys):
        user_id = _seed_user(
            "candidate@example.com",
            role=UserRole.fund_manager,
        )

        main("candidate@example.com")

        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            assert user.role is UserRole.superadmin
        finally:
            db.close()

        out = capsys.readouterr().out
        assert "candidate@example.com" in out
        assert "superadmin" in out

    def test_idempotent_on_already_superadmin(self):
        _seed_user(
            "already@example.com",
            role=UserRole.superadmin,
        )

        main("already@example.com")

        db = SessionLocal()
        try:
            user = (
                db.query(User).filter(User.email == "already@example.com").one()
            )
            assert user.role is UserRole.superadmin
        finally:
            db.close()

    def test_raises_system_exit_for_unknown_user(self):
        with pytest.raises(SystemExit) as excinfo:
            main("nobody@example.com")
        assert "nobody@example.com" in str(excinfo.value)

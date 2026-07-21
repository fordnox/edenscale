"""Tests for the auth/RBAC layer.

User resolution and first-login provisioning live in
`UserRepository.get_or_provision_by_hanko_id` (exercised here directly against
the SQLAlchemy session). Superadmins are defined purely by the
``SUPERADMIN_EMAIL`` setting — `User.is_superadmin` and `require_superadmin`
read config, never the database. No FastAPI client needed.
"""

import pytest
from fastapi import HTTPException

from app.core.auth import _extract_email_from_hanko_payload
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.rbac import require_superadmin
from app.core.slugs import slugify
from app.models import Organization, OrganizationType, User
from app.repositories.user_repository import UserRepository


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_unknown_subject_is_auto_provisioned(db):
    user, is_new = UserRepository(db).get_or_provision_by_hanko_id(
        hanko_id="hanko-new-1",
        email="new@example.com",
        first_name="Ada",
        last_name="Lovelace",
    )

    assert is_new is True
    assert user.id is not None
    assert user.hanko_subject_id == "hanko-new-1"
    assert user.email == "new@example.com"
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"


def test_extract_email_from_hanko_payload_handles_object():
    """Hanko may deliver `email` as a nested object; auth normalises it before
    the value ever reaches the repository.
    """
    payload = {
        "sub": "hanko-new-3",
        "email": {
            "address": "arturas@example.com",
            "is_primary": True,
            "is_verified": False,
        },
    }

    assert _extract_email_from_hanko_payload(payload) == "arturas@example.com"


def test_provision_without_email_raises(db):
    """A new subject with no email cannot be provisioned (email is NOT NULL and
    unique); the repository signals this with `ValueError`, which auth maps to
    a 401.
    """
    with pytest.raises(ValueError):
        UserRepository(db).get_or_provision_by_hanko_id(
            hanko_id="hanko-new-2",
            email=None,
        )


def test_auto_provision_derives_name_when_claims_missing(db):
    user, is_new = UserRepository(db).get_or_provision_by_hanko_id(
        hanko_id="hanko-new-4",
        email="solo@example.com",
    )

    assert is_new is True
    assert user.email == "solo@example.com"
    assert user.first_name == "Solo"  # derived from the email local part
    assert user.last_name == ""


def test_existing_user_is_returned_unchanged(db):
    org = Organization(
        name="NewTaven Capital",
        slug=slugify("NewTaven Capital"),
        type=OrganizationType.fund_manager_firm,
    )
    db.add(org)
    db.flush()
    existing = User(
        first_name="Margot",
        last_name="Lane",
        email="margot@example.com",
        hanko_subject_id="hanko-existing",
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id

    user, is_new = UserRepository(db).get_or_provision_by_hanko_id(
        hanko_id="hanko-existing",
        email="should-not-overwrite@example.com",
        first_name="ShouldNotOverwrite",
    )

    assert is_new is False
    assert user.id == existing_id
    assert user.email == "margot@example.com"
    assert user.first_name == "Margot"


def test_seed_row_is_claimed_by_email_on_first_signin(db):
    """Pre-provisioned user (e.g. from `make seed`) has hanko_subject_id=None.
    First Hanko sign-in with the matching email claim should bind the row by
    setting `hanko_subject_id`, not create a duplicate user.
    """
    org = Organization(
        name="NewTaven Capital",
        slug=slugify("NewTaven Capital"),
        type=OrganizationType.fund_manager_firm,
    )
    db.add(org)
    db.flush()
    seeded = User(
        first_name="Ava",
        last_name="Morgan",
        email="ava.morgan@newtaven.demo",
        hanko_subject_id=None,
    )
    db.add(seeded)
    db.commit()
    seeded_id = seeded.id

    user, is_new = UserRepository(db).get_or_provision_by_hanko_id(
        hanko_id="hanko-claim-1",
        email="ava.morgan@newtaven.demo",
    )

    assert is_new is False
    assert user.id == seeded_id
    assert user.hanko_subject_id == "hanko-claim-1"
    assert db.query(User).filter(User.email == "ava.morgan@newtaven.demo").count() == 1


def test_seed_claim_refuses_when_email_already_linked(db):
    """If the email is already linked to a different `hanko_subject_id`, the
    second sign-in must NOT rebind the row (would be account takeover) and
    must NOT 500 on the unique-email constraint when provisioning a duplicate.
    The repository raises `ValueError` (mapped to a 401 by auth) instead.
    """
    org = Organization(
        name="NewTaven Capital",
        slug=slugify("NewTaven Capital"),
        type=OrganizationType.fund_manager_firm,
    )
    db.add(org)
    db.flush()
    existing = User(
        first_name="Ava",
        last_name="Morgan",
        email="ava.morgan@newtaven.demo",
        hanko_subject_id="hanko-original",
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id

    with pytest.raises(ValueError):
        UserRepository(db).get_or_provision_by_hanko_id(
            hanko_id="hanko-impostor",
            email="ava.morgan@newtaven.demo",
        )

    rebound = db.query(User).filter(User.id == existing_id).one()
    assert rebound.hanko_subject_id == "hanko-original"
    assert db.query(User).filter(User.email == "ava.morgan@newtaven.demo").count() == 1


def _user(email: str) -> User:
    return User(
        first_name="A",
        last_name="B",
        email=email,
        hanko_subject_id="x",
    )


class TestConfigDefinedSuperadmin:
    def test_is_superadmin_matches_configured_email(self, monkeypatch):
        monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "root@example.com")
        assert _user("root@example.com").is_superadmin is True
        assert _user("someone-else@example.com").is_superadmin is False

    def test_match_is_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "Root@Example.COM")
        assert _user("ROOT@example.com").is_superadmin is True

    def test_supports_comma_separated_list(self, monkeypatch):
        monkeypatch.setattr(
            settings, "SUPERADMIN_EMAIL", "root@example.com, ops@example.com"
        )
        assert _user("ops@example.com").is_superadmin is True
        assert _user("root@example.com").is_superadmin is True
        assert _user("other@example.com").is_superadmin is False

    def test_empty_setting_means_no_superadmins(self, monkeypatch):
        monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "")
        assert _user("root@example.com").is_superadmin is False

    def test_require_superadmin_allows_configured_email(self, monkeypatch):
        monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "root@example.com")
        user = _user("root@example.com")

        assert require_superadmin(current_user=user) is user

    def test_require_superadmin_rejects_unconfigured_email(self, monkeypatch):
        monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "root@example.com")

        with pytest.raises(HTTPException) as excinfo:
            require_superadmin(current_user=_user("a@b.com"))
        assert excinfo.value.status_code == 403
        assert excinfo.value.detail == "Superadmin role required"

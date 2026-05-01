"""Tests for the RBAC layer in `app.core.rbac`.

These exercise `get_current_user_record` (auto-provisioning) and the
`require_roles` factory directly with the SQLAlchemy session — no FastAPI
client needed.
"""

import pytest
from fastapi import HTTPException

from app.core.database import Base, SessionLocal, engine
from app.core.rbac import get_current_user_record, require_roles, require_superadmin
from app.models import Organization, OrganizationType, User, UserRole


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
    payload = {
        "sub": "hanko-new-1",
        "email": "new@example.com",
        "given_name": "Ada",
        "family_name": "Lovelace",
    }

    user = get_current_user_record(payload=payload, db=db)

    assert user.id is not None
    assert user.hanko_subject_id == "hanko-new-1"
    assert user.role == UserRole.lp
    assert user.email == "new@example.com"
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"


def test_auto_provision_extracts_address_from_hanko_email_object(db):
    payload = {
        "sub": "hanko-new-3",
        "email": {
            "address": "arturas@example.com",
            "is_primary": True,
            "is_verified": False,
        },
    }

    user = get_current_user_record(payload=payload, db=db)

    assert user.email == "arturas@example.com"


def test_auto_provision_falls_back_to_blanks_when_claims_missing(db):
    payload = {"sub": "hanko-new-2"}

    user = get_current_user_record(payload=payload, db=db)

    assert user.role == UserRole.lp
    assert user.email == ""
    assert user.first_name == ""
    assert user.last_name == ""


def test_existing_user_is_returned_unchanged(db):
    org = Organization(name="Eden Capital", type=OrganizationType.fund_manager_firm)
    db.add(org)
    db.flush()
    existing = User(
        organization_id=org.id,
        role=UserRole.fund_manager,
        first_name="Margot",
        last_name="Lane",
        email="margot@example.com",
        hanko_subject_id="hanko-existing",
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id

    payload = {
        "sub": "hanko-existing",
        "email": "should-not-overwrite@example.com",
        "given_name": "ShouldNotOverwrite",
    }
    user = get_current_user_record(payload=payload, db=db)

    assert user.id == existing_id
    assert user.role == UserRole.fund_manager
    assert user.email == "margot@example.com"
    assert user.first_name == "Margot"


def test_seed_row_is_claimed_by_email_on_first_signin(db):
    """Pre-provisioned user (e.g. from `make seed`) has hanko_subject_id=None.
    First Hanko sign-in with the matching email claim should bind the row by
    setting `hanko_subject_id`, not create a duplicate `lp` user.
    """
    org = Organization(name="Eden Capital", type=OrganizationType.fund_manager_firm)
    db.add(org)
    db.flush()
    seeded = User(
        organization_id=org.id,
        role=UserRole.fund_manager,
        first_name="Ava",
        last_name="Morgan",
        email="ava.morgan@edenscale.demo",
        hanko_subject_id=None,
    )
    db.add(seeded)
    db.commit()
    seeded_id = seeded.id

    payload = {
        "sub": "hanko-claim-1",
        "email": "ava.morgan@edenscale.demo",
    }
    user = get_current_user_record(payload=payload, db=db)

    assert user.id == seeded_id
    assert user.hanko_subject_id == "hanko-claim-1"
    assert user.role == UserRole.fund_manager
    assert (
        db.query(User).filter(User.email == "ava.morgan@edenscale.demo").count() == 1
    )


def test_seed_claim_refuses_when_email_already_linked(db):
    """If the email is already linked to a different `hanko_subject_id`, the
    second sign-in must NOT rebind the row (would be account takeover) and
    must NOT 500 on the unique-email constraint when auto-provisioning a
    duplicate. Returns 401 with a clear message instead.
    """
    org = Organization(name="Eden Capital", type=OrganizationType.fund_manager_firm)
    db.add(org)
    db.flush()
    existing = User(
        organization_id=org.id,
        role=UserRole.fund_manager,
        first_name="Ava",
        last_name="Morgan",
        email="ava.morgan@edenscale.demo",
        hanko_subject_id="hanko-original",
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id

    payload = {
        "sub": "hanko-impostor",
        "email": "ava.morgan@edenscale.demo",
    }
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_record(payload=payload, db=db)
    assert excinfo.value.status_code == 401

    rebound = db.query(User).filter(User.id == existing_id).one()
    assert rebound.hanko_subject_id == "hanko-original"
    assert (
        db.query(User).filter(User.email == "ava.morgan@edenscale.demo").count() == 1
    )


def test_missing_subject_raises_401(db):
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_record(payload={}, db=db)
    assert excinfo.value.status_code == 401


def test_require_roles_allows_matching_role():
    user = User(
        role=UserRole.admin,
        first_name="A",
        last_name="B",
        email="a@b.com",
        hanko_subject_id="x",
    )
    dep = require_roles(UserRole.admin, UserRole.fund_manager)

    assert dep(current_user=user) is user


def test_require_roles_rejects_other_role():
    user = User(
        role=UserRole.lp,
        first_name="A",
        last_name="B",
        email="a@b.com",
        hanko_subject_id="x",
    )
    dep = require_roles(UserRole.admin, UserRole.fund_manager)

    with pytest.raises(HTTPException) as excinfo:
        dep(current_user=user)
    assert excinfo.value.status_code == 403


def test_require_superadmin_allows_superadmin():
    user = User(
        role=UserRole.superadmin,
        first_name="Sam",
        last_name="Root",
        email="sam@example.com",
        hanko_subject_id="x",
    )

    assert require_superadmin(current_user=user) is user


@pytest.mark.parametrize(
    "role",
    [UserRole.admin, UserRole.fund_manager, UserRole.lp],
)
def test_require_superadmin_rejects_non_superadmin(role):
    user = User(
        role=role,
        first_name="A",
        last_name="B",
        email="a@b.com",
        hanko_subject_id="x",
    )

    with pytest.raises(HTTPException) as excinfo:
        require_superadmin(current_user=user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Superadmin role required"

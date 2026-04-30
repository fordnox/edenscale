"""Tests for the RBAC layer in `app.core.rbac`.

These exercise `get_current_user_record` (auto-provisioning) and the
`require_roles` factory directly with the SQLAlchemy session — no FastAPI
client needed.
"""

import pytest
from fastapi import HTTPException

from app.core.database import Base, SessionLocal, engine
from app.core.rbac import get_current_user_record, require_roles
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

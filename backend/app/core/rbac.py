"""Role-based access control helpers layered on top of the Hanko JWT check.

`get_current_user` (in `app.core.auth`) only validates the token and returns
the decoded payload. The platform also needs a local `User` row keyed by
`hanko_subject_id` so routes can authorise on `role`, scope queries by
`organization_id`, and so on. This module bridges the two:

* `get_current_user_record` — find-or-create the local `User` for the JWT
  subject; default new users to `UserRole.lp` and copy any name/email claims
  the IdP supplied.
* `require_roles` — dependency factory that 403s when the resolved user's
  role is not in the allow-list.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.middleware.audit_context import set_audit_user
from app.models.enums import UserRole
from app.models.user import User


def get_current_user_record(
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Return the local `User` row for the authenticated JWT subject.

    Resolution order:

    1. Existing row with matching `hanko_subject_id` — return it.
    2. Existing row with matching `email` and a NULL `hanko_subject_id` —
       bind the row by setting its subject to the JWT `sub` and return it.
       This is how seed / pre-provisioned users (admin, fund_manager) get
       claimed on first sign-in: the seed leaves `hanko_subject_id=None`,
       and Hanko's email claim is verified by Hanko before the JWT is
       issued, so binding by email here is safe.
    3. Otherwise auto-provision a fresh row, defaulting to `role=UserRole.lp`
       and pulling email / first / last name from the JWT claims.

    `first_name` / `last_name` / `email` columns are NOT NULL, so missing
    claims fall back to empty strings — the user can complete their profile
    later via `PATCH /users/me`.
    """
    subject_id = payload.get("sub")
    if not subject_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    user = db.query(User).filter(User.hanko_subject_id == subject_id).first()
    if user is not None:
        set_audit_user(user.id)  # type: ignore[invalid-argument-type]
        return user

    email_claim = payload.get("email")
    if isinstance(email_claim, dict):
        email_value = email_claim.get("address") or ""
    else:
        email_value = email_claim or ""

    if email_value:
        existing_by_email = db.query(User).filter(User.email == email_value).first()
        if existing_by_email is not None:
            if existing_by_email.hanko_subject_id is None:
                existing_by_email.hanko_subject_id = subject_id
                db.commit()
                db.refresh(existing_by_email)
                set_audit_user(existing_by_email.id)  # type: ignore[invalid-argument-type]
                return existing_by_email
            # Email already linked to a different Hanko subject. Refuse rather
            # than 500 on the unique-email constraint when we try to insert.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email already linked to a different account",
            )

    user = User(
        hanko_subject_id=subject_id,
        role=UserRole.lp,
        email=email_value,
        first_name=payload.get("given_name") or "",
        last_name=payload.get("family_name") or "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    set_audit_user(user.id)  # type: ignore[invalid-argument-type]
    return user


def require_roles(*allowed: UserRole) -> Callable[[User], User]:
    """Return a dependency that allows the request only for `allowed` roles."""

    def _dep(current_user: User = Depends(get_current_user_record)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return _dep

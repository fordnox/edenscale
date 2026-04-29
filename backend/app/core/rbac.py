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
from app.models.enums import UserRole
from app.models.user import User


def get_current_user_record(
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Return the local `User` row for the authenticated JWT subject.

    Auto-provisions a row on first sight, defaulting `role=UserRole.lp` and
    pulling email / first / last name from the JWT claims when present.
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
        return user

    user = User(
        hanko_subject_id=subject_id,
        role=UserRole.lp,
        email=payload.get("email") or "",
        first_name=payload.get("given_name") or "",
        last_name=payload.get("family_name") or "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
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

"""Promote a user to the global ``superadmin`` role by email.

Run from the repo root via ``cd backend && uv run python -m
scripts.promote_superadmin <email>``.

Superadmin assignment is intentionally out-of-band — there is no API endpoint
for self-promotion. This CLI flips a user's role to ``superadmin`` and clears
their ``organization_id`` (superadmins are global, not scoped to a single
org). Re-running on an already-promoted user is a no-op idempotently.
"""

from __future__ import annotations

import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository


def main(email: str) -> None:
    db: Session = SessionLocal()
    try:
        repo = UserRepository(db)
        user = repo.get_by_email(email)
        if user is None:
            raise SystemExit(f"User not found: {email}")
        user.role = UserRole.superadmin
        user.organization_id = None
        db.commit()
        db.refresh(user)
        print(
            f"Promoted {user.email} (id={user.id}) to superadmin; "
            "organization_id cleared."
        )
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.promote_superadmin <email>")
    main(sys.argv[1])

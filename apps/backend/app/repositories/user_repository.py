import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.user import UserCreate, UserUpdate


def _derive_name_from_email(email: str) -> str | None:
    """Best-effort ``Display Name`` from the local part of an email.

    ``john.doe@example.com`` → ``"John Doe"``;
    ``johndoe@example.com`` → ``"Johndoe"``. Returns ``None`` if the local
    part is empty so the caller can leave ``User.name`` null.
    """
    local = email.split("@", 1)[0].strip()
    if not local:
        return None
    parts = [p for p in re.split(r"[._\-+]+", local) if p]
    if not parts:
        return None
    return " ".join(p.capitalize() for p in parts)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[User]:
        """Every user on the platform, memberships (and their organizations)
        eager-loaded so serializing ``UserRead.memberships`` is not an N+1.
        Superadmin-only surface — tenant routes must never expose this."""
        return (
            self.db.query(User)
            .options(
                selectinload(User.memberships).joinedload(
                    UserOrganizationMembership.organization
                )
            )
            .order_by(User.created_at, User.id)
            .all()
        )

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_or_provision_by_hanko_id(
        self,
        *,
        hanko_id: str,
        email: str | None,
        first_name: str = "",
        last_name: str = "",
    ) -> tuple[User, bool]:
        """Resolve (or auto-provision on first login) the local user for a Hanko subject.

        Returns ``(user, is_new)`` so the caller can react to fresh signups
        (e.g. firing a welcome email). Resolution order:

        1. Existing row whose ``hanko_subject_id`` matches — return it
           unchanged.
        2. Existing row whose ``email`` matches and whose ``hanko_subject_id``
           is NULL — bind it to this subject and return it. This is how seed /
           pre-provisioned users (e.g. superadmin) get claimed on first
           sign-in; Hanko has already verified the email before issuing the
           JWT, so binding by email is safe. If the email is already linked to
           a *different* subject, raise ``ValueError``.
        3. Otherwise provision a fresh row. ``first_name`` falls back to a
           best-effort name derived from the email local part so new users
           have a reasonable default profile. Access comes later, via
           membership rows (or the config-defined superadmin list).

        Raises ``ValueError`` if a new user must be provisioned but no email
        was supplied in the token, or if the email is already linked to a
        different Hanko subject.
        """
        existing = (
            self.db.query(User).filter(User.hanko_subject_id == hanko_id).one_or_none()
        )
        if existing is not None:
            return existing, False

        if not email:
            raise ValueError("Cannot provision user without email")

        by_email = self.db.query(User).filter(User.email == email).first()
        if by_email is not None:
            if by_email.hanko_subject_id is not None:
                raise ValueError("Email already linked to a different account")
            by_email.hanko_subject_id = hanko_id
            self.db.commit()
            self.db.refresh(by_email)
            return by_email, False

        user = User(
            hanko_subject_id=hanko_id,
            email=email,
            first_name=first_name or _derive_name_from_email(email) or "",
            last_name=last_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user, True

    def get_by_hanko_subject(self, subject_id: str) -> User | None:
        return self.db.query(User).filter(User.hanko_subject_id == subject_id).first()

    def resolve_or_create_stub(
        self,
        *,
        user_id: uuid.UUID | None,
        email: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> User | None:
        """Return the user for `user_id`, or find/stage-create one for `email`.

        Returns None only when `user_id` is given but doesn't resolve. The
        `email` path always returns a user — the stub is added and flushed
        (not committed) so callers that need to land it alongside other rows
        (e.g. a fresh organization + its admin membership) can commit once.
        """
        if user_id is not None:
            return self.get_by_id(user_id)
        assert email is not None
        existing = self.get_by_email(email)
        if existing is not None:
            return existing
        stub = User(
            first_name=first_name or "",
            last_name=last_name or "",
            email=email,
            hanko_subject_id=None,
        )
        self.db.add(stub)
        self.db.flush()
        return stub

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: uuid.UUID, data: UserUpdate) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_active(self, user_id: uuid.UUID, is_active: bool) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_last_login(self, user_id: uuid.UUID) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)
        return user

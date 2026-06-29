from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_organization(
        self,
        organization_id: int,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[User]:
        query = self.db.query(User).filter(User.organization_id == organization_id)
        if not include_inactive:
            query = query.filter(User.is_active.is_(True))
        return query.order_by(User.id).offset(skip).limit(limit).all()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_hanko_subject(self, subject_id: str) -> User | None:
        return self.db.query(User).filter(User.hanko_subject_id == subject_id).first()

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: int, data: UserUpdate) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_role(self, user_id: int, role: UserRole) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.role = role
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_active(self, user_id: int, is_active: bool) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_last_login(self, user_id: int) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)
        return user

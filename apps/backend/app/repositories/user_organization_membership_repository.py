import uuid

from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership


class UserOrganizationMembershipRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[UserOrganizationMembership]:
        return (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.user_id == user_id)
            .order_by(
                UserOrganizationMembership.created_at, UserOrganizationMembership.id
            )
            .all()
        )

    def list_for_organization(
        self, organization_id: uuid.UUID
    ) -> list[UserOrganizationMembership]:
        return (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.organization_id == organization_id)
            .order_by(
                UserOrganizationMembership.created_at, UserOrganizationMembership.id
            )
            .all()
        )

    def list_org_members(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[tuple[UserOrganizationMembership, User]]:
        """The organization's members with their per-org membership row.

        Membership rows — not the legacy ``users.organization_id`` column —
        are the source of truth for who belongs to an org and with what role
        (invitation acceptance only creates a membership).
        """
        query = (
            self.db.query(UserOrganizationMembership, User)
            .join(User, UserOrganizationMembership.user_id == User.id)
            .filter(UserOrganizationMembership.organization_id == organization_id)
        )
        if not include_inactive:
            query = query.filter(User.is_active.is_(True))
        rows = query.order_by(User.created_at, User.id).offset(skip).limit(limit).all()
        return [(membership, user) for membership, user in rows]

    def get(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> UserOrganizationMembership | None:
        return (
            self.db.query(UserOrganizationMembership)
            .filter(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.organization_id == organization_id,
            )
            .first()
        )

    def create(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, role: UserRole
    ) -> UserOrganizationMembership:
        membership = UserOrganizationMembership(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def update_role(
        self, membership_id: uuid.UUID, role: UserRole
    ) -> UserOrganizationMembership | None:
        membership = (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.id == membership_id)
            .first()
        )
        if membership is None:
            return None
        membership.role = role
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def delete_all_for_organization(self, organization_id: uuid.UUID) -> int:
        deleted = (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.organization_id == organization_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return int(deleted)

    def delete(self, membership_id: uuid.UUID) -> UserOrganizationMembership | None:
        membership = (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.id == membership_id)
            .first()
        )
        if membership is None:
            return None
        self.db.delete(membership)
        self.db.commit()
        return membership

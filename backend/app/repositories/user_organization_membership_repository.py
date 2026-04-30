from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership


class UserOrganizationMembershipRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: int) -> list[UserOrganizationMembership]:
        return (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.user_id == user_id)
            .order_by(UserOrganizationMembership.id)
            .all()
        )

    def list_for_organization(
        self, organization_id: int
    ) -> list[UserOrganizationMembership]:
        return (
            self.db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.organization_id == organization_id)
            .order_by(UserOrganizationMembership.id)
            .all()
        )

    def get(
        self, user_id: int, organization_id: int
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
        self, user_id: int, organization_id: int, role: UserRole
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
        self, membership_id: int, role: UserRole
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

    def delete(self, membership_id: int) -> UserOrganizationMembership | None:
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

    def bulk_seed_from_legacy_user_org_id(self) -> int:
        """Idempotently create memberships for every user with a legacy
        ``users.organization_id`` that lacks a corresponding membership row.

        Returns the number of memberships inserted on this call.
        """
        legacy_users = (
            self.db.query(User)
            .filter(User.organization_id.is_not(None))
            .order_by(User.id)
            .all()
        )
        inserted = 0
        for user in legacy_users:
            existing = self.get(user.id, user.organization_id)
            if existing is not None:
                continue
            self.db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    role=user.role,
                )
            )
            inserted += 1
        if inserted:
            self.db.commit()
        return inserted

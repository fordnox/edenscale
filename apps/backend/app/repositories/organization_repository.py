import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_with_member_counts(self) -> list[tuple[Organization, int]]:
        return (
            self.db.query(
                Organization,
                func.count(UserOrganizationMembership.id).label("member_count"),
            )
            .outerjoin(
                UserOrganizationMembership,
                UserOrganizationMembership.organization_id == Organization.id,
            )
            .group_by(Organization.id)
            .order_by(Organization.id)
            .all()  # type: ignore[invalid-return-type]
        )

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[Organization]:
        query = self.db.query(Organization)
        if not include_inactive:
            query = query.filter(Organization.is_active.is_(True))
        return query.order_by(Organization.id).offset(skip).limit(limit).all()

    def get(self, organization_id: uuid.UUID) -> Organization | None:
        return (
            self.db.query(Organization)
            .filter(Organization.id == organization_id)
            .first()
        )

    def create(self, data: OrganizationCreate) -> Organization:
        organization = Organization(**data.model_dump())
        self.db.add(organization)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def update(
        self, organization_id: uuid.UUID, data: OrganizationUpdate
    ) -> Organization | None:
        organization = self.get(organization_id)
        if organization is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(organization, key, value)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def soft_delete(self, organization_id: uuid.UUID) -> Organization | None:
        return self.set_active(organization_id, is_active=False)

    def set_active(
        self, organization_id: uuid.UUID, *, is_active: bool
    ) -> Organization | None:
        organization = self.get(organization_id)
        if organization is None:
            return None
        organization.is_active = is_active
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def create_with_admin(
        self, data: OrganizationCreate, *, admin: User
    ) -> tuple[Organization, UserOrganizationMembership]:
        """Create an organization and its founding admin membership atomically.

        Builds both rows on the session and commits once, rather than going
        through `create()` (which commits the organization alone) followed by
        `UserOrganizationMembershipRepository.create()` — the two rows must
        land together so a superadmin org-creation call never leaves an org
        with no admin.
        """
        organization = Organization(**data.model_dump())
        self.db.add(organization)
        self.db.flush()
        membership = UserOrganizationMembership(
            user_id=admin.id,
            organization_id=organization.id,
            role=UserRole.admin,
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(organization)
        self.db.refresh(membership)
        return organization, membership

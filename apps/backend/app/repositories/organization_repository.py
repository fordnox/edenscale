from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

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

    def get(self, organization_id: int) -> Organization | None:
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
        self, organization_id: int, data: OrganizationUpdate
    ) -> Organization | None:
        organization = self.get(organization_id)
        if organization is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(organization, key, value)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def soft_delete(self, organization_id: int) -> Organization | None:
        organization = self.get(organization_id)
        if organization is None:
            return None
        organization.is_active = False
        self.db.commit()
        self.db.refresh(organization)
        return organization

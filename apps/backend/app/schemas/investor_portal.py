from pydantic import UUID4, BaseModel, ConfigDict

from app.schemas.organization import OrganizationRead


class InvestorOrganizationRead(BaseModel):
    """An organization the user has investor-portal access to.

    Access is derived from contact links (``InvestorContact.user_id``), not
    membership rows — there may be no membership at all.
    """

    organization_id: UUID4
    organization: OrganizationRead

    model_config = ConfigDict(from_attributes=True)

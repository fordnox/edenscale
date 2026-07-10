"""Investor-portal access resolution.

Portal access is derived from contact links (``InvestorContact.user_id``),
never from membership rows: a user may enter an organization's investor
portal if they are a linked contact of at least one investor there.
Membership means staff (admin / fund manager); the two are orthogonal, so a
fund admin who is personally an investor gets the portal via their links
while their staff role stays untouched.

The resolved access is expressed as a transient ``UserOrganizationMembership``
with ``role=lp`` so every repository's existing LP scoping applies unchanged.
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.investor_contact_repository import InvestorContactRepository


def get_investor_membership(
    x_organization_id: uuid.UUID | None = Header(
        default=None, alias="X-Organization-Id"
    ),
    current_user: User = Depends(get_current_user_record),
    db: Session = Depends(get_db),
) -> UserOrganizationMembership:
    """Resolve the org the caller is viewing as an investor.

    Returns a transient (never persisted) ``lp``-role membership for that
    org. 403 when the user has no contact links there; if the header is
    missing, falls back to the single linked org, mirroring
    ``get_active_membership``'s single-membership fallback.
    """
    repo = InvestorContactRepository(db)

    if x_organization_id is not None:
        if not repo.user_has_links_in_organization(
            current_user.id,  # type: ignore[invalid-argument-type]
            x_organization_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No investor access to this organization",
            )
        organization_id = x_organization_id
    else:
        organizations = repo.investor_organizations_for_user(
            current_user.id,  # type: ignore[invalid-argument-type]
        )
        if len(organizations) == 1:
            organization_id = organizations[0].id
        elif not organizations:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No investor access",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Organization-Id required",
            )

    return UserOrganizationMembership(
        user_id=current_user.id,
        organization_id=organization_id,
        role=UserRole.lp,
    )

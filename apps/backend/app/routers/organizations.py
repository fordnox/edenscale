import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import (
    get_active_membership,
    get_current_user_record,
    require_membership_roles,
    require_tenant_user,
)
from app.models.enums import OrganizationType, UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationOnboardingCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.schemas.user_organization_membership import MembershipRead

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_tenant_user)]
)


@router.post(
    "/self-serve",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_self_serve(
    data: OrganizationOnboardingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    """Onboarding entry point for a signed-in user with no organization.

    Creates a new `fund_manager_firm` organization and makes the caller its
    `admin`, so they can immediately create and manage their own fund without
    waiting on an invitation.
    """
    repo = OrganizationRepository(db)
    _organization, membership = repo.create_with_admin(
        OrganizationCreate(
            type=OrganizationType.fund_manager_firm,
            name=data.name,
            legal_name=data.legal_name,
            website=data.website,
            description=data.description,
        ),
        admin=current_user,
    )
    return membership


# NB: /demo routes must be registered before /{organization_id} — the path
# parameter is typed uuid.UUID, so "demo" would otherwise 422 instead of
# reaching these handlers.
@router.get("/demo", response_model=OrganizationRead | None)
async def get_demo_organization(
    db: Session = Depends(get_db),
):
    """Return the shared demo organization, or null when none is seeded.

    Returns 200 with a null body rather than 404 so the onboarding page can
    probe for the demo org without tripping the client's global error
    handling.
    """
    return OrganizationRepository(db).get_demo()


@router.post(
    "/demo/join",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def join_demo_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    """Onboarding alternative to /self-serve: join the seeded demo org.

    Adds the caller as a `fund_manager` of the demo organization so they can
    explore the product with realistic pre-seeded data instead of starting
    from an empty firm. Idempotent: re-joining returns the existing
    membership unchanged (including its original role).
    """
    demo = OrganizationRepository(db).get_demo()
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No demo organization is available",
        )
    membership_repo = UserOrganizationMembershipRepository(db)
    existing = membership_repo.get(current_user.id, demo.id)  # type: ignore[invalid-argument-type]
    if existing is not None:
        return existing
    return membership_repo.create(
        user_id=current_user.id,  # type: ignore[invalid-argument-type]
        organization_id=demo.id,  # type: ignore[invalid-argument-type]
        role=UserRole.fund_manager,
    )


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    if membership.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view an organization outside your membership",
        )
    repo = OrganizationRepository(db)
    organization = repo.get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization


@router.patch(
    "/{organization_id}",
    response_model=OrganizationRead,
)
async def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin)
    ),
):
    if membership.organization_id != organization_id:
        # The active membership (resolved from X-Organization-Id) does not
        # match the path. Refuse rather than silently editing a different org.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit an organization you are not an admin of",
        )
    repo = OrganizationRepository(db)
    organization = repo.update(organization_id, data)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import get_active_membership
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log import AuditLogRead

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    """List audit events visible to the caller's active membership.

    Admins/fund managers/superadmins see every event in the org; everyone
    else only sees events they caused themselves.
    """
    repo = AuditLogRepository(db)
    return repo.list_for_membership(
        membership,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )

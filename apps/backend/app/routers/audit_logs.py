import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import require_roles
from app.models.enums import UserRole
from app.models.user import User
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
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    repo = AuditLogRepository(db)
    return repo.list(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )

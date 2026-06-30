import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import get_current_user_record
from app.models.user import User
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import DashboardOverviewResponse

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
    x_organization_id: uuid.UUID | None = Header(
        default=None, alias="X-Organization-Id"
    ),
) -> DashboardOverviewResponse:
    return DashboardRepository(db).get_overview(current_user, x_organization_id)

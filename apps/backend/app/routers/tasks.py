import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.enums import TaskStatus, UserRole
from app.models.fund import Fund
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.fund_repository import FundRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.notifications import notify_task_assigned

router = APIRouter(dependencies=[Depends(get_current_user)])

_ORG_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


def _load_fund(db: Session, fund_id: uuid.UUID) -> Fund | None:
    row = FundRepository(db).get(fund_id)
    return row[0] if row is not None else None


def _ensure_can_attach_fund(
    membership: UserOrganizationMembership, db: Session, fund_id: uuid.UUID
) -> Fund:
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot attach task to a fund outside your organization",
        )
    return fund


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    fund_id: uuid.UUID | None = None,
    status_filter: TaskStatus | None = None,
    assignee: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = TaskRepository(db)
    effective_assignee = assignee
    if membership.role not in _ORG_ROLES:
        # LPs only ever see their own tasks regardless of `assignee`.
        effective_assignee = membership.user_id
    elif effective_assignee is None and fund_id is None and status_filter is None:
        effective_assignee = membership.user_id
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        status=status_filter,
        assignee=effective_assignee,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.membership_can_view(membership, task):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view this task"
        )
    return task


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    if data.fund_id is not None:
        _ensure_can_attach_fund(membership, db, data.fund_id)
    repo = TaskRepository(db)
    task = repo.create(data, created_by_user_id=membership.user_id)  # type: ignore[invalid-argument-type]
    if (
        task.assigned_to_user_id is not None
        and task.assigned_to_user_id != membership.user_id
    ):
        await notify_task_assigned(
            db, task=task, assignee_user_id=task.assigned_to_user_id
        )
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.membership_can_manage(membership, task):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit this task"
        )
    if data.fund_id is not None and data.fund_id != task.fund_id:
        _ensure_can_attach_fund(membership, db, data.fund_id)
    previous_assignee = task.assigned_to_user_id
    updated = repo.update(task_id, data)
    assert updated is not None
    if (
        updated.assigned_to_user_id is not None
        and updated.assigned_to_user_id != previous_assignee
        and updated.assigned_to_user_id != membership.user_id
    ):
        await notify_task_assigned(
            db, task=updated, assignee_user_id=updated.assigned_to_user_id
        )
    return updated


@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.membership_can_complete(membership, task):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot complete this task"
        )
    try:
        completed = repo.complete(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert completed is not None
    return completed


fund_tasks_router = APIRouter(dependencies=[Depends(get_current_user)])


@fund_tasks_router.get("/{fund_id}/tasks", response_model=list[TaskRead])
async def list_tasks_for_fund(
    fund_id: uuid.UUID,
    status_filter: TaskStatus | None = None,
    assignee: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    repo = TaskRepository(db)
    effective_assignee = assignee
    if membership.role not in _ORG_ROLES:
        effective_assignee = membership.user_id
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        status=status_filter,
        assignee=effective_assignee,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
    )

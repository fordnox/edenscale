from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record, require_roles
from app.models.enums import TaskStatus, UserRole
from app.models.fund import Fund
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = APIRouter()


def _load_fund(db: Session, fund_id: int) -> Fund | None:
    return db.query(Fund).filter(Fund.id == fund_id).first()


def _ensure_can_attach_fund(current_user: User, db: Session, fund_id: int) -> Fund:
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    if (
        current_user.role is UserRole.fund_manager
        and fund.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot attach task to a fund outside your organization",
        )
    return fund


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    fund_id: int | None = None,
    status_filter: TaskStatus | None = None,
    assignee: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = TaskRepository(db)
    effective_assignee = assignee
    if current_user.role not in (UserRole.admin, UserRole.fund_manager):
        # LPs only ever see their own tasks regardless of `assignee`.
        effective_assignee = current_user.id
    elif effective_assignee is None and fund_id is None and status_filter is None:
        effective_assignee = current_user.id
    return repo.list_for_user(
        current_user,
        fund_id=fund_id,
        status=status_filter,
        assignee=effective_assignee,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.user_can_view(current_user, task):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view this task"
        )
    return task


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    if data.fund_id is not None:
        _ensure_can_attach_fund(current_user, db, data.fund_id)
    repo = TaskRepository(db)
    task = repo.create(data, created_by_user_id=current_user.id)  # type: ignore[invalid-argument-type]
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.user_can_manage(current_user, task):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit this task"
        )
    if data.fund_id is not None and data.fund_id != task.fund_id:
        _ensure_can_attach_fund(current_user, db, data.fund_id)
    updated = repo.update(task_id, data)
    assert updated is not None
    return updated


@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = TaskRepository(db)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if not repo.user_can_complete(current_user, task):
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


fund_tasks_router = APIRouter()


@fund_tasks_router.get("/{fund_id}/tasks", response_model=list[TaskRead])
async def list_tasks_for_fund(
    fund_id: int,
    status_filter: TaskStatus | None = None,
    assignee: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    repo = TaskRepository(db)
    effective_assignee = assignee
    if current_user.role not in (UserRole.admin, UserRole.fund_manager):
        effective_assignee = current_user.id
    return repo.list_for_user(
        current_user,
        fund_id=fund_id,
        status=status_filter,
        assignee=effective_assignee,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
    )

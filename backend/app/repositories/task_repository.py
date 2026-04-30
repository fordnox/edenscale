from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session

from app.models.enums import TaskStatus, UserRole
from app.models.fund import Fund
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Task)

    def list_for_user(
        self,
        user: User,
        *,
        fund_id: int | None = None,
        status: TaskStatus | None = None,
        assignee: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        query = self._base_query()
        if user.role is UserRole.admin:
            if assignee is not None:
                query = query.filter(Task.assigned_to_user_id == assignee)
        elif user.role is UserRole.fund_manager:
            org_id = user.organization_id
            if org_id is None:
                org_visible = query.filter(
                    or_(
                        Task.assigned_to_user_id == user.id,
                        Task.created_by_user_id == user.id,
                    )
                )
                query = org_visible
            else:
                org_fund_ids = select(Fund.id).where(Fund.organization_id == org_id)
                query = query.filter(
                    or_(
                        Task.fund_id.in_(org_fund_ids),
                        Task.assigned_to_user_id == user.id,
                        Task.created_by_user_id == user.id,
                    )
                )
            if assignee is not None:
                query = query.filter(Task.assigned_to_user_id == assignee)
        else:
            # LP / non-privileged: only their own assignments are visible.
            query = query.filter(Task.assigned_to_user_id == user.id)
        if fund_id is not None:
            query = query.filter(Task.fund_id == fund_id)
        if status is not None:
            query = query.filter(Task.status == status)
        return query.order_by(Task.id.desc()).offset(skip).limit(limit).all()

    def get(self, task_id: int) -> Task | None:
        return self._base_query().filter(Task.id == task_id).first()

    def user_can_view(self, user: User, task: Task) -> bool:
        if user.role is UserRole.admin:
            return True
        if task.assigned_to_user_id == user.id or task.created_by_user_id == user.id:
            return True
        if user.role is UserRole.fund_manager:
            if task.fund_id is None:
                return False
            fund = self.db.query(Fund).filter(Fund.id == task.fund_id).first()
            return bool(
                fund is not None and fund.organization_id == user.organization_id
            )
        return False

    def user_can_manage(self, user: User, task: Task) -> bool:
        if user.role is UserRole.admin:
            return True
        if user.role is not UserRole.fund_manager:
            # LPs may complete a task assigned to them but not edit metadata.
            return False
        if task.created_by_user_id == user.id:
            return True
        if task.fund_id is None:
            return False
        fund = self.db.query(Fund).filter(Fund.id == task.fund_id).first()
        return bool(fund is not None and fund.organization_id == user.organization_id)

    def user_can_complete(self, user: User, task: Task) -> bool:
        if self.user_can_manage(user, task):
            return True
        return bool(task.assigned_to_user_id == user.id)

    def create(
        self, data: TaskCreate, *, created_by_user_id: int | None = None
    ) -> Task:
        task = Task(
            fund_id=data.fund_id,
            assigned_to_user_id=data.assigned_to_user_id,
            created_by_user_id=created_by_user_id,
            title=data.title,
            description=data.description,
            status=data.status,
            due_date=data.due_date,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update(self, task_id: int, data: TaskUpdate) -> Task | None:
        task = self.get(task_id)
        if task is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(task, key, value)
        if data.status is TaskStatus.done and task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
        elif (
            data.status is not None
            and data.status is not TaskStatus.done
            and task.completed_at is not None
        ):
            task.completed_at = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def complete(self, task_id: int) -> Task | None:
        task = self.get(task_id)
        if task is None:
            return None
        if task.status is TaskStatus.done:
            return task
        if task.status is TaskStatus.cancelled:
            raise ValueError("Cannot complete a cancelled task")
        task.status = TaskStatus.done
        task.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(task)
        return task

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session

from app.models.enums import TaskStatus, UserRole
from app.models.fund import Fund
from app.models.task import Task
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.task import TaskCreate, TaskUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Task)

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        fund_id: int | None = None,
        status: TaskStatus | None = None,
        assignee: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        query = self._base_query()
        if membership.role in _ORG_VISIBLE_ROLES:
            org_fund_ids = select(Fund.id).where(
                Fund.organization_id == membership.organization_id
            )
            query = query.filter(
                or_(
                    Task.fund_id.in_(org_fund_ids),
                    Task.assigned_to_user_id == membership.user_id,
                    Task.created_by_user_id == membership.user_id,
                )
            )
            if assignee is not None:
                query = query.filter(Task.assigned_to_user_id == assignee)
        else:
            # LP / non-privileged: only their own assignments are visible.
            query = query.filter(Task.assigned_to_user_id == membership.user_id)
        if fund_id is not None:
            query = query.filter(Task.fund_id == fund_id)
        if status is not None:
            query = query.filter(Task.status == status)
        return query.order_by(Task.id.desc()).offset(skip).limit(limit).all()

    def get(self, task_id: int) -> Task | None:
        return self._base_query().filter(Task.id == task_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, task: Task
    ) -> bool:
        if (
            task.assigned_to_user_id == membership.user_id
            or task.created_by_user_id == membership.user_id
        ):
            return True
        if membership.role in _ORG_VISIBLE_ROLES:
            if task.fund_id is None:
                return False
            fund = self.db.query(Fund).filter(Fund.id == task.fund_id).first()
            return bool(
                fund is not None and fund.organization_id == membership.organization_id
            )
        return False

    def membership_can_manage(
        self, membership: UserOrganizationMembership, task: Task
    ) -> bool:
        if membership.role not in _ORG_VISIBLE_ROLES:
            # LPs may complete a task assigned to them but not edit metadata.
            return False
        if task.created_by_user_id == membership.user_id:
            return True
        if task.fund_id is None:
            return False
        fund = self.db.query(Fund).filter(Fund.id == task.fund_id).first()
        return bool(
            fund is not None and fund.organization_id == membership.organization_id
        )

    def membership_can_complete(
        self, membership: UserOrganizationMembership, task: Task
    ) -> bool:
        if self.membership_can_manage(membership, task):
            return True
        return bool(task.assigned_to_user_id == membership.user_id)

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

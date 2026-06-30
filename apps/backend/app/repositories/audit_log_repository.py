import uuid
from datetime import datetime

from sqlalchemy.orm import Query, Session

from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.user_organization_membership import UserOrganizationMembership

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(AuditLog)

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Audit entries visible to the active membership.

        Admins/fund managers/superadmins see every event in the org; everyone
        else only sees events they themselves caused — the `user_id` filter is
        forced to their own id rather than honoring an arbitrary request, so a
        non-privileged caller can't page through other users' activity.
        """
        query = self._base_query().filter(
            AuditLog.organization_id == membership.organization_id
        )
        effective_user_id = (
            user_id if membership.role in _ORG_VISIBLE_ROLES else membership.user_id
        )
        if entity_type is not None:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.filter(AuditLog.entity_id == entity_id)
        if effective_user_id is not None:
            query = query.filter(AuditLog.user_id == effective_user_id)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        if date_from is not None:
            query = query.filter(AuditLog.created_at >= date_from)
        if date_to is not None:
            query = query.filter(AuditLog.created_at <= date_to)
        return (
            query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

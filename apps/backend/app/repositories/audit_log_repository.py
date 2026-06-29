from datetime import datetime

from sqlalchemy.orm import Query, Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(AuditLog)

    def list(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        user_id: int | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        query = self._base_query()
        if entity_type is not None:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.filter(AuditLog.entity_id == entity_id)
        if user_id is not None:
            query = query.filter(AuditLog.user_id == user_id)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        if date_from is not None:
            query = query.filter(AuditLog.created_at >= date_from)
        if date_to is not None:
            query = query.filter(AuditLog.created_at <= date_to)
        return query.order_by(AuditLog.id.desc()).offset(skip).limit(limit).all()

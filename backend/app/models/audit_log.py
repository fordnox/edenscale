from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String, Text,
                        func)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    action = Column(String(150), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)
    audit_metadata = Column("metadata", Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")
    organization = relationship("Organization", back_populates="audit_logs")

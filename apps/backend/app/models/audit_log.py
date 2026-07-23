import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    action = Column(String(150), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Uuid(as_uuid=True), nullable=True)
    audit_metadata = Column("metadata", Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    # ISO 3166-1 alpha-2 from Cloudflare's CF-IPCountry ("XX" unknown, "T1"/"T2"
    # Tor). Null for traffic that did not transit the edge — local dev, tests,
    # and background jobs.
    country = Column(String(2), nullable=True)
    user_agent = Column(String(400), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")
    organization = relationship("Organization", back_populates="audit_logs")

import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import FundStatus


class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "slug", name="uq_funds_organization_id_slug"
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    fund_group_id = Column(
        Uuid(as_uuid=True), ForeignKey("fund_groups.id"), nullable=True, index=True
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255), nullable=True)
    vintage_year = Column(Integer, nullable=True)
    strategy = Column(String(255), nullable=True)
    currency_code = Column(String(3), nullable=False, default="USD")
    # Capital the fund aims to raise, in currency_code units.
    target_size = Column(Numeric(18, 2), nullable=True)
    # Maximum commitments the fund will accept; fundraising stops at this ceiling.
    hard_cap = Column(Numeric(18, 2), nullable=True)
    status = Column(
        Enum(FundStatus, name="fund_status"),
        nullable=False,
        default=FundStatus.draft,
    )
    inception_date = Column(Date, nullable=True)
    close_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="funds")
    fund_group = relationship("FundGroup", back_populates="funds")
    commitments = relationship("Commitment", back_populates="fund")
    capital_calls = relationship("CapitalCall", back_populates="fund")
    distributions = relationship("Distribution", back_populates="fund")
    documents = relationship("Document", back_populates="fund")
    communications = relationship("Communication", back_populates="fund")
    tasks = relationship("Task", back_populates="fund")

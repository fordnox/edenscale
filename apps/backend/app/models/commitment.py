import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import CommitmentStatus


class Commitment(Base):
    __tablename__ = "commitments"
    __table_args__ = (
        UniqueConstraint("fund_id", "investor_id", name="uq_commitment_fund_investor"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id = Column(
        Uuid(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True
    )
    investor_id = Column(
        Uuid(as_uuid=True), ForeignKey("investors.id"), nullable=False, index=True
    )
    committed_amount = Column(Numeric(18, 2), nullable=False)
    called_amount = Column(Numeric(18, 2), nullable=False, default=0)
    distributed_amount = Column(Numeric(18, 2), nullable=False, default=0)
    commitment_date = Column(Date, nullable=False)
    status = Column(
        Enum(CommitmentStatus, name="commitment_status"),
        nullable=False,
        default=CommitmentStatus.pending,
    )
    share_class = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="commitments")
    investor = relationship("Investor", back_populates="commitments")
    capital_call_items = relationship("CapitalCallItem", back_populates="commitment")
    distribution_items = relationship("DistributionItem", back_populates="commitment")

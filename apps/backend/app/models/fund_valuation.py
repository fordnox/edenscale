import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FundValuation(Base):
    """A fund-level net asset value (fair value) mark as of a given date.

    Enables residual-value metrics (NAV, TVPI, RVPI) and the LP capital account
    at fair value. One mark per (fund, as_of_date); the latest by date is the
    current NAV.
    """

    __tablename__ = "fund_valuations"
    __table_args__ = (
        UniqueConstraint("fund_id", "as_of_date", name="uq_fund_valuation_as_of"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id = Column(
        Uuid(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True
    )
    as_of_date = Column(Date, nullable=False)
    # Net asset value / fair value of the whole fund as of ``as_of_date``.
    nav = Column(Numeric(18, 2), nullable=False)
    note = Column(Text, nullable=True)
    created_by_user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", foreign_keys=[fund_id])

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
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import DistributionStatus


class Distribution(Base):
    __tablename__ = "distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    distribution_date = Column(Date, nullable=False)
    record_date = Column(Date, nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    status = Column(
        Enum(DistributionStatus, name="distribution_status"),
        nullable=False,
        default=DistributionStatus.draft,
    )
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="distributions")
    created_by_user = relationship("User", back_populates="created_distributions")
    items = relationship("DistributionItem", back_populates="distribution")

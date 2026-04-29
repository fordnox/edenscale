from sqlalchemy import (Column, Date, DateTime, Enum, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import FundStatus


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    fund_group_id = Column(
        Integer, ForeignKey("fund_groups.id"), nullable=True, index=True
    )
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    vintage_year = Column(Integer, nullable=True)
    strategy = Column(String(255), nullable=True)
    currency_code = Column(String(3), nullable=False, default="USD")
    target_size = Column(Numeric(18, 2), nullable=True)
    hard_cap = Column(Numeric(18, 2), nullable=True)
    current_size = Column(Numeric(18, 2), nullable=True, default=0)
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
    team_members = relationship("FundTeamMember", back_populates="fund")
    commitments = relationship("Commitment", back_populates="fund")
    capital_calls = relationship("CapitalCall", back_populates="fund")
    distributions = relationship("Distribution", back_populates="fund")
    documents = relationship("Document", back_populates="fund")
    communications = relationship("Communication", back_populates="fund")
    tasks = relationship("Task", back_populates="fund")

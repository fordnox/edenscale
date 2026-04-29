from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FundTeamMember(Base):
    __tablename__ = "fund_team_members"
    __table_args__ = (
        UniqueConstraint("fund_id", "user_id", name="uq_fund_team_member_fund_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(150), nullable=True)
    permissions = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="team_members")
    user = relationship("User", back_populates="fund_team_memberships")

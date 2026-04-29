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
from app.models.enums import CapitalCallStatus


class CapitalCall(Base):
    __tablename__ = "capital_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    call_date = Column(Date, nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    status = Column(
        Enum(CapitalCallStatus, name="capital_call_status"),
        nullable=False,
        default=CapitalCallStatus.draft,
    )
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="capital_calls")
    created_by_user = relationship("User", back_populates="created_capital_calls")
    items = relationship("CapitalCallItem", back_populates="capital_call")

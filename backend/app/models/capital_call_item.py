from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CapitalCallItem(Base):
    __tablename__ = "capital_call_items"
    __table_args__ = (
        UniqueConstraint(
            "capital_call_id",
            "commitment_id",
            name="uq_capital_call_item_call_commitment",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    capital_call_id = Column(
        Integer, ForeignKey("capital_calls.id"), nullable=False, index=True
    )
    commitment_id = Column(
        Integer, ForeignKey("commitments.id"), nullable=False, index=True
    )
    amount_due = Column(Numeric(18, 2), nullable=False)
    amount_paid = Column(Numeric(18, 2), nullable=False, default=0)
    paid_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    capital_call = relationship("CapitalCall", back_populates="items")
    commitment = relationship("Commitment", back_populates="capital_call_items")

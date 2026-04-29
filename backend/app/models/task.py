from sqlalchemy import (Column, Date, DateTime, Enum, ForeignKey, Integer,
                        String, Text, func)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=True, index=True)
    assigned_to_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.open,
    )
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="tasks")
    assigned_to_user = relationship(
        "User", back_populates="assigned_tasks", foreign_keys=[assigned_to_user_id]
    )
    created_by_user = relationship(
        "User", back_populates="created_tasks", foreign_keys=[created_by_user_id]
    )

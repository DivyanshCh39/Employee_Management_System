from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.enums import LeaveStatus, LeaveType
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.modules.employee.model import Employee


class LeaveTypeConfig(Base, TimestampMixin):
    __tablename__ = "leave_type_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    leave_type: Mapped[LeaveType] = mapped_column(
        SAEnum(LeaveType, values_callable=lambda x: [e.value for e in x]),
        unique=True, nullable=False, index=True,
    )
    max_days_per_year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_carry_forward_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_document: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    balances: Mapped[list["LeaveBalance"]] = relationship("LeaveBalance", back_populates="leave_type_config")

    def __repr__(self) -> str:
        return f"<LeaveTypeConfig {self.leave_type} max={self.max_days_per_year}>"


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_config_id: Mapped[int] = mapped_column(ForeignKey("leave_type_configs.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_days: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    used_days: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_config_id", "year", name="uq_leave_balance_emp_type_year"),
        Index("ix_leave_balance_emp_year", "employee_id", "year"),
    )

    employee: Mapped["Employee"] = relationship("Employee")
    leave_type_config: Mapped["LeaveTypeConfig"] = relationship("LeaveTypeConfig", back_populates="balances")

    @property
    def remaining_days(self) -> float:
        return float(self.allocated_days) - float(self.used_days)

    def __repr__(self) -> str:
        return f"<LeaveBalance emp={self.employee_id} year={self.year} used={self.used_days}/{self.allocated_days}>"


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type: Mapped[LeaveType] = mapped_column(
        SAEnum(LeaveType, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_days: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=LeaveStatus.PENDING, index=True,
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_leave_req_emp_status", "employee_id", "status"),
        Index("ix_leave_req_status_dates", "status", "start_date", "end_date"),
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="leave_requests", foreign_keys=[employee_id])
    reviewer: Mapped["Employee | None"] = relationship("Employee", back_populates="reviewed_leaves", foreign_keys=[reviewed_by_id])

    def __repr__(self) -> str:
        return f"<LeaveRequest id={self.id} emp={self.employee_id} type={self.leave_type} status={self.status}>"
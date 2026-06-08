from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import Role
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.modules.audit.model import AuditLog
    from app.modules.department.model import Department
    from app.modules.leave.model import LeaveRequest


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    emp_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=Role.EMPLOYEE, index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True,
    )

    department: Mapped["Department | None"] = relationship("Department", back_populates="employees")
    manager: Mapped["Employee | None"] = relationship(
        "Employee", remote_side="Employee.id", back_populates="direct_reports", foreign_keys=[manager_id],
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="manager", foreign_keys=[manager_id],
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest", back_populates="employee", foreign_keys="LeaveRequest.employee_id",
    )
    reviewed_leaves: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest", back_populates="reviewer", foreign_keys="LeaveRequest.reviewed_by_id",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="actor")

    __table_args__ = (
        Index("ix_employees_dept_role", "department_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} email={self.email!r} role={self.role}>"
"""Create core tables: departments, employees, leave_type_configs,
leave_balances, leave_requests, audit_logs

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_role_enum = sa.Enum("ADMIN", "HR", "MANAGER", "EMPLOYEE", name="role")
_leave_type_enum = sa.Enum("SICK", "CASUAL", "EARNED", "UNPAID", name="leavetype")
_leave_status_enum = sa.Enum("PENDING", "APPROVED", "REJECTED", "CANCELLED", name="leavestatus")


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now() ON UPDATE now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("emp_code", sa.String(20), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", _role_enum, nullable=False, server_default="EMPLOYEE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now() ON UPDATE now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
    )
    op.create_foreign_key("fk_employees_manager_id", "employees", "employees", ["manager_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_employees_emp_code", "employees", ["emp_code"], unique=True)
    op.create_index("ix_employees_email", "employees", ["email"], unique=True)
    op.create_index("ix_employees_role", "employees", ["role"], unique=False)
    op.create_index("ix_employees_dept_id", "employees", ["department_id"], unique=False)
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"], unique=False)
    op.create_index("ix_employees_dept_role", "employees", ["department_id", "role"], unique=False)

    op.create_table(
        "leave_type_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("leave_type", _leave_type_enum, nullable=False),
        sa.Column("max_days_per_year", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_carry_forward_allowed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requires_document", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now() ON UPDATE now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("leave_type", name="uq_leave_type_configs_leave_type"),
    )
    op.create_index("ix_leave_type_configs_leave_type", "leave_type_configs", ["leave_type"], unique=True)

    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_config_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("allocated_days", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("used_days", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_config_id"], ["leave_type_configs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("employee_id", "leave_type_config_id", "year", name="uq_leave_balance_emp_type_year"),
    )
    op.create_index("ix_leave_balance_emp_year", "leave_balances", ["employee_id", "year"])

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", _leave_type_enum, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_days", sa.Numeric(5, 1), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", _leave_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now() ON UPDATE now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["employees.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_leave_req_emp_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_req_leave_type", "leave_requests", ["leave_type"])
    op.create_index("ix_leave_req_status", "leave_requests", ["status"])
    op.create_index("ix_leave_req_reviewed_by", "leave_requests", ["reviewed_by_id"])
    op.create_index("ix_leave_req_emp_status", "leave_requests", ["employee_id", "status"])
    op.create_index("ix_leave_req_status_dates", "leave_requests", ["status", "start_date", "end_date"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["employees.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_actor_action", "audit_logs", ["actor_id", "action"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_entity", table_name="audit_logs")
    op.drop_index("ix_audit_actor_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_leave_req_status_dates", table_name="leave_requests")
    op.drop_index("ix_leave_req_emp_status", table_name="leave_requests")
    op.drop_index("ix_leave_req_reviewed_by", table_name="leave_requests")
    op.drop_index("ix_leave_req_status", table_name="leave_requests")
    op.drop_index("ix_leave_req_leave_type", table_name="leave_requests")
    op.drop_index("ix_leave_req_emp_id", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_leave_balance_emp_year", table_name="leave_balances")
    op.drop_table("leave_balances")
    op.drop_index("ix_leave_type_configs_leave_type", table_name="leave_type_configs")
    op.drop_table("leave_type_configs")
    op.drop_constraint("fk_employees_manager_id", "employees", type_="foreignkey")
    op.drop_index("ix_employees_dept_role", table_name="employees")
    op.drop_index("ix_employees_manager_id", table_name="employees")
    op.drop_index("ix_employees_dept_id", table_name="employees")
    op.drop_index("ix_employees_role", table_name="employees")
    op.drop_index("ix_employees_email", table_name="employees")
    op.drop_index("ix_employees_emp_code", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_table("departments")
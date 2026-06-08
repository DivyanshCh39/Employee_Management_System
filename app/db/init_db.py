from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Role


def seed_first_admin(db: Session) -> None:
    # Import all models first to ensure relationships are loaded
    from app.modules.department.model import Department
    from app.modules.employee.model import Employee
    from app.modules.leave.model import LeaveTypeConfig, LeaveBalance, LeaveRequest
    from app.modules.audit.model import AuditLog
    from app.core.security import hash_password

    existing = db.query(Employee).filter(Employee.role == Role.ADMIN).first()
    if existing:
        return

    admin = Employee(
        full_name=settings.FIRST_ADMIN_NAME,
        email=settings.FIRST_ADMIN_EMAIL,
        hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
        role=Role.ADMIN,
        is_active=True,
        emp_code="EMP001",
    )
    db.add(admin)
    db.commit()
    print(f"[init_db] Admin user created: {settings.FIRST_ADMIN_EMAIL}")
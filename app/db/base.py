from app.core.database import Base  # noqa: F401

# Import in correct order — no FKs first, then dependent models
from app.modules.department.model import Department          # noqa: F401
from app.modules.employee.model import Employee              # noqa: F401
from app.modules.leave.model import (                        # noqa: F401
    LeaveTypeConfig,
    LeaveBalance,
    LeaveRequest,
)
from app.modules.audit.model import AuditLog                 # noqa: F401
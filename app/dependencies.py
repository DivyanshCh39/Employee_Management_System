from collections.abc import Generator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import Role
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token

if TYPE_CHECKING:
    from app.modules.employee.model import Employee

bearer_scheme = HTTPBearer(auto_error=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> "Employee":
    from app.modules.employee.model import Employee

    payload = decode_access_token(credentials.credentials)
    email: str = payload.get("sub", "")

    if not email:
        raise UnauthorizedException("Token payload is missing the subject claim")

    employee: Employee | None = (
        db.query(Employee).filter(Employee.email == email).first()
    )

    if not employee:
        raise UnauthorizedException("User associated with this token no longer exists")

    if not employee.is_active:
        raise ForbiddenException("This account has been deactivated. Contact HR.")

    return employee


CurrentUser = Annotated["Employee", Depends(get_current_user)]


def require_roles(*roles: Role):
    def role_checker(
        current_user: "Employee" = Depends(get_current_user),
    ) -> "Employee":
        if current_user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise ForbiddenException(
                f"Access denied. Required role(s): [{allowed}]. "
                f"Your role: {current_user.role.value}."
            )
        return current_user

    role_checker.__name__ = f"require_roles_{'_'.join(r.value for r in roles)}"
    return role_checker


AdminOnly      = Depends(require_roles(Role.ADMIN))
AdminOrHR      = Depends(require_roles(Role.ADMIN, Role.HR))
AdminHRManager = Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER))
AnyRole        = Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))
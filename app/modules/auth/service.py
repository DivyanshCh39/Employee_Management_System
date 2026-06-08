from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AuditAction
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import (
    AccessTokenResponse,
    EmployeeSummary,
    MeResponse,
    MessageResponse,
    TokenResponse,
)


def _write_audit(
    db: Session,
    *,
    actor_id: int | None,
    action: AuditAction,
    entity_type: str,
    entity_id: int | None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    from app.modules.audit.model import AuditLog

    db.add(AuditLog(
        actor_id=actor_id,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        ip_address=ip_address,
    ))


def login(
    email: str,
    password: str,
    db: Session,
    ip_address: str | None = None,
) -> TokenResponse:
    from app.modules.employee.model import Employee

    employee: Employee | None = (
        db.query(Employee).filter(Employee.email == email).first()
    )

    # Valid pre-computed bcrypt hash — always fails verify() but keeps
    # timing consistent to prevent user enumeration via response time.
    dummy_hash = "$2b$12$KKNDdzImC7Y30KZZUKWsO.ukT3OE0AHCmhQ5aRJDji58jg6PQnhh."
    stored_hash = employee.hashed_password if employee else dummy_hash

    password_ok = verify_password(password, stored_hash)

    if not employee or not password_ok:
        raise UnauthorizedException("Invalid email or password")

    if not employee.is_active:
        raise UnauthorizedException("Account is deactivated. Please contact HR.")

    access_token = create_access_token(subject=employee.email, role=employee.role)
    refresh_token = create_refresh_token(subject=employee.email)

    _write_audit(
        db,
        actor_id=employee.id,
        action=AuditAction.USER_LOGIN,
        entity_type="Employee",
        entity_id=employee.id,
        detail={"email": employee.email},
        ip_address=ip_address,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        employee=EmployeeSummary.model_validate(employee),
    )


def refresh_access_token(refresh_token: str, db: Session) -> AccessTokenResponse:
    from app.modules.employee.model import Employee

    payload = decode_refresh_token(refresh_token)
    email: str = payload.get("sub", "")

    employee: Employee | None = (
        db.query(Employee).filter(Employee.email == email).first()
    )

    if not employee or not employee.is_active:
        raise UnauthorizedException("User not found or deactivated")

    new_access_token = create_access_token(
        subject=employee.email, role=employee.role
    )

    return AccessTokenResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def get_me(employee) -> MeResponse:
    return MeResponse.model_validate(employee)


def change_password(
    employee,
    current_password: str,
    new_password: str,
    db: Session,
    ip_address: str | None = None,
) -> MessageResponse:
    if not verify_password(current_password, employee.hashed_password):
        raise BadRequestException("Current password is incorrect")

    if verify_password(new_password, employee.hashed_password):
        raise BadRequestException("New password must be different from the current password")

    employee.hashed_password = hash_password(new_password)
    employee.updated_at = datetime.now(timezone.utc)

    _write_audit(
        db,
        actor_id=employee.id,
        action=AuditAction.EMPLOYEE_UPDATED,
        entity_type="Employee",
        entity_id=employee.id,
        detail={"action": "password_changed"},
        ip_address=ip_address,
    )

    db.add(employee)
    db.commit()

    return MessageResponse(message="Password changed successfully")
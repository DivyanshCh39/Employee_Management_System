"""
Leave service — all business logic for the leave workflow.
"""
import math
from datetime import datetime, timezone

from sqlalchemy import and_, extract, func, or_
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, LeaveStatus, LeaveType, Role
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.leave.schemas import (
    LeaveApplyRequest,
    LeaveBalanceListResponse,
    LeaveBalanceRead,
    LeaveListResponse,
    LeaveRead,
    MessageResponse,
)


def _write_audit(
    db: Session,
    *,
    actor_id: int | None,
    action: AuditAction,
    entity_id: int | None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    from app.modules.audit.model import AuditLog

    db.add(AuditLog(
        actor_id=actor_id,
        action=action.value,
        entity_type="LeaveRequest",
        entity_id=entity_id,
        detail=detail,
        ip_address=ip_address,
    ))


def _get_leave_or_404(db: Session, leave_id: int):
    from app.modules.leave.model import LeaveRequest

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise NotFoundException(f"Leave request with id={leave_id} not found")
    return leave


def _compute_total_days(start_date, end_date) -> float:
    return float((end_date - start_date).days + 1)


def _get_leave_type_config(db: Session, leave_type: LeaveType):
    from app.modules.leave.model import LeaveTypeConfig

    config = db.query(LeaveTypeConfig).filter(
        LeaveTypeConfig.leave_type == leave_type,
        LeaveTypeConfig.is_active == True,  # noqa: E712
    ).first()

    if not config:
        raise BadRequestException(
            f"Leave type '{leave_type.value}' is not configured or currently inactive. "
            "Contact HR."
        )
    return config


def _get_or_create_balance(
    db: Session,
    employee_id: int,
    leave_type_config_id: int,
    year: int,
    default_allocated: float,
):
    from app.modules.leave.model import LeaveBalance

    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type_config_id == leave_type_config_id,
        LeaveBalance.year == year,
    ).first()

    if balance is None:
        balance = LeaveBalance(
            employee_id=employee_id,
            leave_type_config_id=leave_type_config_id,
            year=year,
            allocated_days=default_allocated,
            used_days=0,
        )
        db.add(balance)
        db.flush()

    return balance


def _check_overlap(
    db: Session,
    employee_id: int,
    start_date,
    end_date,
    exclude_leave_id: int | None = None,
) -> None:
    from app.modules.leave.model import LeaveRequest

    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    )

    if exclude_leave_id is not None:
        query = query.filter(LeaveRequest.id != exclude_leave_id)

    overlapping = query.first()

    if overlapping:
        raise BadRequestException(
            f"You already have a {overlapping.status.value} leave request "
            f"({overlapping.leave_type.value}) from {overlapping.start_date} "
            f"to {overlapping.end_date} that overlaps with the requested dates "
            f"({start_date} to {end_date}). "
            "Cancel or wait for rejection of the existing request first."
        )


def _assert_reviewer_can_act(actor, leave) -> None:
    if actor.role == Role.MANAGER:
        if leave.employee_id == actor.id:
            raise ForbiddenException(
                "Managers cannot approve or reject their own leave requests. "
                "Contact HR or an Admin."
            )
        if leave.employee.manager_id != actor.id:
            raise ForbiddenException(
                "Managers can only approve or reject leave requests "
                "from their own direct reports."
            )


def apply_leave(
    payload: LeaveApplyRequest,
    actor,
    db: Session,
    ip_address: str | None = None,
) -> LeaveRead:
    from app.modules.leave.model import LeaveRequest

    config = _get_leave_type_config(db, payload.leave_type)
    total_days = _compute_total_days(payload.start_date, payload.end_date)
    year = payload.start_date.year

    _check_overlap(db, actor.id, payload.start_date, payload.end_date)

    if config.max_days_per_year > 0:
        balance = _get_or_create_balance(
            db,
            employee_id=actor.id,
            leave_type_config_id=config.id,
            year=year,
            default_allocated=float(config.max_days_per_year),
        )
        if float(balance.remaining_days) < total_days:
            raise BadRequestException(
                f"Insufficient {payload.leave_type.value} leave balance. "
                f"Requested: {total_days} day(s). "
                f"Remaining: {balance.remaining_days} day(s)."
            )

    leave = LeaveRequest(
        employee_id=actor.id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=total_days,
        reason=payload.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(leave)
    db.flush()

    _write_audit(
        db,
        actor_id=actor.id,
        action=AuditAction.LEAVE_APPLIED,
        entity_id=leave.id,
        detail={
            "leave_type": payload.leave_type.value,
            "start_date": str(payload.start_date),
            "end_date": str(payload.end_date),
            "total_days": total_days,
        },
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(leave)
    return LeaveRead.model_validate(leave)


def list_leaves(
    db: Session,
    actor,
    employee_id: int | None = None,
    status: LeaveStatus | None = None,
    leave_type: LeaveType | None = None,
    year: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> LeaveListResponse:
    from app.modules.leave.model import LeaveRequest
    from app.modules.employee.model import Employee

    query = db.query(LeaveRequest)

    if actor.role == Role.EMPLOYEE:
        query = query.filter(LeaveRequest.employee_id == actor.id)
    elif actor.role == Role.MANAGER:
        direct_report_ids = (
            db.query(Employee.id)
            .filter(Employee.manager_id == actor.id)
            .scalar_subquery()
        )
        query = query.filter(LeaveRequest.employee_id.in_(direct_report_ids))

    if employee_id is not None:
        if actor.role == Role.EMPLOYEE and employee_id != actor.id:
            raise ForbiddenException("You can only view your own leave requests")
        query = query.filter(LeaveRequest.employee_id == employee_id)

    if status is not None:
        query = query.filter(LeaveRequest.status == status)

    if leave_type is not None:
        query = query.filter(LeaveRequest.leave_type == leave_type)

    if year is not None:
        # extract() works on both MySQL (production) and SQLite (tests)
        query = query.filter(
            extract("year", LeaveRequest.start_date) == year
        )

    total = query.with_entities(func.count(LeaveRequest.id)).scalar() or 0

    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    offset = (page - 1) * page_size

    items = (
        query
        .order_by(LeaveRequest.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return LeaveListResponse(
        items=[LeaveRead.model_validate(lr) for lr in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


def get_leave_by_id(
    leave_id: int,
    actor,
    db: Session,
) -> LeaveRead:
    leave = _get_leave_or_404(db, leave_id)

    if actor.role == Role.EMPLOYEE and leave.employee_id != actor.id:
        raise ForbiddenException("You can only view your own leave requests")

    if actor.role == Role.MANAGER:
        is_own = (leave.employee_id == actor.id)
        is_direct_report = (leave.employee.manager_id == actor.id)
        if not is_own and not is_direct_report:
            raise ForbiddenException(
                "Managers can only view their own or their direct reports' leave requests"
            )

    return LeaveRead.model_validate(leave)


def approve_leave(
    leave_id: int,
    actor,
    db: Session,
    ip_address: str | None = None,
) -> LeaveRead:
    from app.modules.leave.model import LeaveBalance

    leave = _get_leave_or_404(db, leave_id)

    if leave.status != LeaveStatus.PENDING:
        raise BadRequestException(
            f"Cannot approve a leave that is already {leave.status.value}. "
            "Only PENDING requests can be approved."
        )

    _assert_reviewer_can_act(actor, leave)

    year = leave.start_date.year
    _check_overlap(
        db,
        employee_id=leave.employee_id,
        start_date=leave.start_date,
        end_date=leave.end_date,
        exclude_leave_id=leave.id,
    )

    config = _get_leave_type_config(db, leave.leave_type)

    if config.max_days_per_year > 0:
        balance = _get_or_create_balance(
            db,
            employee_id=leave.employee_id,
            leave_type_config_id=config.id,
            year=year,
            default_allocated=float(config.max_days_per_year),
        )
        if float(balance.remaining_days) < float(leave.total_days):
            raise BadRequestException(
                f"Cannot approve: insufficient {leave.leave_type.value} balance. "
                f"Requested: {leave.total_days} day(s). "
                f"Remaining: {balance.remaining_days} day(s)."
            )

    leave.status = LeaveStatus.APPROVED
    leave.reviewed_by_id = actor.id
    leave.reviewed_at = datetime.now(timezone.utc)
    leave.updated_at = datetime.now(timezone.utc)

    if config.max_days_per_year > 0:
        balance.used_days = float(balance.used_days) + float(leave.total_days)
        db.add(balance)

    _write_audit(
        db,
        actor_id=actor.id,
        action=AuditAction.LEAVE_APPROVED,
        entity_id=leave.id,
        detail={
            "employee_id": leave.employee_id,
            "leave_type": leave.leave_type.value,
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
            "total_days": float(leave.total_days),
        },
        ip_address=ip_address,
    )

    db.add(leave)
    db.commit()
    db.refresh(leave)
    return LeaveRead.model_validate(leave)


def reject_leave(
    leave_id: int,
    rejection_reason: str,
    actor,
    db: Session,
    ip_address: str | None = None,
) -> LeaveRead:
    leave = _get_leave_or_404(db, leave_id)

    if leave.status != LeaveStatus.PENDING:
        raise BadRequestException(
            f"Cannot reject a leave that is already {leave.status.value}. "
            "Only PENDING requests can be rejected."
        )

    if not rejection_reason or not rejection_reason.strip():
        raise BadRequestException(
            "A rejection_reason is required. "
            "Explain to the employee why the leave was rejected."
        )

    _assert_reviewer_can_act(actor, leave)

    leave.status = LeaveStatus.REJECTED
    leave.reviewed_by_id = actor.id
    leave.reviewed_at = datetime.now(timezone.utc)
    leave.rejection_reason = rejection_reason.strip()
    leave.updated_at = datetime.now(timezone.utc)

    _write_audit(
        db,
        actor_id=actor.id,
        action=AuditAction.LEAVE_REJECTED,
        entity_id=leave.id,
        detail={
            "employee_id": leave.employee_id,
            "leave_type": leave.leave_type.value,
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
            "rejection_reason": rejection_reason.strip(),
        },
        ip_address=ip_address,
    )

    db.add(leave)
    db.commit()
    db.refresh(leave)
    return LeaveRead.model_validate(leave)


def cancel_leave(
    leave_id: int,
    actor,
    db: Session,
    ip_address: str | None = None,
) -> MessageResponse:
    from app.modules.leave.model import LeaveBalance

    leave = _get_leave_or_404(db, leave_id)

    if leave.employee_id != actor.id:
        raise ForbiddenException("You can only cancel your own leave requests")

    if leave.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
        raise BadRequestException(
            f"Cannot cancel a leave with status '{leave.status.value}'. "
            "Only PENDING or APPROVED requests can be cancelled."
        )

    was_approved = leave.status == LeaveStatus.APPROVED

    leave.status = LeaveStatus.CANCELLED
    leave.updated_at = datetime.now(timezone.utc)

    if was_approved:
        config = _get_leave_type_config(db, leave.leave_type)

        if config.max_days_per_year > 0:
            year = leave.start_date.year
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == leave.employee_id,
                LeaveBalance.leave_type_config_id == config.id,
                LeaveBalance.year == year,
            ).first()

            if balance:
                refund = float(leave.total_days)
                balance.used_days = max(0.0, float(balance.used_days) - refund)
                db.add(balance)

    _write_audit(
        db,
        actor_id=actor.id,
        action=AuditAction.LEAVE_CANCELLED,
        entity_id=leave.id,
        detail={
            "leave_type": leave.leave_type.value,
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
            "was_approved": was_approved,
            "balance_refunded": was_approved,
        },
        ip_address=ip_address,
    )

    db.add(leave)
    db.commit()

    action_verb = "cancelled" + (" and balance refunded" if was_approved else "")
    return MessageResponse(
        message=f"Leave request id={leave_id} has been {action_verb} successfully"
    )


def get_leave_balances(
    employee_id: int,
    actor,
    db: Session,
    year: int | None = None,
) -> LeaveBalanceListResponse:
    from app.modules.employee.model import Employee
    from app.modules.leave.model import LeaveBalance, LeaveTypeConfig

    target_year = year or datetime.now(timezone.utc).year

    if actor.role == Role.EMPLOYEE and employee_id != actor.id:
        raise ForbiddenException("You can only view your own leave balances")

    if actor.role == Role.MANAGER:
        target_emp = db.query(Employee).filter(Employee.id == employee_id).first()
        if not target_emp:
            raise NotFoundException(f"Employee id={employee_id} not found")
        is_own = (employee_id == actor.id)
        is_direct_report = (target_emp.manager_id == actor.id)
        if not is_own and not is_direct_report:
            raise ForbiddenException(
                "Managers can only view their own or their direct reports' balances"
            )

    rows = (
        db.query(LeaveBalance, LeaveTypeConfig)
        .join(LeaveTypeConfig, LeaveBalance.leave_type_config_id == LeaveTypeConfig.id)
        .filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == target_year,
        )
        .all()
    )

    balances = []
    for balance, config in rows:
        balances.append(LeaveBalanceRead(
            id=balance.id,
            employee_id=balance.employee_id,
            leave_type_config_id=balance.leave_type_config_id,
            leave_type=config.leave_type,
            year=balance.year,
            allocated_days=float(balance.allocated_days),
            used_days=float(balance.used_days),
            remaining_days=balance.remaining_days,
        ))

    return LeaveBalanceListResponse(
        employee_id=employee_id,
        year=target_year,
        balances=balances,
    )
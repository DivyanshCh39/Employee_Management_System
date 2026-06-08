from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.enums import LeaveStatus, LeaveType, Role
from app.dependencies import AdminHRManager, AnyRole, DBSession, require_roles
from app.modules.leave import service
from app.modules.leave.schemas import (
    LeaveApplyRequest, LeaveBalanceListResponse, LeaveListResponse,
    LeaveRead, LeaveReviewRequest, MessageResponse,
)

router = APIRouter(prefix="/leaves", tags=["Leave Management"])


@router.post("/", response_model=LeaveRead, status_code=201, summary="Apply for leave")
def apply_leave(payload: LeaveApplyRequest, request: Request,
                actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))],
                db: DBSession):
    ip = request.client.host if request.client else None
    return service.apply_leave(payload=payload, actor=actor, db=db, ip_address=ip)


@router.get("/", response_model=LeaveListResponse, summary="List leave requests with optional filters")
def list_leaves(actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))],
                db: DBSession,
                employee_id: int | None = Query(default=None, gt=0),
                status: LeaveStatus | None = Query(default=None),
                leave_type: LeaveType | None = Query(default=None),
                year: int | None = Query(default=None, ge=2000, le=2100),
                page: int = Query(default=1, ge=1),
                page_size: int = Query(default=20, ge=1, le=100)):
    return service.list_leaves(db=db, actor=actor, employee_id=employee_id,
                               status=status, leave_type=leave_type,
                               year=year, page=page, page_size=page_size)


# CRITICAL: /balances/{employee_id} MUST come before /{leave_id}
# to prevent FastAPI matching "balances" as an integer leave_id
@router.get("/balances/{employee_id}", response_model=LeaveBalanceListResponse, summary="Get leave balances for an employee")
def get_leave_balances(employee_id: int,
                       actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))],
                       db: DBSession,
                       year: int | None = Query(default=None, ge=2000, le=2100)):
    return service.get_leave_balances(employee_id=employee_id, actor=actor, db=db, year=year)


@router.get("/{leave_id}", response_model=LeaveRead, summary="Get a leave request by ID")
def get_leave(leave_id: int,
              actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))],
              db: DBSession):
    return service.get_leave_by_id(leave_id=leave_id, actor=actor, db=db)


@router.patch("/{leave_id}/approve", response_model=LeaveRead, dependencies=[AdminHRManager], summary="Approve a pending leave request")
def approve_leave(leave_id: int, request: Request,
                  actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER))],
                  db: DBSession):
    ip = request.client.host if request.client else None
    return service.approve_leave(leave_id=leave_id, actor=actor, db=db, ip_address=ip)


@router.patch("/{leave_id}/reject", response_model=LeaveRead, dependencies=[AdminHRManager], summary="Reject a pending leave request")
def reject_leave(leave_id: int, payload: LeaveReviewRequest, request: Request,
                 actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER))],
                 db: DBSession):
    if not payload.rejection_reason or not payload.rejection_reason.strip():
        from app.core.exceptions import BadRequestException
        raise BadRequestException("rejection_reason is required when rejecting a leave request")
    ip = request.client.host if request.client else None
    return service.reject_leave(leave_id=leave_id, rejection_reason=payload.rejection_reason,
                                actor=actor, db=db, ip_address=ip)


@router.delete("/{leave_id}/cancel", response_model=MessageResponse, summary="Cancel own leave request")
def cancel_leave(leave_id: int, request: Request,
                 actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER, Role.EMPLOYEE))],
                 db: DBSession):
    ip = request.client.host if request.client else None
    return service.cancel_leave(leave_id=leave_id, actor=actor, db=db, ip_address=ip)
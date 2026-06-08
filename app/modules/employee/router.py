from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.enums import Role
from app.dependencies import AdminOnly, AdminOrHR, AdminHRManager, CurrentUser, DBSession, require_roles
from app.modules.employee import service
from app.modules.employee.schemas import EmployeeCreate, EmployeeListResponse, EmployeeRead, EmployeeUpdate, MessageResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("/", response_model=EmployeeRead, status_code=201, dependencies=[AdminOrHR], summary="Create a new employee")
def create_employee(payload: EmployeeCreate, request: Request,
                    actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.create_employee(payload, actor=actor, db=db, ip_address=ip)


@router.get("/", response_model=EmployeeListResponse, dependencies=[AdminHRManager], summary="List employees with optional filters")
def list_employees(actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR, Role.MANAGER))],
                   db: DBSession,
                   role: Role | None = Query(default=None),
                   department_id: int | None = Query(default=None, gt=0),
                   is_active: bool | None = Query(default=None),
                   search: str | None = Query(default=None, max_length=100),
                   page: int = Query(default=1, ge=1),
                   page_size: int = Query(default=20, ge=1, le=100)):
    return service.list_employees(db=db, actor=actor, role_filter=role, department_id=department_id,
                                  is_active=is_active, search=search, page=page, page_size=page_size)


@router.get("/{employee_id}", response_model=EmployeeRead, summary="Get employee by ID")
def get_employee(employee_id: int, current_user: CurrentUser, db: DBSession):
    return service.get_employee_by_id(employee_id=employee_id, actor=current_user, db=db)


@router.patch("/{employee_id}", response_model=EmployeeRead, summary="Partially update an employee")
def update_employee(employee_id: int, payload: EmployeeUpdate, request: Request,
                    actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.update_employee(employee_id=employee_id, payload=payload, actor=actor, db=db, ip_address=ip)


@router.delete("/{employee_id}", response_model=MessageResponse, dependencies=[AdminOnly], summary="Deactivate an employee")
def deactivate_employee(employee_id: int, request: Request,
                        actor: Annotated[object, Depends(require_roles(Role.ADMIN))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.deactivate_employee(employee_id=employee_id, actor=actor, db=db, ip_address=ip)


@router.post("/{employee_id}/activate", response_model=EmployeeRead, dependencies=[AdminOnly], summary="Reactivate a deactivated employee")
def activate_employee(employee_id: int, request: Request,
                      actor: Annotated[object, Depends(require_roles(Role.ADMIN))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.reactivate_employee(employee_id=employee_id, actor=actor, db=db, ip_address=ip)
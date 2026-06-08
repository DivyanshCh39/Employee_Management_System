from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.enums import Role
from app.dependencies import AdminOrHR, CurrentUser, DBSession, require_roles
from app.modules.department import service
from app.modules.department.schemas import (
    DepartmentCreate, DepartmentListResponse, DepartmentRead, DepartmentUpdate, MessageResponse,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("/", response_model=DepartmentRead, status_code=201, dependencies=[AdminOrHR], summary="Create a new department")
def create_department(payload: DepartmentCreate, request: Request,
                      actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.create_department(payload, actor=actor, db=db, ip_address=ip)


@router.get("/", response_model=DepartmentListResponse, summary="List all departments")
def list_departments(_: CurrentUser, db: DBSession,
                     include_inactive: bool = Query(default=False)):
    return service.list_departments(db=db, include_inactive=include_inactive)


@router.get("/{department_id}", response_model=DepartmentRead, summary="Get department by ID")
def get_department(department_id: int, _: CurrentUser, db: DBSession):
    return service.get_department_by_id(department_id=department_id, db=db)


@router.patch("/{department_id}", response_model=DepartmentRead, summary="Partially update a department")
def update_department(department_id: int, payload: DepartmentUpdate, request: Request,
                      actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.update_department(department_id=department_id, payload=payload, actor=actor, db=db, ip_address=ip)


@router.delete("/{department_id}", response_model=MessageResponse, summary="Deactivate a department")
def deactivate_department(department_id: int, request: Request,
                          actor: Annotated[object, Depends(require_roles(Role.ADMIN, Role.HR))], db: DBSession):
    ip = request.client.host if request.client else None
    return service.deactivate_department(department_id=department_id, actor=actor, db=db, ip_address=ip)
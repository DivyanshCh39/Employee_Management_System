from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.department.schemas import (
    DepartmentCreate, DepartmentListResponse, DepartmentRead, DepartmentUpdate, MessageResponse,
)


def _write_audit(db, *, actor_id, action, entity_id, detail=None, ip_address=None):
    from app.modules.audit.model import AuditLog
    db.add(AuditLog(actor_id=actor_id, action=action.value, entity_type="Department",
                    entity_id=entity_id, detail=detail, ip_address=ip_address))


def _get_or_404(db: Session, department_id: int):
    from app.modules.department.model import Department
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise NotFoundException(f"Department with id={department_id} not found")
    return dept


def create_department(payload: DepartmentCreate, actor, db: Session, ip_address=None) -> DepartmentRead:
    from app.modules.department.model import Department
    existing = db.query(Department).filter(func.lower(Department.name) == payload.name.lower()).first()
    if existing:
        raise ConflictException(f"A department named '{payload.name}' already exists")
    dept = Department(name=payload.name, description=payload.description, is_active=True)
    db.add(dept)
    db.flush()
    _write_audit(db, actor_id=actor.id, action=AuditAction.DEPARTMENT_CREATED,
                 entity_id=dept.id, detail={"name": dept.name}, ip_address=ip_address)
    db.commit()
    db.refresh(dept)
    return DepartmentRead.model_validate(dept)


def list_departments(db: Session, include_inactive: bool = False) -> DepartmentListResponse:
    from app.modules.department.model import Department
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active == True)  # noqa: E712
    depts = query.order_by(Department.name.asc()).all()
    return DepartmentListResponse(items=[DepartmentRead.model_validate(d) for d in depts], total=len(depts))


def get_department_by_id(department_id: int, db: Session) -> DepartmentRead:
    return DepartmentRead.model_validate(_get_or_404(db, department_id))


def update_department(department_id: int, payload: DepartmentUpdate, actor, db: Session, ip_address=None) -> DepartmentRead:
    from app.modules.department.model import Department
    dept = _get_or_404(db, department_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        clash = db.query(Department).filter(
            func.lower(Department.name) == update_data["name"].lower(),
            Department.id != department_id,
        ).first()
        if clash:
            raise ConflictException(f"A department named '{update_data['name']}' already exists")
    before = {"name": dept.name, "description": dept.description, "is_active": dept.is_active}
    for field, value in update_data.items():
        setattr(dept, field, value)
    dept.updated_at = datetime.now(timezone.utc)
    _write_audit(db, actor_id=actor.id, action=AuditAction.DEPARTMENT_UPDATED,
                 entity_id=dept.id, detail={"before": before, "after": update_data}, ip_address=ip_address)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentRead.model_validate(dept)


def deactivate_department(department_id: int, actor, db: Session, ip_address=None) -> MessageResponse:
    from app.modules.employee.model import Employee
    dept = _get_or_404(db, department_id)
    if not dept.is_active:
        raise BadRequestException(f"Department '{dept.name}' is already inactive")
    active_count = db.query(func.count(Employee.id)).filter(
        Employee.department_id == department_id, Employee.is_active == True  # noqa: E712
    ).scalar() or 0
    dept.is_active = False
    dept.updated_at = datetime.now(timezone.utc)
    _write_audit(db, actor_id=actor.id, action=AuditAction.DEPARTMENT_DELETED,
                 entity_id=dept.id,
                 detail={"name": dept.name, "active_employees_affected": active_count},
                 ip_address=ip_address)
    db.add(dept)
    db.commit()
    msg = f"Department '{dept.name}' deactivated."
    if active_count:
        msg += f" {active_count} active employee(s) still assigned — reassign them."
    return MessageResponse(message=msg)
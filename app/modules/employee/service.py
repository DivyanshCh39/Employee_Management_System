import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, Role
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.security import hash_password
from app.modules.employee.schemas import (
    EmployeeCreate,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeRead,
    EmployeeUpdate,
    MessageResponse,
)


def _write_audit(db, *, actor_id, action, entity_type, entity_id, detail=None, ip_address=None):
    from app.modules.audit.model import AuditLog
    db.add(AuditLog(actor_id=actor_id, action=action.value, entity_type="Employee",
                    entity_id=entity_id, detail=detail, ip_address=ip_address))


def _get_or_404(db: Session, employee_id: int):
    from app.modules.employee.model import Employee
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise NotFoundException(f"Employee with id={employee_id} not found")
    return emp


def _generate_emp_code(db: Session) -> str:
    from app.modules.employee.model import Employee
    last = db.query(Employee.emp_code).order_by(Employee.id.desc()).first()
    if last is None:
        return "EMP001"
    try:
        last_num = int(last[0].replace("EMP", "").lstrip("0") or "0")
    except ValueError:
        count = db.query(func.count(Employee.id)).scalar() or 0
        last_num = count
    return f"EMP{str(last_num + 1).zfill(3)}"


def create_employee(payload: EmployeeCreate, actor, db: Session, ip_address=None) -> EmployeeRead:
    from app.modules.department.model import Department
    from app.modules.employee.model import Employee

    existing = db.query(Employee).filter(Employee.email == payload.email).first()
    if existing:
        raise ConflictException(f"An employee with email '{payload.email}' already exists")

    if payload.department_id is not None:
        dept = db.query(Department).filter(
            Department.id == payload.department_id, Department.is_active == True  # noqa: E712
        ).first()
        if not dept:
            raise BadRequestException(f"Department id={payload.department_id} does not exist or is inactive")

    if payload.manager_id is not None:
        manager = db.query(Employee).filter(Employee.id == payload.manager_id).first()
        if not manager:
            raise BadRequestException(f"Manager id={payload.manager_id} does not exist")
        if manager.role == Role.EMPLOYEE:
            raise BadRequestException(
                f"Employee id={payload.manager_id} has role EMPLOYEE and cannot be a manager."
            )

    # HR cannot assign ADMIN role
    if actor.role == Role.HR and payload.role == Role.ADMIN:
        raise ForbiddenException("HR cannot create an employee with the ADMIN role")

    emp_code = _generate_emp_code(db)
    new_employee = Employee(
        emp_code=emp_code, full_name=payload.full_name, email=payload.email,
        hashed_password=hash_password(payload.password), role=payload.role,
        phone=payload.phone, department_id=payload.department_id,
        manager_id=payload.manager_id, is_active=True,
    )
    db.add(new_employee)
    db.flush()

    _write_audit(db, actor_id=actor.id, action=AuditAction.EMPLOYEE_CREATED,
                 entity_type="Employee", entity_id=new_employee.id,
                 detail={"emp_code": emp_code, "email": payload.email, "role": payload.role.value},
                 ip_address=ip_address)

    db.commit()
    db.refresh(new_employee)
    return EmployeeRead.model_validate(new_employee)


def list_employees(db: Session, actor, role_filter=None, department_id=None,
                   is_active=None, search=None, page=1, page_size=20) -> EmployeeListResponse:
    from app.modules.employee.model import Employee

    query = db.query(Employee)

    if actor.role == Role.MANAGER:
        query = query.filter(Employee.manager_id == actor.id)
    elif actor.role == Role.EMPLOYEE:
        raise ForbiddenException("Employees cannot list other employees")

    if role_filter is not None:
        query = query.filter(Employee.role == role_filter)
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            func.lower(Employee.full_name).like(pattern) | func.lower(Employee.email).like(pattern)
        )

    total = query.with_entities(func.count(Employee.id)).scalar() or 0
    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    offset = (page - 1) * page_size

    items = query.order_by(Employee.emp_code.asc()).offset(offset).limit(page_size).all()

    return EmployeeListResponse(
        items=[EmployeeListItem.model_validate(e) for e in items],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


def get_employee_by_id(employee_id: int, actor, db: Session) -> EmployeeRead:
    emp = _get_or_404(db, employee_id)

    if actor.role == Role.MANAGER:
        if emp.id != actor.id and emp.manager_id != actor.id:
            raise ForbiddenException("Managers can only view their own profile or their direct reports")

    if actor.role == Role.EMPLOYEE and emp.id != actor.id:
        raise ForbiddenException("Employees can only view their own profile")

    return EmployeeRead.model_validate(emp)


def update_employee(employee_id: int, payload: EmployeeUpdate, actor, db: Session, ip_address=None) -> EmployeeRead:
    from app.modules.department.model import Department
    from app.modules.employee.model import Employee

    emp = _get_or_404(db, employee_id)

    if actor.role == Role.HR and emp.role == Role.ADMIN:
        raise ForbiddenException("HR cannot modify an ADMIN account")
    if actor.role == Role.HR and payload.role == Role.ADMIN:
        raise ForbiddenException("HR cannot assign the ADMIN role")

    before_snapshot = {"full_name": emp.full_name, "role": emp.role.value,
                       "phone": emp.phone, "department_id": emp.department_id,
                       "manager_id": emp.manager_id, "is_active": emp.is_active}

    update_data = payload.model_dump(exclude_unset=True)

    if "department_id" in update_data and update_data["department_id"] is not None:
        dept = db.query(Department).filter(
            Department.id == update_data["department_id"], Department.is_active == True  # noqa: E712
        ).first()
        if not dept:
            raise BadRequestException(f"Department id={update_data['department_id']} does not exist or is inactive")

    if "manager_id" in update_data and update_data["manager_id"] is not None:
        manager = db.query(Employee).filter(Employee.id == update_data["manager_id"]).first()
        if not manager:
            raise BadRequestException(f"Manager id={update_data['manager_id']} does not exist")
        if manager.role == Role.EMPLOYEE:
            raise BadRequestException(f"Employee id={update_data['manager_id']} has role EMPLOYEE and cannot be assigned as manager")
        if update_data["manager_id"] == employee_id:
            raise BadRequestException("An employee cannot be their own manager")

    for field, value in update_data.items():
        setattr(emp, field, value)
    emp.updated_at = datetime.now(timezone.utc)

    _write_audit(db, actor_id=actor.id, action=AuditAction.EMPLOYEE_UPDATED,
                 entity_type="Employee", entity_id=emp.id,
                 detail={"before": before_snapshot, "after": update_data}, ip_address=ip_address)

    db.add(emp)
    db.commit()
    db.refresh(emp)
    return EmployeeRead.model_validate(emp)


def deactivate_employee(employee_id: int, actor, db: Session, ip_address=None) -> MessageResponse:
    emp = _get_or_404(db, employee_id)

    if emp.id == actor.id:
        raise BadRequestException("You cannot deactivate your own account")
    if not emp.is_active:
        raise BadRequestException(f"Employee '{emp.full_name}' (id={employee_id}) is already inactive")

    emp.is_active = False
    emp.updated_at = datetime.now(timezone.utc)

    _write_audit(db, actor_id=actor.id, action=AuditAction.EMPLOYEE_DELETED,
                 entity_type="Employee", entity_id=emp.id,
                 detail={"emp_code": emp.emp_code, "email": emp.email, "action": "deactivated"},
                 ip_address=ip_address)

    db.add(emp)
    db.commit()
    return MessageResponse(message=f"Employee '{emp.full_name}' (id={employee_id}) has been deactivated")


def reactivate_employee(employee_id: int, actor, db: Session, ip_address=None) -> EmployeeRead:
    emp = _get_or_404(db, employee_id)

    if emp.is_active:
        raise BadRequestException(f"Employee '{emp.full_name}' (id={employee_id}) is already active")

    emp.is_active = True
    emp.updated_at = datetime.now(timezone.utc)

    _write_audit(db, actor_id=actor.id, action=AuditAction.EMPLOYEE_UPDATED,
                 entity_type="Employee", entity_id=emp.id,
                 detail={"emp_code": emp.emp_code, "action": "reactivated"}, ip_address=ip_address)

    db.add(emp)
    db.commit()
    db.refresh(emp)
    return EmployeeRead.model_validate(emp)
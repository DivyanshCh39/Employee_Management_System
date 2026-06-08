"""
Shared pytest fixtures.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.enums import LeaveType, Role
from app.core.security import hash_password
from app.db.base import Base
from app.dependencies import get_db
from app.main import app

TEST_DB_PATH = "/tmp/ems_pytest.db"
engine = create_engine(
    f"sqlite:///{TEST_DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        os.remove(TEST_DB_PATH)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def clean_db(create_tables):
    yield
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()


@pytest.fixture
def db():
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def _db_override():
        s = SessionFactory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db_override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def seed_leave_configs(db):
    from app.modules.leave.model import LeaveTypeConfig

    rows = [
        LeaveTypeConfig(
            leave_type=LeaveType.SICK, max_days_per_year=12,
            is_carry_forward_allowed=False, requires_document=False, is_active=True,
        ),
        LeaveTypeConfig(
            leave_type=LeaveType.CASUAL, max_days_per_year=12,
            is_carry_forward_allowed=False, requires_document=False, is_active=True,
        ),
        LeaveTypeConfig(
            leave_type=LeaveType.EARNED, max_days_per_year=15,
            is_carry_forward_allowed=True, requires_document=False, is_active=True,
        ),
        LeaveTypeConfig(
            leave_type=LeaveType.UNPAID, max_days_per_year=0,
            is_carry_forward_allowed=False, requires_document=False, is_active=True,
        ),
    ]
    db.add_all(rows)
    db.commit()
    return {r.leave_type: r for r in rows}


@pytest.fixture
def admin_employee(db):
    from app.modules.employee.model import Employee
    uid = _uid()
    emp = Employee(
        emp_code=f"ADM{uid}", full_name="System Admin",
        email=f"admin_{uid}@test.com",
        hashed_password=hash_password("Admin@1234"),
        role=Role.ADMIN, is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def hr_employee(db):
    from app.modules.employee.model import Employee
    uid = _uid()
    emp = Employee(
        emp_code=f"HR{uid}", full_name="HR Manager",
        email=f"hr_{uid}@test.com",
        hashed_password=hash_password("HR@12345"),
        role=Role.HR, is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def manager_employee(db):
    from app.modules.employee.model import Employee
    uid = _uid()
    emp = Employee(
        emp_code=f"MGR{uid}", full_name="Team Manager",
        email=f"manager_{uid}@test.com",
        hashed_password=hash_password("Mgr@12345"),
        role=Role.MANAGER, is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def regular_employee(db, manager_employee):
    from app.modules.employee.model import Employee
    uid = _uid()
    emp = Employee(
        emp_code=f"EMP{uid}", full_name="Jane Employee",
        email=f"employee_{uid}@test.com",
        hashed_password=hash_password("Emp@12345"),
        role=Role.EMPLOYEE, is_active=True,
        manager_id=manager_employee.id,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _get_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email!r}: {resp.text}"
    return resp.json()["access_token"]


def _set_auth(client: TestClient, token: str) -> TestClient:
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def admin_client(client, admin_employee):
    token = _get_token(client, admin_employee.email, "Admin@1234")
    return _set_auth(client, token)


@pytest.fixture
def hr_client(client, hr_employee):
    token = _get_token(client, hr_employee.email, "HR@12345")
    return _set_auth(client, token)


@pytest.fixture
def manager_client(client, manager_employee):
    token = _get_token(client, manager_employee.email, "Mgr@12345")
    return _set_auth(client, token)


@pytest.fixture
def employee_client(client, regular_employee, manager_employee):
    token = _get_token(client, regular_employee.email, "Emp@12345")
    return _set_auth(client, token)


@pytest.fixture
def all_tokens(
    client,
    admin_employee,
    hr_employee,
    manager_employee,
    regular_employee,
):
    return {
        "admin":    _get_token(client, admin_employee.email,   "Admin@1234"),
        "hr":       _get_token(client, hr_employee.email,      "HR@12345"),
        "manager":  _get_token(client, manager_employee.email, "Mgr@12345"),
        "employee": _get_token(client, regular_employee.email, "Emp@12345"),
    }
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import Role


class DepartmentNested(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class ManagerNested(BaseModel):
    id: int
    emp_code: str
    full_name: str
    email: EmailStr
    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Field(default=Role.EMPLOYEE)
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = Field(default=None, gt=0)
    manager_id: int | None = Field(default=None, gt=0)

    @field_validator("full_name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_name must not be blank or whitespace")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def phone_digits_only(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = set("0123456789 +-+()")
        if not all(ch in allowed for ch in v):
            raise ValueError("phone may only contain digits, spaces, +, -, (, )")
        return v.strip()


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    role: Role | None = None
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = Field(default=None)
    manager_id: int | None = Field(default=None)
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("full_name must not be blank")
        return v.strip() if v else v


class EmployeeRead(BaseModel):
    id: int
    emp_code: str
    full_name: str
    email: EmailStr
    role: Role
    phone: str | None
    is_active: bool
    department_id: int | None
    manager_id: int | None
    department: DepartmentNested | None = None
    manager: ManagerNested | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class EmployeeListItem(BaseModel):
    id: int
    emp_code: str
    full_name: str
    email: EmailStr
    role: Role
    phone: str | None
    is_active: bool
    department_id: int | None
    manager_id: int | None
    created_at: datetime
    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    items: list[EmployeeListItem]
    total: int
    page: int
    page_size: int
    pages: int


class MessageResponse(BaseModel):
    message: str
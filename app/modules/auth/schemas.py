from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import Role


class EmployeeSummary(BaseModel):
    id: int
    emp_code: str
    full_name: str
    email: EmailStr
    role: Role
    department_id: int | None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)

    @field_validator("confirm_password")
    @classmethod
    def passwords_must_match(cls, confirm: str, info) -> str:
        if "new_password" in info.data and confirm != info.data["new_password"]:
            raise ValueError("new_password and confirm_password do not match")
        return confirm


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    employee: EmployeeSummary


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: int
    emp_code: str
    full_name: str
    email: EmailStr
    role: Role
    phone: str | None
    department_id: int | None
    manager_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
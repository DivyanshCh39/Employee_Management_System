from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import LeaveStatus, LeaveType


class EmployeeNested(BaseModel):
    id: int
    emp_code: str
    full_name: str
    model_config = {"from_attributes": True}


class ReviewerNested(BaseModel):
    id: int
    emp_code: str
    full_name: str
    model_config = {"from_attributes": True}


class LeaveApplyRequest(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    @model_validator(mode="after")
    def end_must_be_gte_start(self) -> "LeaveApplyRequest":
        if self.end_date < self.start_date:
            raise ValueError(f"end_date ({self.end_date}) must be on or after start_date ({self.start_date})")
        return self

    @model_validator(mode="after")
    def start_date_not_in_past(self) -> "LeaveApplyRequest":
        if self.start_date < date.today():
            raise ValueError(f"start_date ({self.start_date}) cannot be in the past.")
        return self


class LeaveReviewRequest(BaseModel):
    rejection_reason: str | None = Field(default=None, max_length=500)


class LeaveRead(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    reason: str | None
    status: LeaveStatus
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    employee: EmployeeNested | None = None
    reviewer: ReviewerNested | None = None
    model_config = {"from_attributes": True}


class LeaveListItem(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    status: LeaveStatus
    reviewed_by_id: int | None
    created_at: datetime
    employee: EmployeeNested | None = None
    model_config = {"from_attributes": True}


class LeaveListResponse(BaseModel):
    items: list[LeaveListItem]
    total: int
    page: int
    page_size: int
    pages: int


class LeaveBalanceRead(BaseModel):
    id: int
    employee_id: int
    leave_type_config_id: int
    leave_type: LeaveType
    year: int
    allocated_days: float
    used_days: float
    remaining_days: float
    model_config = {"from_attributes": True}


class LeaveBalanceListResponse(BaseModel):
    employee_id: int
    year: int
    balances: list[LeaveBalanceRead]


class MessageResponse(BaseModel):
    message: str
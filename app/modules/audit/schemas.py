
from datetime import datetime
from pydantic import BaseModel


class ActorNested(BaseModel):
    id: int
    emp_code: str
    full_name: str
    model_config = {"from_attributes": True}


class AuditLogRead(BaseModel):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    detail: dict | None
    ip_address: str | None
    created_at: datetime
    actor: ActorNested | None = None
    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
    pages: int
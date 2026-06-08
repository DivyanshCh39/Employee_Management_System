# app/modules/audit/router.py
from fastapi import APIRouter, Query

from app.dependencies import AdminOnly, DBSession
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogListResponse, AuditLogRead

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("/logs", response_model=AuditLogListResponse, dependencies=[AdminOnly], summary="List audit log entries")
def list_audit_logs(db: DBSession,
                    actor_id: int | None = Query(default=None, gt=0),
                    action: str | None = Query(default=None, max_length=100),
                    entity_type: str | None = Query(default=None, max_length=50),
                    entity_id: int | None = Query(default=None, gt=0),
                    page: int = Query(default=1, ge=1),
                    page_size: int = Query(default=50, ge=1, le=200)):
    return service.list_audit_logs(db=db, actor_id=actor_id, action=action,
                                   entity_type=entity_type, entity_id=entity_id,
                                   page=page, page_size=page_size)


@router.get("/logs/{log_id}", response_model=AuditLogRead, dependencies=[AdminOnly], summary="Get a single audit log entry")
def get_audit_log(log_id: int, db: DBSession):
    return service.get_audit_log_by_id(log_id=log_id, db=db)
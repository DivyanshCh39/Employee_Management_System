# app/modules/audit/service.py
import math
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.modules.audit.schemas import AuditLogListResponse, AuditLogRead


def list_audit_logs(db: Session, actor_id=None, action=None, entity_type=None,
                    entity_id=None, page=1, page_size=50) -> AuditLogListResponse:
    from app.modules.audit.model import AuditLog

    query = db.query(AuditLog)
    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if entity_type is not None:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)

    total = query.with_entities(func.count(AuditLog.id)).scalar() or 0
    page_size = max(1, min(page_size, 200))
    page = max(1, page)
    offset = (page - 1) * page_size
    items = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()

    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(log) for log in items],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


def get_audit_log_by_id(log_id: int, db: Session) -> AuditLogRead:
    from app.modules.audit.model import AuditLog
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        raise NotFoundException(f"Audit log entry with id={log_id} not found")
    return AuditLogRead.model_validate(log)
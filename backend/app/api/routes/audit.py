from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas.notification import AuditEntry

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    action: str | None = None,
    entity_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actor_names = {
        uid: (db.get(User, uid).full_name if db.get(User, uid) else None)
        for uid in actor_ids
    }

    items = []
    for r in rows:
        entry = AuditEntry.model_validate(r).model_dump()
        entry["actor_name"] = actor_names.get(r.actor_id)
        entry["metadata"] = entry.pop("metadata_json", None)
        items.append(entry)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
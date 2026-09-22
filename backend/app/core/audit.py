import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


def audit_action(action: str, entity_type: str | None = None):
    """Thin helper to serialize audit metadata safely (JSON-safe)."""

    def _safe(payload: dict | None) -> dict | None:
        if not payload:
            return None
        try:
            json.dumps(payload)
            return payload
        except (TypeError, ValueError):
            return {"note": str(payload)}

    def _decorator(func):
        def _wrapper(db: Session, actor: User, *args, **kwargs):
            result = func(db, actor, *args, **kwargs)
            record_audit(
                db, actor, action, entity_type, _safe(kwargs.get("audit_meta"))
            )
            return result

        return _wrapper

    return _decorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BatchMembership, User, UserRole


def get_intern_active_batch(db: Session, intern_id: int) -> BatchMembership | None:
    return db.execute(
        select(BatchMembership)
        .where(BatchMembership.intern_id == intern_id, BatchMembership.is_active.is_(True))
    ).scalar_one_or_none()


def get_supervised_batch_ids(db: Session, supervisor_id: int) -> list[int]:
    rows = db.execute(
        select(BatchMembership.batch_id)
        .join(BatchMembership.batch)
        .where(BatchMembership.batch.has(supervisor_id=supervisor_id))
        .distinct()
    )
    return [r[0] for r in rows]


def ensure_supervisor_manages(db: Session, supervisor: User, batch_id: int) -> None:
    from app.models import Batch

    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.supervisor_id != supervisor.id:
        raise HTTPException(status_code=403, detail="Not the assigned supervisor of this batch")


def ensure_batch_active(batch: object) -> None:
    """Reject operational mutations against archived batches."""
    from app.models import BatchStatus

    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status == BatchStatus.ARCHIVED:
        raise HTTPException(
            status_code=403, detail="Archived batches are read-only"
        )


def ensure_supervisor_manages_any(db: Session, supervisor: User) -> bool:
    from app.models import Batch

    return (
        db.execute(select(Batch).where(Batch.supervisor_id == supervisor.id)).first()
        is not None
    )


def ensure_intern_in_batch(db: Session, intern_id: int, batch_id: int) -> BatchMembership:
    membership = db.execute(
        select(BatchMembership).where(
            BatchMembership.intern_id == intern_id,
            BatchMembership.batch_id == batch_id,
            BatchMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Intern is not an active member of this batch",
        )
    return membership


def resolve_intern_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.role != UserRole.INTERN:
        raise HTTPException(status_code=404, detail="Intern not found")
    return user
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import (
    get_current_user,
    require_admin,
)
from app.db.session import get_db
from app.models import (
    Batch,
    BatchMembership,
    BatchStatus,
    User,
    UserRole,
)
from app.schemas.batch import (
    AddInternRequest,
    AddInternsRequest,
    BatchCreate,
    BatchDetail,
    BatchMembershipOut,
    BatchOut,
    BatchUpdate,
    PaginatedBatches,
)

router = APIRouter(prefix="/batches", tags=["batches"])


def _to_out(batch: Batch, memberships: list[BatchMembership]) -> BatchOut:
    out = BatchOut.model_validate(batch)
    out.supervisor_name = batch.supervisor.full_name if batch.supervisor else None
    out.active_intern_count = sum(1 for m in memberships if m.is_active)
    return out


def _memberships_out(db: Session, batch_id: int) -> list[BatchMembershipOut]:
    rows = db.execute(
        select(BatchMembership)
        .where(BatchMembership.batch_id == batch_id)
        .order_by(BatchMembership.joined_at)
    ).scalars().all()
    result = []
    for m in rows:
        intern = m.intern
        result.append(
            BatchMembershipOut(
                id=m.id,
                intern_id=m.intern_id,
                intern_name=intern.full_name if intern else None,
                email=intern.email if intern else None,
                is_active=m.is_active,
                joined_at=m.joined_at,
            )
        )
    return result


@router.get("", response_model=PaginatedBatches)
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str = "",
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Batch)
    if user.role == UserRole.SUPERVISOR:
        query = query.where(Batch.supervisor_id == user.id)
    elif user.role == UserRole.INTERN:
        batch_id = _intern_batch_id(db, user.id)
        query = query.where(Batch.id == batch_id if batch_id else Batch.id == -1)
    if not include_archived:
        query = query.where(Batch.status != BatchStatus.ARCHIVED)
    if status_filter:
        query = query.where(Batch.status == status_filter)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(Batch.name.ilike(like))
    total = db.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar() or 0
    batches = db.execute(
        query.order_by(Batch.start_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    items = []
    for b in batches:
        members = db.execute(
            select(BatchMembership).where(BatchMembership.batch_id == b.id)
        ).scalars().all()
        items.append(_to_out(b, members))
    return PaginatedBatches(items=items, total=total, page=page, page_size=page_size)


def _intern_batch_id(db: Session, intern_id: int) -> int | None:
    row = db.execute(
        select(BatchMembership.batch_id).where(
            BatchMembership.intern_id == intern_id,
            BatchMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return row if row else None


@router.post("", response_model=BatchOut)
def create_batch(
    payload: BatchCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    supervisor = db.get(User, payload.supervisor_id)
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR:
        raise HTTPException(status_code=400, detail="Assigned user is not a supervisor")
    if payload.start_date >= payload.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    batch = Batch(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        supervisor_id=payload.supervisor_id,
        capacity=payload.capacity,
        start_time=payload.start_time,
        end_time=payload.end_time,
        grace_minutes=payload.grace_minutes,
        status=BatchStatus.ACTIVE,
    )
    db.add(batch)
    db.flush()
    record_audit(db, admin, "batches.create", "batch", batch.id)
    db.commit()
    db.refresh(batch)
    return _to_out(batch, [])


@router.get("/{batch_id}", response_model=BatchDetail)
def get_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    _authorize_view(db, user, batch)
    members = db.execute(
        select(BatchMembership).where(BatchMembership.batch_id == batch_id)
    ).scalars().all()
    detail = BatchDetail(**_to_out(batch, members).model_dump())
    detail.memberships = _memberships_out(db, batch_id)
    return detail


def _authorize_view(db: Session, user: User, batch: Batch) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        if batch.supervisor_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Not assigned to this batch")
    if user.role == UserRole.INTERN:
        membership = db.execute(
            select(BatchMembership).where(
                BatchMembership.intern_id == user.id,
                BatchMembership.batch_id == batch.id,
                BatchMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=403, detail="Not a member of this batch")
        return


@router.patch("/{batch_id}", response_model=BatchOut)
def update_batch(
    batch_id: int,
    payload: BatchUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status == BatchStatus.ARCHIVED:
        raise HTTPException(status_code=403, detail="Archived batches are read-only")
    updates = payload.model_dump(exclude_unset=True)
    if "supervisor_id" in updates and updates["supervisor_id"]:
        supervisor = db.get(User, updates["supervisor_id"])
        if supervisor is None or supervisor.role != UserRole.SUPERVISOR:
            raise HTTPException(status_code=400, detail="Assigned user is not a supervisor")
    for k, v in updates.items():
        setattr(batch, k, v)
    record_audit(db, admin, "batches.update", "batch", batch_id)
    db.commit()
    db.refresh(batch)
    members = db.execute(
        select(BatchMembership).where(BatchMembership.batch_id == batch_id)
    ).scalars().all()
    return _to_out(batch, members)


@router.post("/{batch_id}/archive", response_model=BatchOut)
def archive_batch(
    batch_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch.status = BatchStatus.ARCHIVED
    for m in db.execute(
        select(BatchMembership).where(BatchMembership.batch_id == batch_id)
    ).scalars():
        m.is_active = False
        m.left_at = __import__("datetime").datetime.utcnow()
    record_audit(db, admin, "batches.archive", "batch", batch_id)
    db.commit()
    db.refresh(batch)
    return _to_out(batch, [])


@router.post("/{batch_id}/interns")
def add_intern(
    batch_id: int,
    payload: AddInternRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status == BatchStatus.ARCHIVED:
        raise HTTPException(status_code=403, detail="Archived batches are read-only")
    intern = db.get(User, payload.user_id)
    if intern is None or intern.role != UserRole.INTERN:
        raise HTTPException(status_code=400, detail="User is not an intern")

    active_count = db.execute(
        select(func.count()).select_from(BatchMembership).where(
            BatchMembership.batch_id == batch_id, BatchMembership.is_active.is_(True)
        )
    ).scalar() or 0
    if active_count >= batch.capacity:
        raise HTTPException(status_code=400, detail="Batch capacity reached")

    existing_active = db.execute(
        select(BatchMembership).where(
            BatchMembership.intern_id == payload.user_id, BatchMembership.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if existing_active:
        if existing_active.batch_id == batch_id:
            raise HTTPException(status_code=400, detail="Intern already in this batch")
        raise HTTPException(
            status_code=400, detail="Intern already belongs to another active batch"
        )

    membership = BatchMembership(
        batch_id=batch_id, intern_id=payload.user_id, is_active=True
    )
    db.add(membership)
    record_audit(db, admin, "batches.add_intern", "batch", batch_id)
    db.commit()
    return {"message": "Intern added to batch"}


@router.post("/{batch_id}/interns/bulk")
def add_interns(
    batch_id: int,
    payload: AddInternsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status == BatchStatus.ARCHIVED:
        raise HTTPException(status_code=403, detail="Archived batches are read-only")

    active_count = db.execute(
        select(func.count()).select_from(BatchMembership).where(
            BatchMembership.batch_id == batch_id, BatchMembership.is_active.is_(True)
        )
    ).scalar() or 0
    if active_count + len(payload.user_ids) > batch.capacity:
        raise HTTPException(status_code=400, detail="Adding interns would exceed batch capacity")

    added = 0
    skipped = []
    for uid in payload.user_ids:
        intern = db.get(User, uid)
        if intern is None or intern.role != UserRole.INTERN:
            skipped.append({"user_id": uid, "error": "Not an intern"})
            continue
        existing = db.execute(
            select(BatchMembership).where(
                BatchMembership.intern_id == uid, BatchMembership.is_active.is_(True)
            )
        ).scalar_one_or_none()
        if existing:
            skipped.append({"user_id": uid, "error": "Already in an active batch"})
            continue
        db.add(BatchMembership(batch_id=batch_id, intern_id=uid, is_active=True))
        added += 1
    record_audit(
        db, admin, "batches.bulk_add_interns",
        metadata={"batch_id": batch_id, "added": added, "skipped": skipped},
    )
    db.commit()
    return {"added": added, "skipped": skipped}


@router.delete("/{batch_id}/interns/{intern_id}")
def remove_intern(
    batch_id: int,
    intern_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.execute(
        select(BatchMembership).where(
            BatchMembership.batch_id == batch_id, BatchMembership.intern_id == intern_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership.is_active = False
    membership.left_at = __import__("datetime").datetime.utcnow()
    record_audit(db, admin, "batches.remove_intern", "batch", batch_id)
    db.commit()
    return {"message": "Intern removed from batch"}
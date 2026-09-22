from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AttendanceRecord,
    AttendanceStatus,
    Batch,
    BatchMembership,
    LeaveRequest,
    User,
)
from app.services.access import get_intern_active_batch
from app.utils.time import utcnow


def get_or_create_record(
    db: Session, intern_id: int, for_date: date | None = None
) -> tuple[AttendanceRecord, Batch | None]:
    day = for_date or date.today()
    membership = get_intern_active_batch(db, intern_id)
    if membership is None:
        return None, None
    batch = db.get(Batch, membership.batch_id)
    record = db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.intern_id == intern_id, AttendanceRecord.date == day)
    ).scalar_one_or_none()
    if record is None:
        record = AttendanceRecord(intern_id=intern_id, batch_id=batch.id, date=day)
        db.add(record)
        db.flush()
    return record, batch


def check_in(db: Session, intern: User) -> AttendanceRecord | None:
    record, batch = get_or_create_record(db, intern.id)
    if record is None or batch is None:
        return None
    if record.check_in is not None:
        return record
    now = utcnow()
    record.check_in = now

    start = batch.working_start
    grace_end_minutes = (
        start.hour * 60 + start.minute + (batch.grace_minutes or 0)
    )
    check_minutes = now.hour * 60 + now.minute
    record.late_status = (
        AttendanceStatus.LATE if check_minutes > grace_end_minutes else AttendanceStatus.ON_TIME
    )
    db.flush()
    return record


def check_out(db: Session, intern: User, work_done: str | None = None) -> AttendanceRecord | None:
    record, _ = get_or_create_record(db, intern.id)
    if record is None:
        return None
    if record.check_in is None:
        return None
    if record.check_out is not None:
        return record
    now = utcnow()
    record.check_out = now
    worked = (now - record.check_in).total_seconds() / 3600.0
    record.worked_hours = round(max(worked, 0.0), 2)
    if work_done:
        record.work_done = work_done
    db.flush()
    return record


def save_daily_log(
    db: Session,
    intern: User,
    work_done: str | None = None,
    blockers: str | None = None,
    next_day_plan: str | None = None,
) -> AttendanceRecord | None:
    record, _ = get_or_create_record(db, intern.id)
    if record is None:
        return None
    if work_done is not None:
        record.work_done = work_done
    if blockers is not None:
        record.blockers = blockers
    if next_day_plan is not None:
        record.next_day_plan = next_day_plan
    db.flush()
    return record


def is_on_approved_leave(db: Session, intern_id: int, day: date) -> bool:
    return (
        db.execute(
            select(LeaveRequest).where(
                LeaveRequest.intern_id == intern_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= day,
                LeaveRequest.end_date >= day,
            )
        ).first()
        is not None
    )


def attendance_overview(db: Session, batch_id: int) -> list[dict]:
    """Present / late / hours summary per intern for a batch, excluding
    approved-leave days from absence counts."""

    records = db.execute(
        select(AttendanceRecord)
        .options(joinedload(AttendanceRecord.intern))
        .where(AttendanceRecord.batch_id == batch_id)
    ).scalars()

    interns: dict[int, dict] = {}
    for rec in records:
        entry = interns.setdefault(
            rec.intern_id,
            {
                "intern_id": rec.intern_id,
                "intern_name": rec.intern.full_name if rec.intern else "",
                "present_days": 0,
                "late_days": 0,
                "total_hours": 0.0,
                "workdays": 0,
            },
        )
        entry["workdays"] += 1
        if rec.check_in is not None:
            entry["present_days"] += 1
            if rec.late_status == AttendanceStatus.LATE:
                entry["late_days"] += 1
            entry["total_hours"] += rec.worked_hours or 0.0
        else:
            # count as absent unless on approved leave
            if not is_on_approved_leave(db, rec.intern_id, rec.date):
                entry["absent_days"] = entry.get("absent_days", 0) + 1

    for entry in interns.values():
        total = entry["workdays"] - entry.get("absent_days", 0)
        entry["attendance_rate"] = round(entry["present_days"] / total * 100, 1) if total else 0.0
    return sorted(interns.values(), key=lambda x: x["intern_name"].lower())


def batch_member_ids(db: Session, batch_id: int) -> list[int]:
    rows = db.execute(
        select(BatchMembership.intern_id).where(
            BatchMembership.batch_id == batch_id, BatchMembership.is_active.is_(True)
        )
    )
    return [r[0] for r in rows]
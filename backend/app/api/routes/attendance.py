from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import (
    get_current_user,
    require_admin,
    require_any_authenticated,
)
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    AttendanceRemark,
    Batch,
    LeaveRequest,
    User,
    UserRole,
)
from app.schemas.attendance import (
    AttendanceOut,
    AttendanceSummaryRow,
    DailyLogUpdate,
    LeaveCreate,
    LeaveDecision,
    LeaveOut,
    RemarkCreate,
)
from app.services.access import (
    ensure_supervisor_manages,
    get_intern_active_batch,
    get_supervised_batch_ids,
)
from app.services.attendance import (
    attendance_overview,
    check_in,
    check_out,
    save_daily_log,
)
from app.services.notifications import notify_many

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _att_out(record: AttendanceRecord) -> AttendanceOut:
    out = AttendanceOut.model_validate(record)
    out.remarks = [
        {
            "id": r.id,
            "supervisor_name": r.supervisor.full_name if r.supervisor else None,
            "remark": r.remark,
            "created_at": r.created_at.isoformat(),
        }
        for r in record.remarks
    ]
    return out


@router.post("/check-in", response_model=AttendanceOut)
def do_check_in(
    intern: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    if intern.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns can check in")
    record = check_in(db, intern)
    if record is None:
        raise HTTPException(status_code=403, detail="You are not assigned to an active batch")
    record_audit(db, intern, "attendance.check_in", "attendance", record.id)
    _notify_supervisor(db, record, intern, "checked in")
    db.commit()
    db.refresh(record)
    return _att_out(record)


@router.post("/check-out", response_model=AttendanceOut)
def do_check_out(
    payload: DailyLogUpdate | None = None,
    intern: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    if intern.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns can check out")
    data = payload.model_dump() if payload else {}
    record = check_out(db, intern, data.get("work_done"))
    if record is None:
        raise HTTPException(status_code=403, detail="You have not checked in today")
    record_audit(db, intern, "attendance.check_out", "attendance", record.id)
    _notify_supervisor(db, record, intern, "checked out")
    db.commit()
    db.refresh(record)
    return _att_out(record)


def _notify_supervisor(db: Session, record: AttendanceRecord, intern: User, verb: str) -> None:
    batch = db.get(Batch, record.batch_id)
    if batch and batch.supervisor_id:
        notify_many(
            db, [batch.supervisor_id], "attendance_update",
            f"{intern.full_name} {verb}",
            f"{intern.full_name} {verb} today ({record.date}).",
            link=f"/attendance?date={record.date}",
            actor_id=intern.id,
        )


@router.post("/daily-log", response_model=AttendanceOut)
def update_daily_log(
    payload: DailyLogUpdate,
    intern: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    if intern.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns can update daily logs")
    record = save_daily_log(
        db, intern, payload.work_done, payload.blockers, payload.next_day_plan
    )
    if record is None:
        raise HTTPException(status_code=403, detail="Not assigned to an active batch")
    db.commit()
    db.refresh(record)
    return _att_out(record)


@router.get("/today")
def my_today(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    day = date.today()
    if user.role == UserRole.INTERN:
        membership = get_intern_active_batch(db, user.id)
        if membership is None:
            return None
        record = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.intern_id == user.id, AttendanceRecord.date == day
            )
        ).scalar_one_or_none()
        return _att_out(record) if record else None
    raise HTTPException(status_code=403, detail="Only interns have a daily attendance view")


@router.get("/summary")
def attendance_summary(
    batch_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == UserRole.INTERN:
        membership = get_intern_active_batch(db, user.id)
        b_id = membership.batch_id if membership else None
        if b_id is None:
            return []
        return _summarize(db, b_id, intern_id=user.id)
    if user.role == UserRole.SUPERVISOR:
        allowed = set(get_supervised_batch_ids(db, user.id))
        if batch_id is not None and batch_id not in allowed:
            raise HTTPException(status_code=403, detail="Not assigned to this batch")
        if batch_id is None and allowed:
            batch_id = next(iter(allowed))
        if batch_id is None:
            return []
        return _summarize(db, batch_id)
    # Admin
    if batch_id is not None:
        return _summarize(db, batch_id)
    # organization-wide: merge across active batches
    batch_ids = [r[0] for r in db.execute(select(Batch.id).where(Batch.status == "active"))]
    merged: dict[int, AttendanceSummaryRow] = {}
    for bid in batch_ids:
        for row in _summarize(db, bid):
            merged[row.intern_id] = row
    return sorted(merged.values(), key=lambda r: r.intern_name.lower())


def _summarize(db: Session, batch_id: int, intern_id: int | None = None) -> list[dict]:
    rows = attendance_overview(db, batch_id)
    if intern_id is not None:
        rows = [r for r in rows if r["intern_id"] == intern_id]
    return rows


@router.post("/{attendance_id}/remarks", response_model=AttendanceOut)
def add_remark(
    attendance_id: int,
    payload: RemarkCreate,
    supervisor: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    if supervisor.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only supervisors can add remarks")
    record = db.get(AttendanceRecord, attendance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, record.batch_id)
    remark = AttendanceRemark(
        attendance_id=attendance_id,
        supervisor_id=supervisor.id,
        remark=payload.remark,
    )
    db.add(remark)
    db.commit()
    db.refresh(record)
    return _att_out(record)


# ---------------- Attendance record raw view by supervisor/admin ----------------

@router.get("/records")
def list_records(
    batch_id: int | None = None,
    intern_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(AttendanceRecord)
    if user.role == UserRole.INTERN:
        query = query.where(AttendanceRecord.intern_id == user.id)
    elif user.role == UserRole.SUPERVISOR:
        allowed = set(get_supervised_batch_ids(db, user.id))
        if batch_id is not None and batch_id not in allowed:
            raise HTTPException(status_code=403, detail="Not assigned to this batch")
        if batch_id is None:
            query = query.where(AttendanceRecord.batch_id.in_(allowed) if allowed else AttendanceRecord.id == -1)
        else:
            query = query.where(AttendanceRecord.batch_id == batch_id)
    if batch_id is not None and user.role != UserRole.SUPERVISOR:
        query = query.where(AttendanceRecord.batch_id == batch_id)
    if intern_id is not None:
        query = query.where(AttendanceRecord.intern_id == intern_id)
    if from_date:
        query = query.where(AttendanceRecord.date >= from_date)
    if to_date:
        query = query.where(AttendanceRecord.date <= to_date)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    records = db.execute(
        query.order_by(AttendanceRecord.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "items": [_att_out(r) for r in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------- Leave ----------------

LEAVE_ROUTER = APIRouter(prefix="/leave", tags=["leave"])


@LEAVE_ROUTER.post("", response_model=LeaveOut)
def create_leave(
    payload: LeaveCreate,
    intern: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    if intern.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns can request leave")
    membership = get_intern_active_batch(db, intern.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not assigned to an active batch")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    leave = LeaveRequest(
        intern_id=intern.id,
        batch_id=membership.batch_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        note=payload.note,
        status="pending",
    )
    db.add(leave)
    db.flush()
    batch = db.get(Batch, membership.batch_id)
    if batch and batch.supervisor_id:
        notify_many(
            db, [batch.supervisor_id], "leave_decision",
            "New leave request",
            f"{intern.full_name} requested leave {payload.start_date} to {payload.end_date}.",
        )
    db.commit()
    db.refresh(leave)
    return _leave_out(leave)


@LEAVE_ROUTER.get("")
def list_leave(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(LeaveRequest)
    if user.role == UserRole.INTERN:
        query = query.where(LeaveRequest.intern_id == user.id)
    elif user.role == UserRole.SUPERVISOR:
        allowed = set(get_supervised_batch_ids(db, user.id))
        query = query.where(LeaveRequest.batch_id.in_(allowed))
    rows = db.execute(query.order_by(LeaveRequest.created_at.desc())).scalars().all()
    return [_leave_out(r) for r in rows]


@LEAVE_ROUTER.get("/{leave_id}", response_model=LeaveOut)
def get_leave(
    leave_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave = db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if user.role == UserRole.INTERN and leave.intern_id != user.id:
        raise HTTPException(status_code=403, detail="Not your leave request")
    return _leave_out(leave)


@LEAVE_ROUTER.post("/{leave_id}/decide", response_model=LeaveOut)
def decide_leave(
    leave_id: int,
    payload: LeaveDecision,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    leave = db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Leave already decided")
    leave.status = "approved" if payload.approve else "rejected"
    from datetime import datetime, timezone

    leave.decided_by = admin.id
    leave.decided_at = datetime.now(timezone.utc)
    record_audit(
        db, admin, "leave." + leave.status, "leave", leave_id,
        {"intern_id": leave.intern_id},
    )
    notify_many(
        db, [leave.intern_id], "leave_decision",
        "Leave request " + ("approved" if payload.approve else "rejected"),
        f"Your leave from {leave.start_date} to {leave.end_date} was {leave.status}.",
    )
    db.commit()
    db.refresh(leave)
    return _leave_out(leave)


def _leave_out(leave: LeaveRequest) -> LeaveOut:
    out = LeaveOut.model_validate(leave)
    out.intern_name = leave.intern.full_name if leave.intern else None
    return out
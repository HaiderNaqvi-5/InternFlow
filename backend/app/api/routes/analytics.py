from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, require_admin
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    Batch,
    BatchMembership,
    LeaveRequest,
    Submission,
    Task,
    User,
    UserRole,
)
from app.services.access import get_intern_active_batch, get_supervised_batch_ids
from app.utils.time import utcnow

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/intern")
def intern_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Intern analytics only")
    membership = get_intern_active_batch(db, user.id)
    if membership is None:
        return _empty_intern()
    batch_id = membership.batch_id

    tasks = db.execute(
        select(Task).where(Task.batch_id == batch_id)
    ).scalars().all()
    assigned = [t for t in tasks if t.scope.value == "batch" or t.assignee_id == user.id]
    submissions = db.execute(
        select(Submission).where(
            Submission.intern_id == user.id, Submission.batch_id == batch_id
        )
    ).scalars().all()

    done = [s for s in submissions if s.status.value in ("approved", "changes_requested", "rejected")]
    approved = [s for s in submissions if s.status.value == "approved"]
    late = [s for s in submissions if s.is_late]
    pending = [s for s in submissions if s.status.value == "pending"]

    scores = [
        r.score
        for s in submissions
        for r in s.reviews
    ]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    att_rows = db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.intern_id == user.id, AttendanceRecord.batch_id == batch_id
        )
    ).scalars().all()
    present = sum(1 for a in att_rows if a.check_in is not None)
    late_days = sum(1 for a in att_rows if a.late_status == "late")
    total_hours = round(sum(a.worked_hours or 0.0 for a in att_rows), 1)
    total_days = len(att_rows)
    attendance_rate = round(present / total_days * 100, 1) if total_days else 0.0

    total_effort_est = round(sum(t.estimated_effort_hours for t in assigned), 1)
    total_effort_actual = round(sum(s.actual_effort_hours or 0.0 for s in submissions), 1)

    upcoming = sorted(
        [t for t in assigned if not any(s.task_id == t.id for s in approved)],
        key=lambda t: t.deadline,
    )[:6]

    return {
        "tasks_total": len(assigned),
        "tasks_completed": len(done),
        "tasks_approved": len(approved),
        "tasks_pending": len(pending),
        "overdue_tasks": sum(
            1 for t in assigned if t.deadline < utcnow() and not any(
                s.task_id == t.id and s.status.value == "approved" for s in submissions
            )
        ),
        "late_submissions": len(late),
        "average_score": avg_score,
        "estimated_effort_hours": total_effort_est,
        "actual_effort_hours": total_effort_actual,
        "attendance_rate": attendance_rate,
        "present_days": present,
        "late_days": late_days,
        "total_hours": total_hours,
        "progress_percent": round(len(done) / len(assigned) * 100, 1) if assigned else 0.0,
        "upcoming_deadlines": [
            {"id": t.id, "title": t.title, "deadline": t.deadline.isoformat()} for t in upcoming
        ],
        "recent_feedback": [
            {
                "task_id": s.task_id,
                "task_title": s.task.title if s.task else "",
                "score": r.score,
                "feedback": r.feedback,
                "decision": r.decision.value,
            }
            for s in submissions
            for r in s.reviews
        ][-5:],
        "scores_over_time": [
            {"version": s.version, "score": (r.score if (r := _latest_review(s)) else None), "submitted_at": s.submitted_at.isoformat()}
            for s in submissions
            if _latest_review(s)
        ],
    }


def _latest_review(submission):
    reviews = sorted(submission.reviews, key=lambda r: r.reviewed_at)
    return reviews[-1] if reviews else None


def _empty_intern():
    return {
        "tasks_total": 0,
        "tasks_completed": 0,
        "tasks_approved": 0,
        "tasks_pending": 0,
        "overdue_tasks": 0,
        "late_submissions": 0,
        "average_score": 0.0,
        "estimated_effort_hours": 0.0,
        "actual_effort_hours": 0.0,
        "attendance_rate": 0.0,
        "present_days": 0,
        "late_days": 0,
        "total_hours": 0.0,
        "progress_percent": 0.0,
        "upcoming_deadlines": [],
        "recent_feedback": [],
        "scores_over_time": [],
    }


@router.get("/supervisor")
def supervisor_analytics(
    batch_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Supervisor analytics only")
    allowed = set(get_supervised_batch_ids(db, user.id))
    if batch_id is not None and (user.role == UserRole.SUPERVISOR and batch_id not in allowed):
        raise HTTPException(status_code=403, detail="Not assigned to this batch")

    scalar = _batch_stats(db, batch_id) if batch_id else _all_supervised_stats(db, user, allowed)
    return scalar


def _all_supervised_stats(db: Session, user: User, allowed: set[int]):
    batches = db.execute(
        select(Batch).where(Batch.supervisor_id == user.id)
    ).scalars().all()
    intern_ids: set[int] = set()
    active_interns = 0
    tasks_total = 0
    pending_reviews = 0
    overdue = 0
    late = 0
    scores: list[float] = []
    attendance_rows: list[AttendanceRecord] = []
    capacities = [b.capacity for b in batches if b.status.value == "active"]

    for b in batches:
        members = db.execute(
            select(BatchMembership).where(
                BatchMembership.batch_id == b.id, BatchMembership.is_active.is_(True)
            )
        ).scalars().all()
        active_interns_for_batch = len(members)
        if b.status.value == "active":
            active_interns += active_interns_for_batch
        intern_ids.update(m.intern_id for m in members)
        tasks = db.execute(select(Task).where(Task.batch_id == b.id)).scalars().all()
        tasks_total += len(tasks)
        overdue += sum(
            1 for t in tasks
            if t.deadline < utcnow()
            and _task_not_approved(db, t)
        )
        subs = db.execute(select(Submission).where(Submission.batch_id == b.id)).scalars().all()
        pending_reviews += sum(1 for s in subs if s.status.value == "pending")
        late += sum(1 for s in subs if s.is_late)
        for s in subs:
            scores.extend(r.score for r in s.reviews)
        attendance_rows.extend(
            db.execute(
                select(AttendanceRecord).where(AttendanceRecord.batch_id == b.id)
            ).scalars().all()
        )

    present = sum(1 for a in attendance_rows if a.check_in is not None)
    total_days = len(attendance_rows)
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    return {
        "batches_total": len(batches),
        "active_batches": sum(1 for b in batches if b.status.value == "active"),
        "active_interns": active_interns,
        "batch_capacity": min(capacities) if capacities else 0,
        "tasks_total": tasks_total,
        "pending_reviews": pending_reviews,
        "overdue_tasks": overdue,
        "late_submissions": late,
        "average_score": avg_score,
        "attendance_rate": round(present / total_days * 100, 1) if total_days else 0.0,
        "total_attendance_days": total_days,
        "total_hours": round(sum(a.worked_hours or 0.0 for a in attendance_rows), 1),
    }


def _batch_stats(db: Session, batch_id: int) -> dict:
    members = db.execute(
        select(BatchMembership).where(
            BatchMembership.batch_id == batch_id, BatchMembership.is_active.is_(True)
        )
    ).scalars().all()
    intern_ids = [m.intern_id for m in members]
    tasks = db.execute(select(Task).where(Task.batch_id == batch_id)).scalars().all()
    subs = db.execute(select(Submission).where(Submission.batch_id == batch_id)).scalars().all()
    scores = [r.score for s in subs for r in s.reviews]
    attendance_rows = db.execute(
        select(AttendanceRecord).where(AttendanceRecord.batch_id == batch_id)
    ).scalars().all()
    present = sum(1 for a in attendance_rows if a.check_in is not None)
    total_days = len(attendance_rows)
    batch = db.get(Batch, batch_id)
    return {
        "batch_id": batch_id,
        "batch_name": batch.name if batch else "",
        "interns_total": len(intern_ids),
        "capacity": batch.capacity if batch else 0,
        "tasks_total": len(tasks),
        "pending_reviews": sum(1 for s in subs if s.status.value == "pending"),
        "overdue_tasks": sum(1 for t in tasks if t.deadline < utcnow() and _task_not_approved(db, t)),
        "late_submissions": sum(1 for s in subs if s.is_late),
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "attendance_rate": round(present / total_days * 100, 1) if total_days else 0.0,
        "total_hours": round(sum(a.worked_hours or 0.0 for a in attendance_rows), 1),
        "total_attendance_days": total_days,
    }


def _task_not_approved(db: Session, task: Task) -> bool:
    return not db.execute(
        select(Submission).where(
            Submission.task_id == task.id, Submission.status == "approved"
        )
    ).first()


@router.get("/hr")
def hr_analytics(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.models.enums import BatchStatus

    active_batches = db.execute(
        select(Batch).where(Batch.status == BatchStatus.ACTIVE)
    ).scalars().all()
    active_interns = 0
    total_capacity = 0
    task_count = 0
    overdue = 0
    late = 0
    scores: list[float] = []
    attendance_rows: list[AttendanceRecord] = []
    leave_rows = db.execute(select(LeaveRequest)).scalars().all()

    for b in active_batches:
        intern_ids = db.execute(
            select(BatchMembership.intern_id).where(
                BatchMembership.batch_id == b.id, BatchMembership.is_active.is_(True)
            )
        ).scalars()
        active_interns += sum(1 for _ in intern_ids)
        total_capacity += b.capacity
        tasks = db.execute(select(Task).where(Task.batch_id == b.id)).scalars().all()
        task_count += len(tasks)
        overdue += sum(1 for t in tasks if t.deadline < utcnow() and _task_not_approved(db, t))
        subs = db.execute(select(Submission).where(Submission.batch_id == b.id)).scalars().all()
        late += sum(1 for s in subs if s.is_late)
        scores.extend(r.score for s in subs for r in s.reviews)
        attendance_rows.extend(
            db.execute(
                select(AttendanceRecord).where(AttendanceRecord.batch_id == b.id)
            ).scalars().all()
        )

    present = sum(1 for a in attendance_rows if a.check_in is not None)
    total_days = len(attendance_rows)
    approved_leaves = sum(1 for leave in leave_rows if leave.status == "approved")
    pending_leaves = sum(1 for leave in leave_rows if leave.status == "pending")

    # per-batch comparison
    batch_trends = []
    for b in active_batches:
        subs = db.execute(select(Submission).where(Submission.batch_id == b.id)).scalars().all()
        batch_scores = [r.score for s in subs for r in s.reviews]
        batch_trends.append(
            {
                "batch_id": b.id,
                "name": b.name,
                "interns": db.execute(
                    select(func.count()).select_from(BatchMembership).where(
                        BatchMembership.batch_id == b.id, BatchMembership.is_active.is_(True)
                    )
                ).scalar() or 0,
                "average_score": round(sum(batch_scores) / len(batch_scores), 2) if batch_scores else 0.0,
                "tasks": len(subs),
            }
        )

    return {
        "active_batches": len(active_batches),
        "active_interns": active_interns,
        "batches_capacity_total": total_capacity,
        "tasks_total": task_count,
        "overdue_tasks": overdue,
        "late_submissions": late,
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "attendance_rate": round(present / total_days * 100, 1) if total_days else 0.0,
        "total_hours": round(sum(a.worked_hours or 0.0 for a in attendance_rows), 1),
        "total_attendance_days": total_days,
        "leave_approved": approved_leaves,
        "leave_pending": pending_leaves,
        "batch_trends": batch_trends,
    }
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import (
    get_current_user,
    require_supervisor,
)
from app.db.session import get_db
from app.models import (
    Batch,
    Submission,
    SubmissionReview,
    SubmissionStatus,
    Task,
    TaskScope,
    User,
    UserRole,
)
from app.schemas.submission import (
    PaginatedSubmissions,
    ReviewCreate,
    ReviewOut,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionOut,
)
from app.services.access import (
    ensure_intern_in_batch,
    ensure_supervisor_manages,
    get_intern_active_batch,
)
from app.services.notifications import notify_many
from app.utils.storage import read_upload, storage

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _sub_out(db: Session, sub: Submission) -> SubmissionOut:
    out = SubmissionOut.model_validate(sub)
    task = db.get(Task, sub.task_id)
    out.task_title = task.title if task else None
    out.reviews = [
        ReviewOut.model_validate(r) for r in sorted(sub.reviews, key=lambda r: r.reviewed_at)
    ]
    return out


def _scope_submissions_query(db: Session, user: User):
    query = select(Submission)
    if user.role == UserRole.INTERN:
        return query.where(Submission.intern_id == user.id)
    if user.role == UserRole.SUPERVISOR:
        return query.where(
            Submission.batch_id.in_(
                select(Batch.id).where(Batch.supervisor_id == user.id)
            )
        )
    return query


@router.get("", response_model=PaginatedSubmissions)
def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    task_id: int | None = None,
    intern_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _scope_submissions_query(db, user)
    if task_id:
        query = query.where(Submission.task_id == task_id)
    if intern_id:
        if user.role == UserRole.INTERN and intern_id != user.id:
            raise HTTPException(status_code=403, detail="Not permitted")
        query = query.where(Submission.intern_id == intern_id)
    if status_filter:
        query = query.where(Submission.status == SubmissionStatus(status_filter))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    subs = db.execute(
        query.order_by(Submission.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    items = [_sub_out(db, s) for s in subs]
    return PaginatedSubmissions(items=items, total=total, page=page, page_size=page_size)


@router.get("/my")
def my_submissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns have personal submissions")
    subs = db.execute(
        select(Submission).where(Submission.intern_id == user.id).order_by(Submission.submitted_at.desc())
    ).scalars().all()
    return [_sub_out(db, s) for s in subs]


@router.post("/{task_id}", response_model=SubmissionOut)
async def submit_work(
    task_id: int,
    payload: SubmissionCreate,
    intern: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _create_submission(db, intern, task_id, payload)


@router.post("/{task_id}/file", response_model=SubmissionOut)
async def submit_work_with_file(
    task_id: int,
    file: UploadFile = File(...),
    github_url: str | None = Form(None),
    live_url: str | None = Form(None),
    notes: str | None = Form(None),
    actual_effort_hours: float | None = Form(None),
    late_reason: str | None = Form(None),
    intern: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = SubmissionCreate(
        github_url=github_url,
        live_url=live_url,
        notes=notes,
        actual_effort_hours=actual_effort_hours,
        late_reason=late_reason,
    )
    return await _create_submission(db, intern, task_id, payload, file=file)


async def _create_submission(
    db: Session,
    intern: User,
    task_id: int,
    payload: SubmissionCreate,
    file: UploadFile | None = None,
) -> SubmissionOut:
    if intern.role != UserRole.INTERN:
        raise HTTPException(status_code=403, detail="Only interns can submit work")
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_archived:
        raise HTTPException(status_code=403, detail="Cannot submit to an archived task")

    membership = get_intern_active_batch(db, intern.id)
    if membership is None or membership.batch_id != task.batch_id:
        raise HTTPException(status_code=403, detail="Not a member of the task's batch")
    ensure_intern_in_batch(db, intern.id, task.batch_id)
    if task.scope == TaskScope.INDIVIDUAL and task.assignee_id != intern.id:
        raise HTTPException(status_code=403, detail="This task is assigned to another intern")

    # If a previous submission has been approved, no further resubmission
    existing = db.execute(
        select(Submission).where(
            Submission.task_id == task_id, Submission.intern_id == intern.id
        )
    ).scalars().all()
    approved = [s for s in existing if s.status == SubmissionStatus.APPROVED]
    if approved:
        raise HTTPException(status_code=400, detail="Task already approved")

    next_version = max((s.version for s in existing), default=0) + 1
    allow_resubmit = not existing or existing[-1].status in (
        SubmissionStatus.CHANGES_REQUESTED,
        SubmissionStatus.REJECTED,
    )
    if existing and not allow_resubmit:
        raise HTTPException(
            status_code=400,
            detail="Resubmission allowed only after Changes Requested or Rejected",
        )

    from app.models import DeadlineExtension
    from app.utils.time import ensure_utc, utcnow

    now = utcnow()
    effective_deadline = ensure_utc(task.deadline)

    ext = db.execute(
        select(DeadlineExtension)
        .where(
            DeadlineExtension.task_id == task_id,
            DeadlineExtension.intern_id == intern.id,
        )
        .order_by(DeadlineExtension.created_at.desc())
    ).scalars().first()
    if ext:
        effective_deadline = ensure_utc(ext.new_deadline)

    is_late = now > effective_deadline

    data = payload.model_dump()
    zip_key = None
    filename = None
    if file:
        content = await read_upload(file)
        zip_key = storage.new_key("submissions", file.filename or "submission.zip")
        storage.save_bytes(zip_key, content)
        filename = file.filename

    submission = Submission(
        task_id=task_id,
        intern_id=intern.id,
        batch_id=task.batch_id,
        version=next_version,
        github_url=data.get("github_url"),
        live_url=data.get("live_url"),
        zip_file_key=zip_key,
        filename=filename,
        notes=data.get("notes"),
        actual_effort_hours=data.get("actual_effort_hours"),
        submitted_at=now,
        is_late=is_late,
        late_reason=data.get("late_reason"),
        status=SubmissionStatus.PENDING,
    )
    db.add(submission)
    db.flush()

    record_audit(
        db, intern, "submissions.create", "submission", submission.id,
        {"task_id": task_id, "version": next_version, "is_late": is_late},
    )
    notify_many(
        db, [task.created_by], "submission_submitted",
        "New submission to review",
        f"{intern.full_name} submitted '{task.title}' (v{next_version}).",
        link=f"/tasks/{task_id}",
        actor_id=intern.id,
    )
    db.commit()
    db.refresh(submission)
    return _sub_out(db, submission)


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _authorize_submission(db, user, sub)
    base = SubmissionOut.model_validate(sub).model_dump(exclude={"reviews"})
    detail = SubmissionDetail(**base)
    task = db.get(Task, sub.task_id)
    detail.task_title = task.title if task else None
    detail.reviews = [
        ReviewOut.model_validate(r) for r in sorted(sub.reviews, key=lambda r: r.reviewed_at)
    ]
    return detail


def _authorize_submission(db: Session, user: User, sub: Submission) -> None:
    if user.role == UserRole.INTERN:
        if sub.intern_id != user.id:
            raise HTTPException(status_code=403, detail="Not your submission")
        return
    if user.role == UserRole.SUPERVISOR:
        batch = db.get(Batch, sub.batch_id)
        if batch and batch.supervisor_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Not the assigned supervisor")
    return


@router.get("/{submission_id}/download")
def download_submission_file(
    submission_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _authorize_submission(db, user, sub)
    if not sub.zip_file_key:
        raise HTTPException(status_code=404, detail="No file attached to this submission")
    from fastapi.responses import Response

    content = storage.read_bytes(sub.zip_file_key)
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sub.filename or "submission.zip"}"'},
    )


# ---------------- Reviews (supervisor only) ----------------

@router.post("/{submission_id}/review", response_model=ReviewOut)
def review_submission(
    submission_id: int,
    payload: ReviewCreate,
    supervisor: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    ensure_supervisor_manages(db, supervisor, sub.batch_id)

    from app.models.enums import ReviewDecision, TaskStatus

    decision = ReviewDecision(payload.decision)
    review = SubmissionReview(
        submission_id=submission_id,
        supervisor_id=supervisor.id,
        decision=decision,
        score=payload.score,
        feedback=payload.feedback,
    )
    db.add(review)

    if decision == ReviewDecision.APPROVED:
        sub.status = SubmissionStatus.APPROVED
        task = db.get(Task, sub.task_id)
        if task:
            task.status = TaskStatus.REVIEWED
    elif decision == ReviewDecision.CHANGES_REQUESTED:
        sub.status = SubmissionStatus.CHANGES_REQUESTED
        task = db.get(Task, sub.task_id)
        if task:
            task.status = TaskStatus.PENDING_RESUBMISSION
    else:
        sub.status = SubmissionStatus.REJECTED
        task = db.get(Task, sub.task_id)
        if task:
            task.status = TaskStatus.PENDING_RESUBMISSION

    record_audit(
        db, supervisor, "submissions.review", "submission", submission_id,
        {"decision": decision.value, "score": payload.score},
    )
    task = db.get(Task, sub.task_id)
    notify_many(
        db, [sub.intern_id], "review_result",
        "Your submission was reviewed",
        f"'{task.title if task else 'Task'}' → {decision.value.replace('_', ' ').title()} ({payload.score}/10)",
        link=f"/tasks/{sub.task_id}",
        actor_id=supervisor.id,
    )
    db.commit()
    db.refresh(review)
    return ReviewOut.model_validate(review)


@router.get("/{submission_id}/reviews")
def list_reviews(
    submission_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _authorize_submission(db, user, sub)
    reviews = db.execute(
        select(SubmissionReview)
        .where(SubmissionReview.submission_id == submission_id)
        .order_by(SubmissionReview.reviewed_at)
    ).scalars().all()
    result = []
    for r in reviews:
        row = ReviewOut.model_validate(r).model_dump()
        supervisor = db.get(User, r.supervisor_id)
        row["supervisor_name"] = supervisor.full_name if supervisor else None
        result.append(row)
    return result
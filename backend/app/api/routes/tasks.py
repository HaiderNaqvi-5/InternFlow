from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import (
    get_current_user,
    require_supervisor,
    require_supervisor_or_admin,
)
from app.db.session import get_db
from app.models import (
    Batch,
    BatchMembership,
    DeadlineExtension,
    Submission,
    Task,
    TaskAttachment,
    TaskCategory,
    TaskPriority,
    TaskScope,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.task import (
    ExtensionCreate,
    ExtensionOut,
    PaginatedTasks,
    TaskAttachmentOut,
    TaskCreate,
    TaskDetail,
    TaskOut,
    TaskUpdate,
)
from app.services.access import (
    ensure_batch_active,
    ensure_supervisor_manages,
    get_intern_active_batch,
)
from app.services.notifications import notify_many
from app.utils.storage import read_upload, storage

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_out(db: Session, task: Task, user: User) -> TaskOut:
    out = TaskOut.model_validate(task)
    out.batch_name = task.batch.name if task.batch else None
    out.assignee_name = task.assignee.full_name if task.assignee else None
    out.creator_name = task.creator.full_name if task.creator else None
    if user.role == UserRole.INTERN:
        sub = db.execute(
            select(Submission)
            .where(Submission.task_id == task.id, Submission.intern_id == user.id)
            .order_by(Submission.version.desc())
        ).scalars().first()
        if sub:
            out.has_submission = True
            out.my_submission_status = sub.status.value
    return out


def _scope_tasks_query(db: Session, user: User):
    query = select(Task)
    if user.role == UserRole.INTERN:
        batch_id = get_intern_active_batch(db, user.id)
        if batch_id is None:
            return query.where(Task.id == -1)
        return query.where(
            ((Task.batch_id == batch_id.batch_id) & (Task.scope == TaskScope.BATCH))
            | ((Task.assignee_id == user.id) & (Task.scope == TaskScope.INDIVIDUAL))
        )
    if user.role == UserRole.SUPERVISOR:
        return query.where(
            Task.batch_id.in_(
                select(Batch.id).where(Batch.supervisor_id == user.id)
            )
        )
    return query


@router.get("", response_model=PaginatedTasks)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    batch_id: int | None = None,
    category: str | None = None,
    priority: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    scope: str | None = None,
    search: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _scope_tasks_query(db, user)
    if batch_id is not None:
        query = query.where(Task.batch_id == batch_id)
    if category:
        query = query.where(Task.category == TaskCategory(category))
    if priority:
        query = query.where(Task.priority == TaskPriority(priority))
    if status_filter:
        query = query.where(Task.status == TaskStatus(status_filter))
    if scope:
        query = query.where(Task.scope == TaskScope(scope))
    if search:
        like = f"%{search.strip()}%"
        query = query.where(Task.title.ilike(like))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    tasks = db.execute(
        query.order_by(Task.deadline.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    items = [_task_out(db, t, user) for t in tasks]
    return PaginatedTasks(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TaskOut)
def create_task(
    payload: TaskCreate,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    batch = db.get(Batch, payload.batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    ensure_batch_active(batch)

    # Only the assigned supervisor (or admin) may create tasks for a batch
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, payload.batch_id)

    if payload.scope == TaskScope.INDIVIDUAL.value and not payload.assignee_id:
        raise HTTPException(status_code=400, detail="Individual tasks require an assignee")
    if payload.assignee_id:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.role != UserRole.INTERN:
            raise HTTPException(status_code=400, detail="Assignee must be an intern")
        membership = db.execute(
            select(BatchMembership).where(
                BatchMembership.intern_id == payload.assignee_id,
                BatchMembership.batch_id == payload.batch_id,
                BatchMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=400, detail="Assignee is not an active member of this batch"
            )

    task = Task(
        title=payload.title,
        description=payload.description,
        scope=TaskScope(payload.scope),
        batch_id=payload.batch_id,
        assignee_id=payload.assignee_id,
        created_by=supervisor.id,
        category=TaskCategory(payload.category),
        priority=TaskPriority(payload.priority),
        deadline=payload.deadline,
        estimated_effort_hours=payload.estimated_effort_hours,
        status=TaskStatus.OPEN,
    )
    db.add(task)
    db.flush()
    record_audit(db, supervisor, "tasks.create", "task", task.id)

    # Notify interns (batch-wide) or the single assignee
    if task.scope == TaskScope.BATCH:
        intern_ids = [
            r[0]
            for r in db.execute(
                select(BatchMembership.intern_id).where(
                    BatchMembership.batch_id == task.batch_id,
                    BatchMembership.is_active.is_(True),
                )
            )
        ]
        notify_many(
            db, intern_ids, "task_assigned",
            f"New task: {task.title}",
            f"A new {task.category.value} task is assigned to your batch.",
            link=f"/tasks/{task.id}",
            actor_id=supervisor.id,
        )
    elif task.assignee_id:
        notify_many(
            db, [task.assignee_id], "task_assigned",
            f"New task: {task.title}",
            "A new task has been assigned to you.",
            link=f"/tasks/{task.id}",
            actor_id=supervisor.id,
        )
    db.commit()
    db.refresh(task)
    return _task_out(db, task, supervisor)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _authorize_task(db, user, task)
    base = _task_out(db, task, user)
    detail = TaskDetail(**base.model_dump())
    detail.attachments = [
        TaskAttachmentOut.model_validate(a) for a in task.attachments
    ]
    detail.effective_deadline = _effective_deadline(db, task, user, task_id)
    return detail


def _effective_deadline(db: Session, task: Task, user: User, task_id: int) -> datetime | None:
    if user.role == UserRole.INTERN:
        ext = db.execute(
            select(DeadlineExtension)
            .where(
                DeadlineExtension.task_id == task_id,
                DeadlineExtension.intern_id == user.id,
            )
            .order_by(DeadlineExtension.created_at.desc())
        ).scalars().first()
        if ext:
            return ext.new_deadline
    return task.deadline


def _authorize_task(db: Session, user: User, task: Task) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        batch = db.get(Batch, task.batch_id)
        if batch and batch.supervisor_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Not the assigned supervisor")
    if user.role == UserRole.INTERN:
        membership = get_intern_active_batch(db, user.id)
        if membership is None:
            raise HTTPException(status_code=403, detail="Not assigned to a batch")
        if task.scope == TaskScope.BATCH:
            if task.batch_id == membership.batch_id:
                return
            raise HTTPException(status_code=403, detail="Not permitted to view this task")
        if task.scope == TaskScope.INDIVIDUAL:
            if task.assignee_id == user.id:
                return
            raise HTTPException(status_code=403, detail="Not permitted to view this task")
        raise HTTPException(status_code=403, detail="Not permitted to view this task")


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    supervisor: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_supervisor_manages(db, supervisor, task.batch_id)
    ensure_batch_active(task.batch)
    if task.is_archived:
        raise HTTPException(status_code=403, detail="Archived tasks are read-only")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(task, k, v)
    record_audit(db, supervisor, "tasks.update", "task", task_id)
    db.commit()
    db.refresh(task)
    return _task_out(db, task, supervisor)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    supervisor: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_supervisor_manages(db, supervisor, task.batch_id)
    if task.submissions:
        # official record path: archive instead of hard delete
        task.is_archived = True
        record_audit(db, supervisor, "tasks.archive", "task", task_id, {"via": "delete"})
        db.commit()
        return {"message": "Task archived (has submission history)"}
    for att in task.attachments:
        storage.delete(att.storage_key)
    db.delete(task)
    record_audit(db, supervisor, "tasks.delete", "task", task_id)
    db.commit()
    return {"message": "Task deleted"}


@router.post("/{task_id}/attachments")
async def add_attachment(
    task_id: int,
    file: UploadFile,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, task.batch_id)
    ensure_batch_active(task.batch)
    content = await read_upload(file)
    key = storage.new_key("task_attachments", file.filename or "attachment")
    storage.save_bytes(key, content)
    att = TaskAttachment(
        task_id=task_id,
        filename=file.filename or "attachment",
        storage_key=key,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(att)
    db.commit()
    return TaskAttachmentOut.model_validate(att)


@router.get("/{task_id}/attachments/{attachment_id}/download")
def download_attachment(
    task_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _authorize_task(db, user, task)
    att = db.get(TaskAttachment, attachment_id)
    if att is None or att.task_id != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    from fastapi.responses import Response

    content = storage.read_bytes(att.storage_key)
    return Response(
        content,
        media_type=att.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


# ---------------- Deadline extensions (supervisor only) ----------------

@router.post("/{task_id}/extensions", response_model=ExtensionOut)
def grant_extension(
    task_id: int,
    payload: ExtensionCreate,
    supervisor: User = Depends(require_supervisor),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_supervisor_manages(db, supervisor, task.batch_id)
    ensure_batch_active(task.batch)
    if task.is_archived:
        raise HTTPException(status_code=403, detail="Archived tasks are read-only")
    from app.models import BatchMembership

    is_member = db.execute(
        select(BatchMembership).where(
            BatchMembership.intern_id == payload.intern_id,
            BatchMembership.batch_id == task.batch_id,
            BatchMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if is_member is None:
        raise HTTPException(
            status_code=400, detail="Intern is not an active member of this batch"
        )
    extension = DeadlineExtension(
        task_id=task_id,
        intern_id=payload.intern_id,
        original_deadline=task.deadline,
        new_deadline=payload.new_deadline,
        reason=payload.reason,
        granted_by=supervisor.id,
    )
    db.add(extension)
    db.flush()
    record_audit(db, supervisor, "tasks.extension", "task", task_id, {"to": payload.intern_id})
    notify_many(
        db, [payload.intern_id], "deadline_extension",
        "Deadline extension granted",
        f"Your deadline for '{task.title}' was extended to {payload.new_deadline:%b %d, %Y %H:%M}.",
        link=f"/tasks/{task_id}",
        actor_id=supervisor.id,
    )
    db.commit()
    db.refresh(extension)
    return ExtensionOut.model_validate(extension)


@router.get("/{task_id}/extensions")
def list_extensions(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _authorize_task(db, user, task)
    rows = db.execute(
        select(DeadlineExtension)
        .where(DeadlineExtension.task_id == task_id)
        .order_by(DeadlineExtension.created_at.desc())
    ).scalars().all()
    return [ExtensionOut.model_validate(e) for e in rows]
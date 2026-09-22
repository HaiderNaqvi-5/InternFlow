
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import (
    get_current_user,
    require_supervisor_or_admin,
)
from app.db.session import get_db
from app.models import (
    Announcement,
    AnnouncementAttachment,
    Batch,
    BatchEvent,
    CommentMention,
    Task,
    TaskComment,
    User,
    UserRole,
)
from app.schemas.collab import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    BatchEventCreate,
    BatchEventOut,
    CommentCreate,
    CommentOut,
    CommentUpdate,
)
from app.services.access import (
    ensure_batch_active,
    ensure_supervisor_manages,
    get_intern_active_batch,
)
from app.services.notifications import notify_many

router = APIRouter(tags=["discussions"])

COMMENT_PREFIX = "/tasks/{task_id}/comments"
ANNOUNCEMENT_PREFIX = "/announcements"
EVENT_PREFIX = "/events"
CALENDAR_PREFIX = "/calendar"


def _comment_out(db: Session, comment: TaskComment) -> CommentOut:
    out = CommentOut(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        content=comment.content,
        is_edited=comment.is_edited,
        is_deleted=comment.is_deleted,
        is_pinned=comment.is_pinned,
        mentions=[m.mentioned_user_id for m in comment.mentions],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )
    author = db.get(User, comment.author_id)
    out.author_name = author.full_name if author else None
    return out


# ---------------- Comments ----------------

@router.get("/tasks/{task_id}/comments")
def list_comments(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.api.routes.tasks import _authorize_task

    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _authorize_task(db, user, task)
    rows = db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
    ).scalars().all()
    return [_comment_out(db, c) for c in rows]


@router.post(COMMENT_PREFIX, response_model=CommentOut)
def create_comment(
    task_id: int,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.api.routes.tasks import _authorize_task

    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _authorize_task(db, user, task)
    comment = TaskComment(task_id=task_id, author_id=user.id, content=payload.content)
    db.add(comment)
    db.flush()

    mentioned_ids: list[int] = []
    for uid in set(payload.mentions or []):
        target = db.get(User, uid)
        if target is None:
            continue
        db.add(CommentMention(comment_id=comment.id, mentioned_user_id=uid))
        mentioned_ids.append(uid)
    if mentioned_ids:
        notify_many(
            db, mentioned_ids, "mention",
            f"{user.full_name} mentioned you on '{task.title}'",
            payload.content[:200],
            link=f"/tasks/{task_id}",
            actor_id=user.id,
        )

    # notify other batch viewers of new comment (not self, not mentioned)
    viewers = _task_viewer_ids(db, task, user.id)
    others = [v for v in viewers if v not in mentioned_ids]
    if others:
        notify_many(
            db, others, "comment",
            f"New comment on '{task.title}'",
            payload.content[:200],
            link=f"/tasks/{task_id}",
            actor_id=user.id,
        )
    db.commit()
    db.refresh(comment)
    return _comment_out(db, comment)


def _task_viewer_ids(db: Session, task: Task, exclude_id: int) -> list[int]:
    from app.models import TaskScope
    from app.services.notifications import get_batch_intern_ids

    if task.scope == TaskScope.INDIVIDUAL and task.assignee_id:
        ids = {task.assignee_id}
    else:
        ids = set(get_batch_intern_ids(db, task.batch_id))
    batch = db.get(Batch, task.batch_id)
    if batch and batch.supervisor_id:
        ids.add(batch.supervisor_id)
    ids.discard(exclude_id)
    return list(ids)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def edit_comment(
    comment_id: int,
    payload: CommentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(TaskComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit")
    if comment.is_deleted:
        raise HTTPException(status_code=400, detail="Comment was deleted")
    comment.content = payload.content
    comment.is_edited = True
    db.commit()
    db.refresh(comment)
    return _comment_out(db, comment)


@router.delete("/comments/{comment_id}", response_model=CommentOut)
def delete_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(TaskComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can delete")
    comment.is_deleted = True
    comment.content = "This comment was deleted"
    db.commit()
    db.refresh(comment)
    return _comment_out(db, comment)


@router.post("/comments/{comment_id}/pin", response_model=CommentOut)
def pin_comment(
    comment_id: int,
    pin: bool = True,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    comment = db.get(TaskComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    task = db.get(Task, comment.task_id)
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, task.batch_id)
    comment.is_pinned = pin
    db.commit()
    db.refresh(comment)
    return _comment_out(db, comment)


# ---------------- Announcements ----------------

def _announcement_out(ann: Announcement) -> AnnouncementOut:
    out = AnnouncementOut.model_validate(ann)
    out.author_name = ann.author.full_name if ann.author else None
    out.batch_name = ann.batch.name if ann.batch else None
    out.attachments = [
        {
            "id": a.id,
            "filename": a.filename,
            "storage_key": a.storage_key,
            "content_type": a.content_type,
            "size_bytes": a.size_bytes,
        }
        for a in ann.attachments
    ]
    return out


@router.get(ANNOUNCEMENT_PREFIX)
def list_announcements(
    batch_id: int | None = None,
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Announcement)
    if user.role == UserRole.INTERN:
        membership = get_intern_active_batch(db, user.id)
        query = query.where(Announcement.batch_id == membership.batch_id if membership else Announcement.id == -1)
    elif user.role == UserRole.SUPERVISOR:
        from app.services.access import get_supervised_batch_ids

        allowed = set(get_supervised_batch_ids(db, user.id))
        if batch_id is not None and batch_id not in allowed:
            raise HTTPException(status_code=403, detail="Not assigned to this batch")
        if batch_id is not None:
            query = query.where(Announcement.batch_id == batch_id)
        else:
            query = query.where(Announcement.batch_id.in_(allowed) if allowed else Announcement.id == -1)
    elif batch_id is not None:
        query = query.where(Announcement.batch_id == batch_id)
    if not include_archived:
        query = query.where(Announcement.is_archived.is_(False))
    rows = db.execute(query.order_by(Announcement.created_at.desc())).scalars().all()
    return [_announcement_out(a) for a in rows]


@router.post(ANNOUNCEMENT_PREFIX, response_model=AnnouncementOut)
def create_announcement(
    payload: AnnouncementCreate,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, payload.batch_id)
    batch = db.get(Batch, payload.batch_id)
    ensure_batch_active(batch)
    ann = Announcement(
        batch_id=payload.batch_id,
        author_id=supervisor.id,
        title=payload.title,
        content=payload.content,
    )
    db.add(ann)
    db.flush()
    record_audit(db, supervisor, "announcements.create", "announcement", ann.id)
    from app.services.notifications import get_batch_intern_ids

    interns = get_batch_intern_ids(db, payload.batch_id)
    notify_many(
        db, interns, "announcement",
        f"Announcement: {payload.title}",
        (payload.content or "")[:200],
        link="/announcements",
        actor_id=supervisor.id,
    )
    db.commit()
    db.refresh(ann)
    return _announcement_out(ann)


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    ann = db.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, ann.batch_id)
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(ann, k, v)
    if "is_archived" in updates and updates["is_archived"]:
        record_audit(db, supervisor, "announcements.archive", "announcement", announcement_id)
    db.commit()
    db.refresh(ann)
    return _announcement_out(ann)


@router.post("/announcements/{announcement_id}/attachments")
async def add_announcement_attachment(
    announcement_id: int,
    file: UploadFile,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    ann = db.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, ann.batch_id)
    from app.utils.storage import read_upload, storage

    content = await read_upload(file)
    key = storage.new_key("uploads", file.filename or "attachment")
    storage.save_bytes(key, content)
    att = AnnouncementAttachment(
        announcement_id=announcement_id,
        filename=file.filename or "attachment",
        storage_key=key,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(att)
    db.commit()
    db.refresh(ann)
    return _announcement_out(ann)


# ---------------- Batch events / calendar ----------------

@router.get(EVENT_PREFIX)
def list_events(
    batch_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(BatchEvent)
    if user.role == UserRole.INTERN:
        membership = get_intern_active_batch(db, user.id)
        query = query.where(BatchEvent.batch_id == membership.batch_id if membership else BatchEvent.id == -1)
    elif user.role == UserRole.SUPERVISOR:
        from app.services.access import get_supervised_batch_ids

        allowed = set(get_supervised_batch_ids(db, user.id))
        if batch_id is not None and batch_id not in allowed:
            raise HTTPException(status_code=403, detail="Not assigned to this batch")
        if batch_id is not None:
            query = query.where(BatchEvent.batch_id == batch_id)
        else:
            query = query.where(BatchEvent.batch_id.in_(allowed) if allowed else BatchEvent.id == -1)
    elif batch_id is not None:
        query = query.where(BatchEvent.batch_id == batch_id)
    rows = db.execute(query.order_by(BatchEvent.starts_at.asc())).scalars().all()
    return [_event_out(e) for e in rows]


def _event_out(event: BatchEvent) -> BatchEventOut:
    return BatchEventOut.model_validate(event)


@router.post(EVENT_PREFIX, response_model=BatchEventOut)
def create_event(
    payload: BatchEventCreate,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, payload.batch_id)
    batch = db.get(Batch, payload.batch_id)
    ensure_batch_active(batch)
    event = BatchEvent(
        batch_id=payload.batch_id,
        title=payload.title,
        event_type=payload.event_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        location=payload.location,
        details=payload.details,
        created_by=supervisor.id,
    )
    db.add(event)
    db.flush()
    record_audit(db, supervisor, "events.create", "event", event.id)
    from app.services.notifications import get_batch_intern_ids
    from app.services.notifications import notify_many as nm

    interns = get_batch_intern_ids(db, payload.batch_id)
    nm(
        db, interns, "batch_event",
        f"Event: {payload.title}",
        f"{payload.event_type.replace('_', ' ').title()} scheduled for {payload.starts_at:%b %d, %Y %H:%M}.",
        link="/calendar",
        actor_id=supervisor.id,
    )
    db.commit()
    db.refresh(event)
    return _event_out(event)


@router.delete(EVENT_PREFIX + "/{event_id}")
def delete_event(
    event_id: int,
    supervisor: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    event = db.get(BatchEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if supervisor.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, supervisor, event.batch_id)
    db.delete(event)
    record_audit(db, supervisor, "events.delete", "event", event_id)
    db.commit()
    return {"message": "Event deleted"}


@router.get(CALENDAR_PREFIX)
def calendar(
    from_date: str | None = None,
    to_date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Combined read-only calendar: tasks, events, and (for interns) leave."""
    events = []
    if user.role == UserRole.INTERN:
        from app.models import LeaveRequest

        membership = get_intern_active_batch(db, user.id)
        if membership:
            tasks = db.execute(
                select(Task).where(Task.batch_id == membership.batch_id)
            ).scalars().all()
            for t in tasks:
                if t.assignee_id and t.assignee_id != user.id:
                    continue
                events.append(
                    {
                        "type": "task",
                        "title": t.title,
                        "start": t.deadline.isoformat(),
                        "end": None,
                        "link": f"/tasks/{t.id}",
                    }
                )
            batch_events = db.execute(
                select(BatchEvent).where(BatchEvent.batch_id == membership.batch_id)
            ).scalars().all()
            for e in batch_events:
                events.append(
                    {
                        "type": "event",
                        "title": e.title,
                        "start": e.starts_at.isoformat(),
                        "end": e.ends_at.isoformat() if e.ends_at else None,
                        "link": "/calendar",
                    }
                )
            leaves = db.execute(
                select(LeaveRequest).where(LeaveRequest.intern_id == user.id)
            ).scalars().all()
            for leave in leaves:
                events.append(
                    {
                        "type": "leave",
                        "title": f"Leave: {leave.reason}",
                        "start": leave.start_date.isoformat(),
                        "end": leave.end_date.isoformat(),
                        "link": "/attendance",
                        "status": leave.status,
                    }
                )
    else:
        query = select(BatchEvent)
        if user.role == UserRole.SUPERVISOR:
            from app.services.access import get_supervised_batch_ids

            allowed = set(get_supervised_batch_ids(db, user.id))
            query = query.where(BatchEvent.batch_id.in_(allowed) if allowed else BatchEvent.id == -1)
        rows = db.execute(query).scalars().all()
        for e in rows:
            events.append(
                {
                    "type": "event",
                    "title": e.title,
                    "start": e.starts_at.isoformat(),
                    "end": e.ends_at.isoformat() if e.ends_at else None,
                    "link": "/calendar",
                }
            )
    events.sort(key=lambda e: e["start"])
    return events
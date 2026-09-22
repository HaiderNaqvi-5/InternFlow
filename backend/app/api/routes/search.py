from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.db.session import get_db
from app.models import (
    Announcement,
    Batch,
    BatchMembership,
    Submission,
    Task,
    User,
    UserRole,
)
from app.schemas.notification import SearchResults, SearchSuggestion

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResults)
def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    term = q.strip()
    results: list[SearchSuggestion] = []
    if not term:
        return SearchResults(query=q, results=[])

    like = f"%{term}%"

    # Intern: own tasks, submissions, announcements, feedback
    if user.role == UserRole.INTERN:
        membership = db.execute(
            select(BatchMembership).where(
                BatchMembership.intern_id == user.id,
                BatchMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        batch_id = membership.batch_id if membership else None
        from app.models import TaskScope

        task_scope = (
            ((Task.batch_id == batch_id) & (Task.scope == TaskScope.BATCH))
            | ((Task.assignee_id == user.id) & (Task.scope == TaskScope.INDIVIDUAL))
            if batch_id
            else (Task.id == -1)
        )
        tasks = db.execute(
            select(Task).where(
                Task.title.ilike(like),
                task_scope,
            ).limit(limit)
        ).scalars().all()
        for t in tasks:
            results.append(SearchSuggestion(type="task", id=t.id, label=t.title, subtitle="Task", link=f"/tasks/{t.id}"))
        anns = db.execute(
            select(Announcement).where(
                Announcement.title.ilike(like),
                Announcement.batch_id == batch_id if batch_id else Announcement.id == -1,
            ).limit(limit)
        ).scalars().all()
        for a in anns:
            results.append(SearchSuggestion(type="announcement", id=a.id, label=a.title, subtitle="Announcement", link="/announcements"))
        subs = db.execute(
            select(Submission).where(
                Submission.intern_id == user.id,
                Submission.notes.ilike(like),
            ).limit(limit)
        ).scalars().all()
        for s in subs:
            results.append(SearchSuggestion(type="submission", id=s.id, label=f"Submission v{s.version}", subtitle="Submission", link=f"/tasks/{s.task_id}"))

    # Supervisor: assigned batches, interns, tasks, submissions, announcements
    elif user.role == UserRole.SUPERVISOR:
        from app.services.access import get_supervised_batch_ids

        batch_ids = get_supervised_batch_ids(db, user.id)
        batches = db.execute(
            select(Batch).where(
                Batch.supervisor_id == user.id, Batch.name.ilike(like)
            ).limit(limit)
        ).scalars().all()
        for b in batches:
            results.append(SearchSuggestion(type="batch", id=b.id, label=b.name, subtitle="Batch", link=f"/batches/{b.id}"))
        tasks = db.execute(
            select(Task).where(
                Task.batch_id.in_(batch_ids) if batch_ids else Task.id == -1,
                Task.title.ilike(like),
            ).limit(limit)
        ).scalars().all()
        for t in tasks:
            results.append(SearchSuggestion(type="task", id=t.id, label=t.title, subtitle="Task", link=f"/tasks/{t.id}"))
        intern_ids = [
            r[0]
            for r in db.execute(
                select(BatchMembership.intern_id).where(
                    BatchMembership.batch_id.in_(batch_ids),
                    BatchMembership.is_active.is_(True),
                )
            )
        ]
        interns = db.execute(
            select(User).where(
                User.id.in_(intern_ids) if intern_ids else User.id == -1,
                User.full_name.ilike(like),
            ).limit(limit)
        ).scalars().all()
        for u in interns:
            results.append(SearchSuggestion(type="intern", id=u.id, label=u.full_name, subtitle=u.email, link=f"/users/{u.id}"))

    # Admin: batches, interns, supervisors, reports, evaluations
    else:
        batches = db.execute(
            select(Batch).where(Batch.name.ilike(like)).limit(limit)
        ).scalars().all()
        for b in batches:
            results.append(SearchSuggestion(type="batch", id=b.id, label=b.name, subtitle="Batch", link=f"/batches/{b.id}"))
        users = db.execute(
            select(User).where(User.full_name.ilike(like)).limit(limit)
        ).scalars().all()
        for u in users:
            link = f"/users/{u.id}"
            results.append(SearchSuggestion(type="user", id=u.id, label=u.full_name, subtitle=f"{u.email} · {u.role.value}", link=link))
        tasks = db.execute(
            select(Task).where(Task.title.ilike(like)).limit(limit)
        ).scalars().all()
        for t in tasks:
            results.append(SearchSuggestion(type="task", id=t.id, label=t.title, subtitle="Task", link=f"/tasks/{t.id}"))

    return SearchResults(query=q, results=results[:limit])
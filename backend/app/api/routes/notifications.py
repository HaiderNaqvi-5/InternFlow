from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.db.session import get_db
from app.models import Notification, NotificationPreference, PushSubscription, User
from app.schemas.notification import (
    NotificationMarkRead,
    NotificationOut,
    NotificationPreferenceOut,
    PreferenceUpdate,
    PushSubscriptionIn,
)
from app.services.notifications import ensure_preference_row

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.recipient_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    total = db.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar() or 0
    rows = db.execute(
        query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return {
        "items": [NotificationOut.model_validate(n) for n in rows],
        "total": total,
        "unread": db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_id == user.id,
                Notification.is_read.is_(False),
            )
        ).scalar()
        or 0,
    }


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_id == user.id,
            Notification.is_read.is_(False),
        )
    ).scalar() or 0
    return {"count": count}


@router.post("/read")
def mark_read(
    payload: NotificationMarkRead,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.recipient_id == user.id)
    if payload.ids:
        query = query.where(Notification.id.in_(payload.ids))
    if payload.all or not payload.ids:
        db.execute(
            Notification.__table__.update()
            .where(Notification.__table__.c.recipient_id == user.id)
            .values(is_read=True)
        )
    else:
        for n in db.execute(query).scalars():
            n.is_read = True
    db.commit()
    return {"message": "Notifications marked as read"}


@router.get("/preferences", response_model=list[NotificationPreferenceOut])
def list_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    ).scalars().all()
    return rows


@router.put("/preferences", response_model=NotificationPreferenceOut)
def update_preference(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = ensure_preference_row(db, user.id, payload.category)
    pref.enabled = payload.enabled
    db.commit()
    db.refresh(pref)
    return pref


@router.post("/push-subscription")
def save_push_subscription(
    payload: PushSubscriptionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).scalar_one_or_none()
    if existing:
        existing.p256dh = payload.p256dh
        existing.auth = payload.auth
        existing.user_id = user.id
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=payload.endpoint,
                p256dh=payload.p256dh,
                auth=payload.auth,
            )
        )
    db.commit()
    return {"message": "Push subscription saved"}


@router.delete("/push-subscription")
def delete_push_subscription(
    endpoint: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == user.id,
        )
    ).scalar_one_or_none()
    if sub:
        db.delete(sub)
        db.commit()
    return {"message": "Push subscription removed"}


@router.get("/vapid-public-key")
def vapid_public_key():
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=404, detail="Web Push not configured")
    return {"public_key": settings.VAPID_PUBLIC_KEY}
import asyncio
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    NotificationPreference,
    NotificationType,
    PushSubscription,
)
from app.websocket.manager import EVENT_NOTIFICATION, build_event, manager

_ws_loop: asyncio.AbstractEventLoop | None = None
_ws_loop_lock = threading.Lock()


def _ws_loop_instance() -> asyncio.AbstractEventLoop | None:
    """Return a long-lived event loop running on a daemon thread, starting it
    lazily. Scheduled coroutines are pushed onto it so they always have a
    running loop to execute on (never left dangling on an unstarted loop)."""
    global _ws_loop
    with _ws_loop_lock:
        if _ws_loop is None or _ws_loop.is_closed():
            _ws_loop = asyncio.new_event_loop()
            threading.Thread(
                target=_ws_loop.run_forever, daemon=True, name="internflow-ws"
            ).start()
        return _ws_loop


def send_event_async(user_id: int, event: dict) -> None:
    """Schedule a websocket delivery without blocking the request lifecycle."""
    loop = _ws_loop_instance()
    if loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.send_to_user(user_id, event), loop)
    except Exception:  # pragma: no cover
        pass


def _event_for(notification: Notification) -> dict:
    return build_event(
        EVENT_NOTIFICATION,
        {
            "id": notification.id,
            "type": notification.notification_type,
            "title": notification.title,
            "body": notification.body,
            "link": notification.link,
            "created_at": notification.created_at.isoformat(),
            "is_read": notification.is_read,
        },
        notification.recipient_id,
    )


def _type_str(notification_type: NotificationType | str) -> str:
    return notification_type.value if hasattr(notification_type, "value") else notification_type


def create_notification(
    db: Session,
    recipient_id: int,
    notification_type: NotificationType | str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    actor_id: int | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        notification_type=_type_str(notification_type),
        title=title,
        body=body,
        link=link,
    )
    db.add(notification)
    db.flush()
    send_event_async(recipient_id, _event_for(notification))
    return notification


def notify_many(
    db: Session,
    recipient_ids: list[int],
    notification_type: NotificationType | str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    actor_id: int | None = None,
) -> int:
    notifications: list[Notification] = []
    for rid in set(recipient_ids):
        if rid == actor_id:
            continue
        notifications.append(
            Notification(
                recipient_id=rid,
                actor_id=actor_id,
                notification_type=_type_str(notification_type),
                title=title,
                body=body,
                link=link,
            )
        )
    if not notifications:
        return 0
    db.add_all(notifications)
    db.flush()
    for n in notifications:
        send_event_async(n.recipient_id, _event_for(n))
    return len(notifications)


def user_preferences_map(db: Session, user_id: int) -> dict[str, bool]:
    rows = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    ).scalars()
    return {p.category: p.enabled for p in rows}


def ensure_preference_row(db: Session, user_id: int, category: str) -> NotificationPreference:
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.category == category,
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id, category=category, enabled=True)
        db.add(pref)
        db.flush()
    return pref


def get_batch_intern_ids(db: Session, batch_id: int) -> list[int]:
    from app.models import BatchMembership

    rows = db.execute(
        select(BatchMembership.intern_id).where(
            BatchMembership.batch_id == batch_id,
            BatchMembership.is_active.is_(True),
        )
    )
    return [r[0] for r in rows]


def get_push_subscriptions(db: Session, user_id: int) -> list[PushSubscription]:
    return list(
        db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        ).scalars()
    )
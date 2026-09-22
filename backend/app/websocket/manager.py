import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("internflow.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        await websocket.accept()
        async with self._lock:
            self.active.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        async with self._lock:
            conns = self.active.get(user_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    self.active.pop(user_id, None)

    def _serialize(self, event: dict[str, Any]) -> str:
        return json.dumps(event, default=str)

    async def send_to_user(self, user_ids: list[int] | int, event: dict[str, Any]) -> int:
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        payload = self._serialize(event)
        sent = 0
        for uid in user_ids:
            conns = self.active.get(uid)
            if not conns:
                continue
            for ws in list(conns):
                try:
                    await ws.send_text(payload)
                    sent += 1
                except Exception:  # pragma: no cover
                    await self.disconnect(ws, uid)
        return sent

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = self._serialize(event)
        for uid, conns in list(self.active.items()):
            for ws in list(conns):
                try:
                    await ws.send_text(payload)
                except Exception:  # pragma: no cover
                    await self.disconnect(ws, uid)


manager = ConnectionManager()

# Real-time event types surfaced to the frontend
EVENT_COMMENT = "comment.created"
EVENT_MENTION = "mention.created"
EVENT_ANNOUNCEMENT = "announcement.created"
EVENT_NOTIFICATION = "notification.created"
EVENT_REVIEW = "submission.reviewed"
EVENT_SUBMISSION = "submission.submitted"
EVENT_ATTENDANCE = "attendance.updated"
EVENT_TASK = "task.updated"
EVENT_EXTENSION = "extension.granted"
EVENT_LEAVE = "leave.decided"
EVENT_EVENT_BATCH = "batch_event.created"


def build_event(name: str, payload: dict[str, Any], receiver_id: int) -> dict[str, Any]:
    return {"type": name, "data": payload, "for_user": receiver_id}
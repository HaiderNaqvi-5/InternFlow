from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_id: int
    notification_type: str
    title: str
    body: str | None = None
    link: str | None = None
    is_read: bool
    created_at: datetime


class NotificationMarkRead(BaseModel):
    ids: list[int] | None = None
    all: bool = False


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: str
    enabled: bool


class PreferenceUpdate(BaseModel):
    category: str
    enabled: bool


class PushSubscriptionIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class SearchSuggestion(BaseModel):
    type: str
    id: int
    label: str
    subtitle: str | None = None
    link: str


class SearchResults(BaseModel):
    query: str
    results: list[SearchSuggestion]


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None = None
    actor_name: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    metadata_json: dict | None = None
    created_at: datetime
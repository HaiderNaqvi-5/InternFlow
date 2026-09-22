from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_id: int
    author_name: str | None = None
    content: str
    is_edited: bool
    is_deleted: bool
    is_pinned: bool
    mentions: list[int] = []
    created_at: datetime
    updated_at: datetime | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    mentions: list[int] = []


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1)


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    batch_name: str | None = None
    author_id: int
    author_name: str | None = None
    title: str
    content: str | None = None
    is_pinned: bool
    is_archived: bool
    attachments: list[dict] = []
    created_at: datetime


class AnnouncementCreate(BaseModel):
    batch_id: int
    title: str
    content: str | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    is_pinned: bool | None = None


class BatchEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    title: str
    event_type: str
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = None
    details: str | None = None
    created_by: int | None = None
    created_at: datetime


class BatchEventCreate(BaseModel):
    batch_id: int
    title: str
    event_type: str = "other"
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = None
    details: str | None = None
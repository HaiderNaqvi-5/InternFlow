from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    storage_key: str
    content_type: str | None = None
    size_bytes: int | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    scope: str
    batch_id: int
    assignee_id: int | None = None
    created_by: int
    category: str
    priority: str
    deadline: datetime
    estimated_effort_hours: float
    status: str
    is_archived: bool
    batch_name: str | None = None
    assignee_name: str | None = None
    creator_name: str | None = None
    has_submission: bool = False
    my_submission_status: str | None = None
    created_at: datetime


class TaskDetail(TaskOut):
    attachments: list[TaskAttachmentOut] = []
    effective_deadline: datetime | None = None


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    scope: str = "batch"
    batch_id: int
    assignee_id: int | None = None
    category: str = "Other"
    priority: str = "Medium"
    deadline: datetime
    estimated_effort_hours: float = Field(default=1.0, ge=0)


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    priority: str | None = None
    deadline: datetime | None = None
    estimated_effort_hours: float | None = None
    status: str | None = None


class ExtensionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    intern_id: int
    original_deadline: datetime
    new_deadline: datetime
    reason: str | None = None
    granted_by: int | None = None
    created_at: datetime


class ExtensionCreate(BaseModel):
    task_id: int
    intern_id: int
    new_deadline: datetime
    reason: str | None = None


class PaginatedTasks(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int
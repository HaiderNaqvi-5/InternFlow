from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubmissionCreate(BaseModel):
    github_url: str | None = None
    live_url: str | None = None
    notes: str | None = None
    actual_effort_hours: float | None = Field(default=None, ge=0)
    late_reason: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    supervisor_id: int
    supervisor_name: str | None = None
    decision: str
    score: float
    feedback: str
    reviewed_at: datetime


class ReviewCreate(BaseModel):
    decision: str
    score: float = Field(ge=0, le=10)
    feedback: str = Field(min_length=1)


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    task_title: str | None = None
    intern_id: int
    batch_id: int
    version: int
    github_url: str | None = None
    live_url: str | None = None
    zip_file_key: str | None = None
    filename: str | None = None
    notes: str | None = None
    actual_effort_hours: float | None = None
    submitted_at: datetime
    is_late: bool
    late_reason: str | None = None
    status: str
    reviews: list[ReviewOut] = []


class SubmissionDetail(SubmissionOut):
    reviews: list[ReviewOut] = []


class PaginatedSubmissions(BaseModel):
    items: list[SubmissionOut]
    total: int
    page: int
    page_size: int
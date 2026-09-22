from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    description: str | None = None
    logo_key: str | None = None
    certificate_template_key: str | None = None
    signature_ceo_key: str | None = None
    signature_instructor_key: str | None = None
    default_start_time: str
    default_end_time: str
    default_grace_minutes: int
    logo_url: str | None = None


class CompanySettingsUpdate(BaseModel):
    company_name: str | None = None
    description: str | None = None
    default_start_time: str | None = None
    default_end_time: str | None = None
    default_grace_minutes: int | None = Field(default=None, ge=0)


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    start_date: date
    end_date: date
    supervisor_id: int
    supervisor_name: str | None = None
    capacity: int
    start_time: str
    end_time: str
    grace_minutes: int
    status: str
    active_intern_count: int | None = None
    created_at: datetime


class BatchCreate(BaseModel):
    name: str
    description: str | None = None
    start_date: date
    end_date: date
    supervisor_id: int
    capacity: int = Field(default=20, ge=1)
    start_time: str = "09:00"
    end_time: str = "18:00"
    grace_minutes: int = Field(default=20, ge=0)


class BatchUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    supervisor_id: int | None = None
    capacity: int | None = Field(default=None, ge=1)
    start_time: str | None = None
    end_time: str | None = None
    grace_minutes: int | None = Field(default=None, ge=0)


class BatchMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intern_id: int
    intern_name: str | None = None
    email: str | None = None
    is_active: bool
    joined_at: datetime


class BatchDetail(BatchOut):
    memberships: list[BatchMembershipOut] = []


class AddInternRequest(BaseModel):
    user_id: int


class AddInternsRequest(BaseModel):
    user_ids: list[int]


class PaginatedBatches(BaseModel):
    items: list[BatchOut]
    total: int
    page: int
    page_size: int
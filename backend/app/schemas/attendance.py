from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intern_id: int
    batch_id: int
    date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    late_status: str | None = None
    worked_hours: float | None = None
    work_done: str | None = None
    blockers: str | None = None
    next_day_plan: str | None = None
    remarks: list[dict] = []


class DailyLogUpdate(BaseModel):
    work_done: str | None = None
    blockers: str | None = None
    next_day_plan: str | None = None


class RemarkCreate(BaseModel):
    remark: str = Field(min_length=1)


class LeaveCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str
    note: str | None = None


class LeaveDecision(BaseModel):
    approve: bool


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intern_id: int
    intern_name: str | None = None
    batch_id: int
    start_date: date
    end_date: date
    reason: str
    note: str | None = None
    status: str
    decided_at: datetime | None = None
    created_at: datetime


class AttendanceSummaryRow(BaseModel):
    intern_id: int
    intern_name: str
    present_days: int
    late_days: int
    total_hours: float
    workdays: int
    attendance_rate: float
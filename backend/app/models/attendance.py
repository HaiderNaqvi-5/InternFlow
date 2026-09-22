from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import AttendanceStatus


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("intern_id", "date", name="uq_attendance_intern_date"),
        Index("ix_attendance_batch_date", "batch_id", "date"),
    )

    id: int = Column(Integer, primary_key=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime(timezone=True), nullable=True)
    check_out = Column(DateTime(timezone=True), nullable=True)
    late_status = Column(Enum(AttendanceStatus), nullable=True)
    worked_hours = Column(Float, nullable=True, default=0.0)
    work_done = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    next_day_plan = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    intern = relationship("User", foreign_keys=[intern_id])
    batch = relationship("Batch", foreign_keys=[batch_id])
    remarks = relationship(
        "AttendanceRemark", back_populates="attendance", cascade="all, delete-orphan"
    )


class AttendanceRemark(Base):
    __tablename__ = "attendance_remarks"

    id: int = Column(Integer, primary_key=True)
    attendance_id = Column(Integer, ForeignKey("attendance_records.id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    remark = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    attendance = relationship("AttendanceRecord", back_populates="remarks")
    supervisor = relationship("User", foreign_keys=[supervisor_id])


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: int = Column(Integer, primary_key=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    note = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    intern = relationship("User", foreign_keys=[intern_id])
    decider = relationship("User", foreign_keys=[decided_by])
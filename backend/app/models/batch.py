from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import BatchStatus


class Batch(Base):
    __tablename__ = "batches"

    id: int = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    capacity = Column(Integer, nullable=False, default=20)
    start_time = Column(String(5), nullable=False, default="09:00")
    end_time = Column(String(5), nullable=False, default="18:00")
    grace_minutes = Column(Integer, nullable=False, default=20)
    status = Column(Enum(BatchStatus), nullable=False, default=BatchStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    supervisor = relationship("User", foreign_keys=[supervisor_id])
    memberships = relationship(
        "BatchMembership",
        back_populates="batch",
        foreign_keys="BatchMembership.batch_id",
        cascade="all, delete-orphan",
    )
    tasks = relationship(
        "Task", back_populates="batch", foreign_keys="Task.batch_id", lazy="selectin"
    )

    @property
    def working_start(self) -> time:
        return time.fromisoformat(self.start_time or "09:00")

    @property
    def working_end(self) -> time:
        return time.fromisoformat(self.end_time or "18:00")

    @property
    def active_intern_count(self) -> int:
        return sum(1 for m in self.memberships if m.is_active)


class BatchMembership(Base):
    __tablename__ = "batch_memberships"
    __table_args__ = (
        Index(
            "ix_single_active_membership",
            "intern_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        UniqueConstraint("batch_id", "intern_id", name="uq_batch_intern"),
    )

    id: int = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime(timezone=True), nullable=True)

    batch = relationship("Batch", back_populates="memberships", foreign_keys=[batch_id])
    intern = relationship("User", back_populates="batch_memberships", foreign_keys=[intern_id])

    def __repr__(self) -> str:
        return f"<BatchMembership(batch={self.batch_id}, intern={self.intern_id}, active={self.is_active})>"
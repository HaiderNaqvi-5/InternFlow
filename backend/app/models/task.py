from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import TaskCategory, TaskPriority, TaskScope, TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id: int = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    scope = Column(Enum(TaskScope), nullable=False, default=TaskScope.BATCH)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(Enum(TaskCategory), nullable=False, default=TaskCategory.OTHER)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)
    deadline = Column(DateTime(timezone=True), nullable=False, index=True)
    estimated_effort_hours = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.OPEN)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    batch = relationship("Batch", back_populates="tasks", foreign_keys=[batch_id])
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assignee_id])
    attachments = relationship(
        "TaskAttachment", back_populates="task", cascade="all, delete-orphan"
    )
    submissions = relationship("Submission", back_populates="task")
    extensions = relationship("DeadlineExtension", back_populates="task")
    comments = relationship(
        "TaskComment", back_populates="task", cascade="all, delete-orphan"
    )


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id: int = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    storage_key = Column(String(500), nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True, default=0)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="attachments")


class DeadlineExtension(Base):
    __tablename__ = "deadline_extensions"

    id: int = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    original_deadline = Column(DateTime(timezone=True), nullable=False)
    new_deadline = Column(DateTime(timezone=True), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="extensions")

    __table_args__ = (
        Index("ix_extension_task_intern", "task_id", "intern_id"),
    )
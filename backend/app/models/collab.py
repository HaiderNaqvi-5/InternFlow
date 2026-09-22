from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: int = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_edited = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_pinned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    task = relationship("Task", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])
    mentions = relationship(
        "CommentMention", back_populates="comment", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_comments_task_created", "task_id", "created_at"),)


class CommentMention(Base):
    __tablename__ = "comment_mentions"
    __table_args__ = (
        UniqueConstraint("comment_id", "mentioned_user_id", name="uq_comment_mention"),
    )

    id: int = Column(Integer, primary_key=True)
    comment_id = Column(Integer, ForeignKey("task_comments.id"), nullable=False, index=True)
    mentioned_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    comment = relationship("TaskComment", back_populates="mentions")
    mentioned_user = relationship("User", foreign_keys=[mentioned_user_id])


class Announcement(Base):
    __tablename__ = "announcements"

    id: int = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    batch = relationship("Batch", foreign_keys=[batch_id])
    author = relationship("User", foreign_keys=[author_id])
    attachments = relationship(
        "AnnouncementAttachment", back_populates="announcement", cascade="all, delete-orphan"
    )


class AnnouncementAttachment(Base):
    __tablename__ = "announcement_attachments"

    id: int = Column(Integer, primary_key=True)
    announcement_id = Column(
        Integer, ForeignKey("announcements.id"), nullable=False, index=True
    )
    filename = Column(String(500), nullable=False)
    storage_key = Column(String(500), nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True, default=0)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    announcement = relationship("Announcement", back_populates="attachments")


class BatchEvent(Base):
    __tablename__ = "batch_events"

    id: int = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    event_type = Column(String(32), nullable=False, default="other")
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    location = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    batch = relationship("Batch", foreign_keys=[batch_id])
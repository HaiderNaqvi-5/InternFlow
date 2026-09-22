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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import ReviewDecision, SubmissionStatus


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "intern_id", "version", name="uq_submission_version"),
        Index("ix_submission_task_intern", "task_id", "intern_id"),
    )

    id: int = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    github_url = Column(String(500), nullable=True)
    live_url = Column(String(500), nullable=True)
    zip_file_key = Column(String(500), nullable=True)
    filename = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    actual_effort_hours = Column(Float, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    is_late = Column(Boolean, nullable=False, default=False)
    late_reason = Column(Text, nullable=True)
    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.PENDING)
    latest_review = Column(String(32), nullable=True)

    task = relationship("Task", back_populates="submissions")
    intern = relationship("User", back_populates="submissions", foreign_keys=[intern_id])
    reviews = relationship(
        "SubmissionReview",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SubmissionReview(Base):
    __tablename__ = "submission_reviews"

    id: int = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    decision = Column(Enum(ReviewDecision), nullable=False)
    score = Column(Float, nullable=False)
    feedback = Column(Text, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    submission = relationship("Submission", back_populates="reviews")
    supervisor = relationship("User", back_populates="reviews", foreign_keys=[supervisor_id])
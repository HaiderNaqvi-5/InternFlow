import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import UserRole


def _uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.INTERN)
    full_name = Column(String(255), nullable=False)
    must_reset_password = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    phone = Column(String(32), nullable=True)
    bio = Column(Text, nullable=True)
    github_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    avatar_key = Column(String(500), nullable=True)
    skills = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    batch_memberships = relationship(
        "BatchMembership", back_populates="intern", foreign_keys="BatchMembership.intern_id"
    )
    tasks_created = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")
    submissions = relationship("Submission", back_populates="intern")
    reviews = relationship("SubmissionReview", back_populates="supervisor")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: int = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
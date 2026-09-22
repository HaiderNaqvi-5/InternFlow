from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class InternshipOutcome(Base):
    __tablename__ = "internship_outcomes"
    __table_args__ = (
        UniqueConstraint("intern_id", "batch_id", name="uq_outcome_intern_batch"),
    )

    id: int = Column(Integer, primary_key=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    supervisor_recommendation = Column(String(40), nullable=True)
    hr_completion_status = Column(String(40), nullable=False, default="not_completed")
    completed_on = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    intern = relationship("User", foreign_keys=[intern_id])


class Report(Base):
    __tablename__ = "reports"

    id: int = Column(Integer, primary_key=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    report_type = Column(String(50), nullable=False, default="internship_report")
    file_key = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    intern = relationship("User", foreign_keys=[intern_id])
    batch = relationship("Batch", foreign_keys=[batch_id])


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("intern_id", "batch_id", name="uq_cert_intern_batch"),
    )

    id: int = Column(Integer, primary_key=True)
    intern_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, index=True)
    template_version = Column(String(32), nullable=False, default="v1")
    signature_ceo_key = Column(String(500), nullable=True)
    signature_instructor_key = Column(String(500), nullable=True)
    file_key = Column(String(500), nullable=True)
    filename = Column(String(500), nullable=True)
    issued_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    intern = relationship("User", foreign_keys=[intern_id])
    batch = relationship("Batch", foreign_keys=[batch_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: int = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(60), nullable=True)
    entity_id = Column(Integer, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    actor = relationship("User", foreign_keys=[actor_id])
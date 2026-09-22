from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: int = Column(Integer, primary_key=True)
    company_name = Column(String(255), nullable=False, default="")
    description = Column(String(500), nullable=True)
    logo_key = Column(String(500), nullable=True)
    certificate_template_key = Column(String(500), nullable=True)
    signature_ceo_key = Column(String(500), nullable=True)
    signature_instructor_key = Column(String(500), nullable=True)
    default_start_time = Column(String(5), nullable=False, default="09:00")
    default_end_time = Column(String(5), nullable=False, default="18:00")
    default_grace_minutes = Column(Integer, nullable=False, default=20)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
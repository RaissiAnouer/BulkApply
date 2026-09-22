"""Job model — stores extracted and user-edited job postings."""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "url", name="uq_user_job_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    work_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # remote, hybrid, onsite
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    application_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # form, email, external_link

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="jobs")
    applications = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )
    company_intelligence = relationship(
        "CompanyIntelligence", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

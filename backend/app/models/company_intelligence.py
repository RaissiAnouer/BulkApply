"""Company Intelligence and Contact models."""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CompanyIntelligence(Base):
    __tablename__ = "company_intelligence"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    headquarters: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    technologies: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Confidence: HIGH, MEDIUM, LOW, UNKNOWN
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")

    # Status: PENDING, RESEARCHING, COMPLETED, FAILED
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    job = relationship("Job", back_populates="company_intelligence")
    contacts = relationship(
        "CompanyContact", back_populates="intelligence", cascade="all, delete-orphan"
    )


class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    intelligence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_intelligence.id", ondelete="CASCADE"), nullable=False, index=True
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Category: "hiring", "leadership", "other"
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Confidence: HIGH, MEDIUM, LOW
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User review flag
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    intelligence = relationship("CompanyIntelligence", back_populates="contacts")

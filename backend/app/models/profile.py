from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobSeekerProfile(Base):
    __tablename__ = "job_seeker_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Required for MVP — enforced NOT NULL in DB
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(150), nullable=False, default="")

    # Optional Professional Links
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Conditional Eligibility Fields (NULL means not provided / not answered yet)
    work_authorization: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    requires_sponsorship: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)

    # Conditional Qualifications (Required only when specific job asks, empty during basic profile)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    salary_expectation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Optional Job Preferences
    target_job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    work_preference: Mapped[str | None] = mapped_column(String(30), nullable=True, default="remote")
    employment_type: Mapped[str | None] = mapped_column(String(30), nullable=True, default="full-time")
    preferred_locations: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="profile")

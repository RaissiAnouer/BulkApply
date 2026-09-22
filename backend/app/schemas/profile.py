"""Pydantic schemas for Job Seeker Profile and Admin User Management."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=150)
    phone: str | None = Field(None, max_length=30)
    location: str | None = Field(None, max_length=150)

    linkedin_url: str | None = Field(None, max_length=255)
    github_url: str | None = Field(None, max_length=255)
    portfolio_url: str | None = Field(None, max_length=255)

    # Nullable eligibility flags: None = not provided yet
    work_authorization: bool | None = None
    requires_sponsorship: bool | None = None

    # Conditional fields (empty until required by application)
    years_of_experience: int | None = Field(None, ge=0, le=70)
    salary_expectation: str | None = Field(None, max_length=50)
    education_level: str | None = Field(None, max_length=100)
    languages: str | None = Field(None, max_length=255)

    # Optional Job Preferences
    target_job_title: str | None = Field(None, max_length=150)
    work_preference: str | None = Field(None, max_length=30)
    employment_type: str | None = Field(None, max_length=30)
    preferred_locations: str | None = Field(None, max_length=255)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str
    role: str
    is_active: bool
    is_verified: bool

    full_name: str
    phone: str
    location: str

    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

    work_authorization: bool | None = None
    requires_sponsorship: bool | None = None

    years_of_experience: int | None = None
    salary_expectation: str | None = None
    education_level: str | None = None
    languages: str | None = None

    target_job_title: str | None = None
    work_preference: str | None = None
    employment_type: str | None = None
    preferred_locations: str | None = None

    created_at: datetime
    updated_at: datetime


class AdminUserSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    profile: ProfileResponse | None = None

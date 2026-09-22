"""Pydantic schemas for Job management and URL extraction."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
import re
from app.schemas.company_intelligence import CompanyIntelligenceData


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class JobExtractRequest(BaseModel):
    """Submitted by the user to extract job data from a URL."""
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", v, re.IGNORECASE):
            raise ValueError("Please enter a valid URL (must start with http:// or https://)")
        return v


class JobSaveRequest(BaseModel):
    """Sent when the user saves a reviewed/edited job to the database."""
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    description: str | None = None
    salary: str | None = None
    application_url: str | None = None
    application_method: str | None = None
    company_intelligence: CompanyIntelligenceData | None = None

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("remote", "hybrid", "onsite", ""):
            raise ValueError("work_type must be 'remote', 'hybrid', or 'onsite'")
        return v or None

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, v: str | None) -> str | None:
        valid = ("entry", "mid", "senior", "lead", "executive", "")
        if v is not None and v not in valid:
            raise ValueError(f"experience_level must be one of: {', '.join(valid)}")
        return v or None


class JobUpdateRequest(BaseModel):
    """Partial update of job fields."""
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    description: str | None = None
    salary: str | None = None
    application_url: str | None = None
    application_method: str | None = None
    status: str | None = None

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("remote", "hybrid", "onsite", ""):
            raise ValueError("work_type must be 'remote', 'hybrid', or 'onsite'")
        return v or None

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, v: str | None) -> str | None:
        valid = ("entry", "mid", "senior", "lead", "executive", "")
        if v is not None and v not in valid:
            raise ValueError(f"experience_level must be one of: {', '.join(valid)}")
        return v or None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class JobExtractedResponse(BaseModel):
    """Returned from the extraction endpoint — preview data, NOT saved yet."""
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    description: str | None = None
    salary: str | None = None
    application_url: str | None = None
    application_method: str | None = None
    extraction_method: str | None = None  # "gemini_url_context", "gemini_text_fallback", "manual"
    extraction_warning: str | None = None  # warning message if extraction was partial/failed
    company_intelligence: CompanyIntelligenceData | None = None


class JobResponse(BaseModel):
    """Full job record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    description: str | None = None
    salary: str | None = None
    application_url: str | None = None
    application_method: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """Paginated job list."""
    items: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Gemini extraction schema (used as response_schema for structured output)
# ---------------------------------------------------------------------------

class GeminiJobExtraction(BaseModel):
    """Schema passed to Gemini for structured JSON output."""
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None  # remote, hybrid, onsite
    experience_level: str | None = None  # entry, mid, senior, lead, executive
    skills: str | None = None  # comma-separated
    description: str | None = None
    salary: str | None = None
    application_url: str | None = None
    application_method: str | None = None  # form, email, external_link


# ---------------------------------------------------------------------------
# Bulk Import Schemas
# ---------------------------------------------------------------------------

class BulkJobExtractRequest(BaseModel):
    """Submitted by the user to extract multiple job URLs in bulk."""
    urls: list[str]


class BulkJobItemResult(BaseModel):
    """Result of extracting an individual URL in a bulk batch."""
    url: str
    status: str  # "extracted", "duplicate", "failed"
    error: str | None = None
    data: JobExtractedResponse | None = None
    existing_job_id: int | None = None


class BulkJobExtractResponse(BaseModel):
    """Response containing batch extraction statistics and items."""
    total: int
    extracted_count: int
    duplicate_count: int
    failed_count: int
    items: list[BulkJobItemResult]


class BulkJobSaveRequest(BaseModel):
    """List of reviewed job objects to save in bulk."""
    jobs: list[JobSaveRequest]


class BulkJobSaveResponse(BaseModel):
    """Response returned after bulk saving jobs."""
    saved_count: int
    skipped_count: int
    saved_jobs: list[JobResponse]

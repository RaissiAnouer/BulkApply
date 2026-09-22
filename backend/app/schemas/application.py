"""Pydantic schemas for the Applications module."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    url: str
    application_url: str | None = None


class StatusHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    notes: str | None = None
    created_at: datetime


class ApplicationCreateRequest(BaseModel):
    job_ids: list[int] = Field(..., min_length=1, description="List of Job IDs to create applications for")


class ApplicationCreateResponse(BaseModel):
    message: str
    application_ids: list[int]
    count: int


class ApplicationStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: interview, offer, or rejected")
    notes: str | None = Field(None, description="Optional note for status transition")


class ApplicationCoverLetterUpdate(BaseModel):
    cover_letter: str = Field(..., min_length=10, description="Updated cover letter content")


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    job_id: int
    status: str
    cover_letter: str | None = None
    failure_reason: str | None = None
    discovered_form_url: str | None = None

    # Diagnostics (AUT-19 to AUT-32)
    execution_id: str | None = None
    error_type: str | None = None
    error_phase: str | None = None
    technical_error: str | None = None
    last_action: str | None = None
    discovery_step: int | None = None
    manual_intervention_required: bool = False

    created_at: datetime
    updated_at: datetime
    job: JobSummary | None = None


class ApplicationDetailResponse(ApplicationResponse):
    status_history: list[StatusHistoryEntry] = []
    action_log: str | None = None
    error_details: str | None = None
    screenshot_path: str | None = None
    has_screenshot: bool = False


class AutomationDiagnosticsResponse(BaseModel):
    application_id: int
    execution_id: str | None = None
    status: str
    phase: str | None = None
    error_type: str | None = None
    failure_reason: str | None = None
    technical_error: str | None = None
    last_action: str | None = None
    discovery_step: int | None = None
    manual_intervention_required: bool = False
    has_screenshot: bool = False
    action_log: list[dict[str, Any]] = []
    error_details: dict[str, Any] | None = None


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DailyQuotaResponse(BaseModel):
    limit: int
    used_today: int
    remaining: int


class BatchSubmitRequest(BaseModel):
    application_ids: list[int] = Field(..., min_length=1, description="List of Application IDs to submit")


class AutomationSubmitResponse(BaseModel):
    message: str
    application_ids: list[int]
    status: str = "queued"


class LinkedInCookieRequest(BaseModel):
    cookie_value: str = Field(..., min_length=5, description="Value of the li_at session cookie")


class BatchDeleteRequest(BaseModel):
    application_ids: list[int] = Field(..., min_length=1, description="List of Application IDs to delete")


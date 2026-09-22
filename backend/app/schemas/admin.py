"""Pydantic schemas for Admin Module."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.profile import AdminUserSummaryResponse


class AdminDashboardMetricsResponse(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    total_jobs: int
    applications_today: int
    total_applications: int
    failure_rate_percent: float
    status_breakdown: dict[str, int]


class SystemSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str
    updated_at: datetime
    updated_by: int | None = None


class SystemSettingUpdateRequest(BaseModel):
    value: str = Field(..., min_length=1, max_length=500, description="New setting value")


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int | None = None
    admin_name: str | None = None
    action: str
    target_user_id: int | None = None
    details: str | None = None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserSummaryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AdminApplicationItem(BaseModel):
    id: int
    job_id: int
    job_title: str | None = None
    job_company: str | None = None
    status: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserDetailResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: str | None = None
    location: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    email_notifications_enabled: bool
    created_at: datetime
    profile: dict | None = None
    cv: dict | None = None
    applications: list[AdminApplicationItem] = []

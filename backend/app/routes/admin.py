"""Admin API endpoints for Dashboard Metrics, System Settings, Audit Logs, and User Management."""

import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_admin
from app.models.user import User
from app.schemas.profile import AdminUserSummaryResponse
from app.schemas.admin import (
    AdminDashboardMetricsResponse,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
    AdminAuditLogResponse,
    AdminUserListResponse,
    AdminUserDetailResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Metrics (ADM-01) ---

@router.get("/metrics", response_model=AdminDashboardMetricsResponse)
def get_dashboard_metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve aggregate system metrics for admin dashboard."""
    return admin_service.get_dashboard_metrics(db)


# --- System Settings (ADM-02) ---

@router.get("/settings", response_model=list[SystemSettingResponse])
def list_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all configurable system settings."""
    daily_limit = admin_service.get_setting(db, "daily_application_limit", default="20")
    return [daily_limit]


@router.put("/settings/{key}", response_model=SystemSettingResponse)
def update_setting(
    key: str,
    data: SystemSettingUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a specific system setting (e.g. daily_application_limit)."""
    if key == "daily_application_limit":
        if not data.value.isdigit() or int(data.value) < 1 or int(data.value) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily application limit must be a positive integer between 1 and 1000.",
            )
    return admin_service.update_setting(db, admin.id, key, data.value)


# --- User Management (ADM-03, ADM-04, ADM-05) ---

@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    q: str | None = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List and search all Job Seeker accounts with pagination."""
    items, total = admin_service.list_job_seekers(db, query=q, page=page, page_size=page_size)
    pages = math.ceil(total / page_size) if total > 0 else 1
    return AdminUserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_details(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """View full user profile, CV, and application history."""
    try:
        return admin_service.get_user_details(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/users/{user_id}/suspend")
def suspend_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Suspend a Job Seeker account."""
    try:
        admin_service.suspend_user(db, admin.id, user_id)
        return {"message": "User suspended successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/users/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reactivate a suspended Job Seeker account."""
    try:
        admin_service.reactivate_user(db, admin.id, user_id)
        return {"message": "User reactivated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Permanently delete a Job Seeker account and associated records."""
    try:
        admin_service.delete_user(db, admin.id, user_id)
        return {"message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Audit Logs (ADM-06) ---

@router.get("/audit-logs", response_model=list[AdminAuditLogResponse])
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List recent administrative audit trail events."""
    return admin_service.list_audit_logs(db, limit=limit)

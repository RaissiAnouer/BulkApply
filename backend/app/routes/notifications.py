"""API endpoints for In-App Notifications and User Preferences."""

import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    NotificationPreferencesRequest,
    NotificationPreferencesResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve notifications for the current user."""
    items, total, unread_count = notification_service.get_notifications(
        db=db,
        user_id=user.id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 1
    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the number of unread notifications for the current user."""
    count = notification_service.get_unread_count(db, user.id)
    return UnreadCountResponse(unread_count=count)


@router.put("/mark-all-read")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications as read for current user."""
    count = notification_service.mark_all_notifications_as_read(db, user.id)
    return {"message": f"Marked {count} notification(s) as read.", "count": count}


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    try:
        notif = notification_service.mark_notification_as_read(db, user.id, notification_id)
        return notif
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get email notification preferences."""
    prefs = notification_service.get_preferences(db, user.id)
    return NotificationPreferencesResponse(**prefs)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def update_preferences(
    data: NotificationPreferencesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update email notification preferences."""
    prefs = notification_service.update_preferences(
        db, user.id, data.email_notifications_enabled
    )
    return NotificationPreferencesResponse(**prefs)

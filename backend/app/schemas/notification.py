"""Pydantic schemas for Notifications."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    application_id: int | None = None
    type: str
    title: str
    message: str
    is_read: bool
    email_sent: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    pages: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPreferencesRequest(BaseModel):
    email_notifications_enabled: bool = Field(..., description="Enable or disable email alerts")


class NotificationPreferencesResponse(BaseModel):
    email_notifications_enabled: bool

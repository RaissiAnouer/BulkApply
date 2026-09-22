"""Notification business logic — create in-app alerts, dispatch failure emails, manage read state."""

import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import send_notification_email

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    message: str,
    application_id: int | None = None,
) -> Notification:
    """
    Create an in-app notification.
    If the type indicates failure or manual intervention, also dispatches an email alert
    provided the user has email notifications enabled.
    """
    user = db.query(User).filter(User.id == user_id).first()
    email_sent = False

    if type in ("app_failed", "manual_intervention") and user and user.email_notifications_enabled:
        try:
            send_notification_email(
                email=user.email,
                subject=f"[AutoApply Alert] {title}",
                message=message,
            )
            email_sent = True
            logger.info("[Notification] Email alert dispatched to %s for %s", user.email, type)
        except Exception as e:
            logger.error("[Notification] Failed to send email alert to %s: %s", user.email, e)

    notification = Notification(
        user_id=user_id,
        application_id=application_id,
        type=type,
        title=title,
        message=message,
        is_read=False,
        email_sent=email_sent,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    logger.info("[Notification] In-app notification #%d created for user #%d: %s", notification.id, user_id, title)
    return notification


def get_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int, int]:
    """Retrieve user notifications with optional unread filter and pagination."""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()

    if unread_only:
        query = query.filter(Notification.is_read == False)

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total, unread_count


def get_unread_count(db: Session, user_id: int) -> int:
    """Return count of unread notifications for a user."""
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()


def mark_notification_as_read(db: Session, user_id: int, notification_id: int) -> Notification:
    """Mark a specific notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()
    if not notif:
        raise ValueError("Notification not found.")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_notifications_as_read(db: Session, user_id: int) -> int:
    """Mark all unread notifications for a user as read."""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return count


def get_preferences(db: Session, user_id: int) -> dict:
    """Get email notification preference for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found.")
    return {"email_notifications_enabled": bool(user.email_notifications_enabled)}


def update_preferences(db: Session, user_id: int, email_notifications_enabled: bool) -> dict:
    """Update email notification preference for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found.")
    user.email_notifications_enabled = email_notifications_enabled
    db.commit()
    return {"email_notifications_enabled": bool(user.email_notifications_enabled)}

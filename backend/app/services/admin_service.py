"""Business logic for Admin Module — Metrics, System Settings, Audit Logging, User Management."""

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.admin import SystemSetting, AdminAuditLog
from app.schemas.profile import AdminUserSummaryResponse
from app.services.profile_service import to_profile_response


def get_dashboard_metrics(db: Session) -> dict:
    """Aggregate system-wide metrics for the Admin dashboard (ADM-01)."""
    total_users = db.query(User).filter(User.role == "job_seeker").count()
    active_users = db.query(User).filter(User.role == "job_seeker", User.is_active == True).count()
    suspended_users = db.query(User).filter(User.role == "job_seeker", User.is_active == False).count()
    total_jobs = db.query(Job).count()

    # UTC start of day for applications today
    now_utc = datetime.now(timezone.utc)
    start_of_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
    applications_today = db.query(Application).filter(Application.created_at >= start_of_day_utc).count()

    total_applications = db.query(Application).count()
    failed_count = db.query(Application).filter(Application.status == "failed").count()

    failure_rate_percent = (
        round((failed_count / total_applications) * 100, 2) if total_applications > 0 else 0.0
    )

    # Status breakdown
    statuses = ["ready", "applying", "submitted", "failed", "interview", "offer", "rejected"]
    status_counts = (
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    status_dict = {s: 0 for s in statuses}
    for st, count in status_counts:
        status_dict[st] = count

    return {
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "total_jobs": total_jobs,
        "applications_today": applications_today,
        "total_applications": total_applications,
        "failure_rate_percent": failure_rate_percent,
        "status_breakdown": status_dict,
    }


def get_setting(db: Session, key: str, default: str = "20") -> SystemSetting:
    """Retrieve system setting by key, creating with default if not found (ADM-02)."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=default)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def update_setting(db: Session, admin_id: int, key: str, value: str) -> SystemSetting:
    """Update system setting and log audit trail (ADM-02, ADM-06)."""
    setting = get_setting(db, key)
    old_value = setting.value
    setting.value = value
    setting.updated_at = datetime.utcnow()
    setting.updated_by = admin_id
    db.commit()
    db.refresh(setting)

    log_admin_action(
        db=db,
        admin_id=admin_id,
        action="update_setting",
        details=f"Setting '{key}' changed from '{old_value}' to '{value}'",
    )
    return setting


def log_admin_action(
    db: Session,
    admin_id: int,
    action: str,
    target_user_id: int | None = None,
    details: str | None = None,
) -> AdminAuditLog:
    """Record an entry in the admin audit log (ADM-06)."""
    log_entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
        created_at=datetime.utcnow(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def list_job_seekers(
    db: Session,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AdminUserSummaryResponse], int]:
    """List or search all Job Seeker users with their profile data (ADM-03)."""
    db_query = db.query(User).filter(User.role == "job_seeker")

    if query and query.strip():
        q = f"%{query.strip()}%"
        db_query = db_query.filter(
            (User.name.ilike(q)) | (User.email.ilike(q))
        )

    total = db_query.count()
    users = (
        db_query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for u in users:
        prof_resp = to_profile_response(u, u.profile) if u.profile else None
        results.append(
            AdminUserSummaryResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                profile=prof_resp,
            )
        )
    return results, total


def get_user_details(db: Session, user_id: int) -> dict:
    """Get full details of a specific user including profile, CV, and application history (ADM-04)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    prof_data = None
    if user.profile:
        p = user.profile
        prof_data = {
            "full_name": p.full_name,
            "phone": p.phone,
            "location": p.location,
            "target_job_title": p.target_job_title,
            "work_authorization": p.work_authorization,
            "requires_sponsorship": p.requires_sponsorship,
            "years_of_experience": p.years_of_experience,
            "salary_expectation": p.salary_expectation,
            "education_level": p.education_level,
            "languages": p.languages,
            "linkedin_url": p.linkedin_url,
            "github_url": p.github_url,
            "portfolio_url": p.portfolio_url,
            "work_preference": p.work_preference,
            "employment_type": p.employment_type,
            "preferred_locations": p.preferred_locations,
        }

    cv_data = None
    if user.cv:
        cv_data = {
            "file_name": user.cv.file_name,
            "file_size": user.cv.file_size,
            "file_type": user.cv.file_type,
            "parsed_data": user.cv.parsed_data,
            "created_at": user.cv.created_at.isoformat(),
        }

    # Applications list
    apps = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    app_items = []
    for a in apps:
        app_items.append({
            "id": a.id,
            "job_id": a.job_id,
            "job_title": a.job.title if a.job else None,
            "job_company": a.job.company if a.job else None,
            "status": a.status,
            "failure_reason": a.failure_reason,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        })

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "location": user.location,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "email_notifications_enabled": user.email_notifications_enabled,
        "created_at": user.created_at,
        "profile": prof_data,
        "cv": cv_data,
        "applications": app_items,
    }


def suspend_user(db: Session, admin_id: int, user_id: int) -> User:
    """Suspend a job seeker account and log action (ADM-05, ADM-06)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    if user.role == "admin":
        raise ValueError("Cannot suspend an admin account")

    user.is_active = False
    db.commit()
    db.refresh(user)

    log_admin_action(
        db=db,
        admin_id=admin_id,
        action="suspend_user",
        target_user_id=user.id,
        details=f"Suspended user {user.name} ({user.email})",
    )
    return user


def reactivate_user(db: Session, admin_id: int, user_id: int) -> User:
    """Reactivate a suspended user account and log action (ADM-05, ADM-06)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)

    log_admin_action(
        db=db,
        admin_id=admin_id,
        action="reactivate_user",
        target_user_id=user.id,
        details=f"Reactivated user {user.name} ({user.email})",
    )
    return user


def delete_user(db: Session, admin_id: int, user_id: int) -> None:
    """Delete a user account and log action (ADM-05, ADM-06)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    if user.role == "admin":
        raise ValueError("Cannot delete an admin account")

    user_info = f"{user.name} ({user.email})"
    db.delete(user)
    db.commit()

    log_admin_action(
        db=db,
        admin_id=admin_id,
        action="delete_user",
        target_user_id=user_id,
        details=f"Deleted user {user_info}",
    )


def list_audit_logs(db: Session, limit: int = 50) -> list[dict]:
    """Retrieve recent admin audit log entries (ADM-06)."""
    logs = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for entry in logs:
        results.append({
            "id": entry.id,
            "admin_id": entry.admin_id,
            "admin_name": entry.admin.name if entry.admin else "System",
            "action": entry.action,
            "target_user_id": entry.target_user_id,
            "details": entry.details,
            "created_at": entry.created_at,
        })
    return results

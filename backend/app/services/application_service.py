"""Application Service — handles application creation, rate limiting, and status tracking.

Enforces:
- CV & Profile prerequisite (400)
- Pre-creation duplicate checks (intra-request 400, existing DB 409)
- Atomic batch creation (zero partial creation)
- UTC calendar day rate limiting (default 20/day, batch overflow 429)
- Manual status transitions restricted to interview, offer, rejected (400)
- Cover letter editing restricted to 'ready' status (400)
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.application import Application, ApplicationStatusHistory
from app.models.job import Job
from app.models.user import User
from app.models.cv import CV
from app.models.profile import JobSeekerProfile
from app.services import cover_letter_service

logger = logging.getLogger(__name__)

DAILY_APPLICATION_LIMIT = 20
ALLOWED_MANUAL_STATUSES = {"interview", "offer", "rejected"}
AUTOMATION_ONLY_STATUSES = {"ready", "applying", "submitted", "failed"}
TERMINAL_STATUSES = {"offer", "rejected"}


class ApplicationPrerequisiteError(Exception):
    """Raised when prerequisites like Profile or CV are missing."""
    pass


class ApplicationDuplicateError(Exception):
    """Raised when an application already exists for a job."""
    pass


class RequestDuplicateError(Exception):
    """Raised when job_ids contains duplicate entries within the request."""
    pass


class DailyQuotaExceededError(Exception):
    """Raised when daily application quota is exceeded."""
    pass


class InvalidStatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""
    pass


class InvalidOperationError(Exception):
    """Raised when an operation cannot be performed on current status."""
    pass


def get_start_of_today_utc() -> datetime:
    """Return midnight UTC for the current day."""
    now_utc = datetime.utcnow()
    return datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0)


def get_daily_application_count(db: Session, user_id: int) -> int:
    """Count applications created by user on the current UTC calendar day."""
    start_utc = get_start_of_today_utc()
    count = (
        db.query(func.count(Application.id))
        .filter(Application.user_id == user_id, Application.created_at >= start_utc)
        .scalar()
    )
    return count or 0


def get_daily_application_limit(db: Session) -> int:
    """Retrieve dynamic daily application limit from system_settings, fallback to 20 (ADM-02)."""
    try:
        from app.models.admin import SystemSetting
        setting = db.query(SystemSetting).filter(SystemSetting.key == "daily_application_limit").first()
        if setting and setting.value and setting.value.isdigit():
            return int(setting.value)
    except Exception:
        pass
    return DAILY_APPLICATION_LIMIT


def get_daily_quota(db: Session, user_id: int) -> dict:
    """Get remaining daily application quota."""
    limit = get_daily_application_limit(db)
    used = get_daily_application_count(db, user_id)
    remaining = max(0, limit - used)
    return {
        "limit": limit,
        "used_today": used,
        "remaining": remaining,
    }


def validate_and_create_applications(
    db: Session, user: User, job_ids: list[int]
) -> list[int]:
    """
    Validate batch application request and create applications atomically.
    Zero partial records created if any validation fails.
    """
    if not job_ids:
        raise RequestDuplicateError("At least one job ID must be provided.")

    # 1. Intra-request duplicates check
    if len(job_ids) != len(set(job_ids)):
        raise RequestDuplicateError("Duplicate job IDs provided in request.")

    # 2. CV & Profile check (CV is optional — profile required)
    cv = db.query(CV).filter(CV.user_id == user.id).first()
    cv_parsed_data = (cv.parsed_data if cv and cv.parsed_data else {})

    profile = db.query(JobSeekerProfile).filter(JobSeekerProfile.user_id == user.id).first()
    if not profile:
        raise ApplicationPrerequisiteError(
            "You must complete your profile before applying for jobs."
        )

    # 3. Job existence and ownership check
    jobs = db.query(Job).filter(Job.id.in_(job_ids), Job.user_id == user.id).all()
    if len(jobs) != len(job_ids):
        found_ids = {j.id for j in jobs}
        missing_ids = [jid for jid in job_ids if jid not in found_ids]
        raise ValueError(f"Job(s) not found or not owned: {missing_ids}")

    # Maintain order of requested job_ids
    job_map = {j.id: j for j in jobs}
    ordered_jobs = [job_map[jid] for jid in job_ids]

    # 4. Existing application duplicates check
    existing_apps = (
        db.query(Application.job_id)
        .filter(Application.user_id == user.id, Application.job_id.in_(job_ids))
        .all()
    )
    if existing_apps:
        duplicate_job_ids = [app[0] for app in existing_apps]
        raise ApplicationDuplicateError(
            f"Application already exists for job ID(s): {duplicate_job_ids}"
        )

    # 5. Daily rate limit check (Atomic batch check)
    limit = get_daily_application_limit(db)
    used_today = get_daily_application_count(db, user.id)
    requested_count = len(job_ids)
    if used_today + requested_count > limit:
        remaining = max(0, limit - used_today)
        raise DailyQuotaExceededError(
            f"Daily application limit exceeded. Limit is {limit} per day. "
            f"You have used {used_today} today; {remaining} remaining. Requested {requested_count}."
        )

    # 6. All pre-validations passed. Generate cover letters and create Application records
    cv_contact = (cv_parsed_data.get("contact_info") or {}) if isinstance(cv_parsed_data, dict) else {}
    candidate_name = (
        (cv_contact.get("full_name") or "").strip()
        or (profile.full_name if profile else "")
        or user.name
    )
    created_ids = []

    try:
        for job in ordered_jobs:
            cover_letter, source = cover_letter_service.generate_cover_letter(
                cv_parsed_data=cv_parsed_data,
                candidate_name=candidate_name,
                job_title=job.title,
                company=job.company,
                job_description=job.description,
                job_skills=job.skills,
            )

            application = Application(
                user_id=user.id,
                job_id=job.id,
                status="ready",
                cover_letter=cover_letter,
                failure_reason=None,
            )
            db.add(application)
            db.flush()  # obtain application.id

            history = ApplicationStatusHistory(
                application_id=application.id,
                status="ready",
                notes=f"Application created. Cover letter generated via {source}.",
            )
            db.add(history)
            created_ids.append(application.id)

        db.commit()
        logger.info(
            "Created %d applications for user_id=%d: %s",
            len(created_ids),
            user.id,
            created_ids,
        )
        return created_ids

    except Exception as exc:
        db.rollback()
        logger.error("Failed creating batch applications for user_id=%d: %s", user.id, str(exc))
        raise


def list_applications(
    db: Session,
    user_id: int,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Application], int]:
    """Return paginated list of applications with optional status filtering."""
    query = db.query(Application).filter(Application.user_id == user_id)

    if status and status.strip():
        query = query.filter(Application.status == status.strip().lower())

    total = query.count()
    items = (
        query.order_by(Application.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_application_detail(db: Session, user_id: int, application_id: int) -> Application | None:
    """Retrieve full application details by ID, ensuring user ownership."""
    return (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user_id)
        .first()
    )


def update_application_status(
    db: Session, user_id: int, application_id: int, new_status: str, notes: str | None = None
) -> Application:
    """
    Update application status manually by Job Seeker.
    Allowed manual statuses: interview, offer, rejected.
    Forbidden manual statuses: applying, submitted, failed (reserved for automation).
    """
    app = get_application_detail(db, user_id, application_id)
    if not app:
        raise ValueError("Application not found.")

    target_status = new_status.strip().lower()

    # Automation-only statuses are strictly forbidden for manual user updates
    if target_status in AUTOMATION_ONLY_STATUSES:
        raise InvalidStatusTransitionError(
            f"Cannot manually set status to '{target_status}'. "
            "This status is controlled by the automated application process."
        )

    if target_status not in ALLOWED_MANUAL_STATUSES:
        raise InvalidStatusTransitionError(
            f"Invalid manual status '{target_status}'. Allowed statuses: {sorted(ALLOWED_MANUAL_STATUSES)}"
        )

    # Check terminal statuses
    if app.status in TERMINAL_STATUSES:
        raise InvalidStatusTransitionError(
            f"Application is in terminal status '{app.status}' and cannot be updated."
        )

    previous_status = app.status
    app.status = target_status
    app.updated_at = datetime.utcnow()

    history_entry = ApplicationStatusHistory(
        application_id=app.id,
        status=target_status,
        notes=notes or f"Manual status transition from {previous_status} to {target_status}",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(app)
    return app


def update_cover_letter(
    db: Session, user_id: int, application_id: int, new_cover_letter: str
) -> Application:
    """
    Edit application cover letter. Allowed ONLY while application status is 'ready'.
    """
    app = get_application_detail(db, user_id, application_id)
    if not app:
        raise ValueError("Application not found.")

    if app.status not in ("ready", "failed"):
        raise InvalidOperationError(
            f"Cover letter can only be edited when status is 'ready' or 'failed'. Current status: '{app.status}'."
        )

    app.cover_letter = new_cover_letter.strip()
    app.updated_at = datetime.utcnow()

    history_entry = ApplicationStatusHistory(
        application_id=app.id,
        status=app.status,
        notes="Cover letter edited by user.",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(app)
    return app


def delete_application(db: Session, user_id: int, application_id: int) -> bool:
    """
    Delete an application. Cannot delete while automation is actively running ('applying').
    Cleans up associated status history, nullifies notification links, and removes logs.
    """
    import shutil
    import os

    app = db.query(Application).filter(Application.id == application_id, Application.user_id == user_id).first()
    if not app:
        raise ValueError("Application not found.")

    if app.status == "applying":
        raise InvalidOperationError(
            "Cannot delete an application while automation is actively running. Please cancel automation first."
        )

    # Remove any automation logs directory for this application
    base_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_dir = os.path.join(base_backend, "automation_logs", f"app_{application_id}")
    if os.path.exists(artifacts_dir):
        try:
            shutil.rmtree(artifacts_dir, ignore_errors=True)
        except Exception:
            pass

    # Clean up notifications referencing this application
    try:
        from app.models.notification import Notification
        db.query(Notification).filter(Notification.application_id == application_id).update({"application_id": None})
    except Exception:
        pass

    db.delete(app)
    db.commit()
    logger.info("[ApplicationService] User #%d deleted application #%d", user_id, application_id)
    return True


def batch_delete_applications(db: Session, user_id: int, application_ids: list[int]) -> int:
    """
    Delete multiple applications sequentially, skipping any actively in 'applying' status.
    """
    count = 0
    for app_id in application_ids:
        try:
            if delete_application(db, user_id, app_id):
                count += 1
        except Exception as e:
            logger.warning("[ApplicationService] Error deleting application #%d: %s", app_id, e)
    return count

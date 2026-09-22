"""Job CRUD service — business logic for job management."""

import math
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobSaveRequest, JobUpdateRequest
from app.services.job_extraction_service import extract_job_from_url


def extract_job(url: str) -> dict:
    """Extract job data from a URL. Returns extracted data dict (not saved)."""
    return extract_job_from_url(url)


def save_job(db: Session, user: User, data: JobSaveRequest) -> Job:
    """
    Save a reviewed job to the database.
    Raises ValueError if a duplicate (user_id, url) exists.
    Returns the created Job.
    """
    # Check for duplicate URL for this user
    existing = db.query(Job).filter(
        Job.user_id == user.id,
        Job.url == data.url
    ).first()

    if existing:
        raise ValueError(f"You have already added this job (ID: {existing.id}).")

    job = Job(
        user_id=user.id,
        url=data.url,
        title=data.title,
        company=data.company,
        location=data.location,
        work_type=data.work_type,
        experience_level=data.experience_level,
        skills=data.skills,
        description=data.description,
        salary=data.salary,
        application_url=data.application_url,
        application_method=data.application_method,
        status="ready",
    )

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(
    db: Session,
    user: User,
    q: str | None = None,
    location: str | None = None,
    work_type: str | None = None,
    experience_level: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List jobs for a user with search, filtering, sorting, and pagination.
    Returns dict with items, total, page, page_size, total_pages.
    """
    query = db.query(Job).filter(Job.user_id == user.id)

    # Keyword search (title, company, description)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Job.title.ilike(search_term),
                Job.company.ilike(search_term),
                Job.description.ilike(search_term),
            )
        )

    # Filters
    if location and location.strip():
        query = query.filter(Job.location.ilike(f"%{location.strip()}%"))

    if work_type and work_type.strip():
        query = query.filter(Job.work_type == work_type.strip())

    if experience_level and experience_level.strip():
        query = query.filter(Job.experience_level == experience_level.strip())

    # Total count (before pagination)
    total = query.count()

    # Sorting
    sort_column = getattr(Job, sort_by, Job.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Pagination
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
    }


def get_job(db: Session, user: User, job_id: int) -> Job:
    """Get a single job by ID. Raises ValueError if not found or not owned."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError("Job not found.")
    if job.user_id != user.id:
        raise PermissionError("You do not have access to this job.")
    return job


def update_job(db: Session, user: User, job_id: int, data: JobUpdateRequest) -> Job:
    """Update job fields. Only updates fields that are explicitly provided."""
    job = get_job(db, user, job_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, user: User, job_id: int) -> None:
    """Delete a job. Raises ValueError if not found or not owned."""
    job = get_job(db, user, job_id)
    db.delete(job)
    db.commit()

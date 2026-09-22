"""Job CRUD service — business logic for job management."""

import asyncio
import math
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    JobSaveRequest,
    JobUpdateRequest,
    JobResponse,
    JobExtractedResponse,
    BulkJobItemResult,
    BulkJobExtractResponse,
    BulkJobSaveRequest,
    BulkJobSaveResponse,
)
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

    if data.company_intelligence:
        try:
            from app.services.company_intelligence_service import persist_company_intelligence_from_data
            persist_company_intelligence_from_data(db, job.id, data.company_intelligence)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("[SAVE_JOB] Failed to persist inline company intelligence: %s", e)

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


async def bulk_extract_jobs(db: Session, user: User, urls: list[str]) -> BulkJobExtractResponse:
    """
    Extract multiple job postings concurrently with deduplication and error isolation.
    Bounded by an asyncio.Semaphore to prevent rate limits.
    """
    seen = set()
    clean_urls = []
    for raw in urls:
        u = raw.strip()
        if u and (u.startswith("http://") or u.startswith("https://")) and u not in seen:
            seen.add(u)
            clean_urls.append(u)

    if not clean_urls:
        return BulkJobExtractResponse(
            total=0,
            extracted_count=0,
            duplicate_count=0,
            failed_count=0,
            items=[],
        )

    # Check for existing URLs already in this user's jobs
    existing_jobs = db.query(Job).filter(
        Job.user_id == user.id,
        Job.url.in_(clean_urls)
    ).all()
    existing_map = {j.url: j.id for j in existing_jobs}

    items: list[BulkJobItemResult] = []
    urls_to_extract: list[str] = []

    for u in clean_urls:
        if u in existing_map:
            items.append(
                BulkJobItemResult(
                    url=u,
                    status="duplicate",
                    error="Already in your saved jobs",
                    existing_job_id=existing_map[u],
                )
            )
        else:
            urls_to_extract.append(u)

    semaphore = asyncio.Semaphore(3)

    async def _extract_one(target_url: str) -> BulkJobItemResult:
        async with semaphore:
            try:
                res_dict = await asyncio.to_thread(extract_job_from_url, target_url)
                extracted_resp = JobExtractedResponse(url=target_url, **res_dict)
                return BulkJobItemResult(
                    url=target_url,
                    status="extracted",
                    data=extracted_resp,
                )
            except Exception as e:
                return BulkJobItemResult(
                    url=target_url,
                    status="failed",
                    error=str(e),
                )

    if urls_to_extract:
        extracted_results = await asyncio.gather(
            *[_extract_one(u) for u in urls_to_extract],
            return_exceptions=False
        )
        items.extend(extracted_results)

    extracted_count = sum(1 for i in items if i.status == "extracted")
    duplicate_count = sum(1 for i in items if i.status == "duplicate")
    failed_count = sum(1 for i in items if i.status == "failed")

    return BulkJobExtractResponse(
        total=len(items),
        extracted_count=extracted_count,
        duplicate_count=duplicate_count,
        failed_count=failed_count,
        items=items,
    )


def bulk_save_jobs(db: Session, user: User, data: BulkJobSaveRequest) -> BulkJobSaveResponse:
    """Save multiple reviewed jobs in bulk, skipping duplicates."""
    saved_jobs = []
    saved_pairs = []
    skipped_count = 0

    incoming_urls = [j.url.strip() for j in data.jobs if j.url and j.url.strip()]
    existing = db.query(Job.url).filter(
        Job.user_id == user.id,
        Job.url.in_(incoming_urls)
    ).all()
    existing_urls = {r[0] for r in existing}

    for job_req in data.jobs:
        u = job_req.url.strip()
        if not u or u in existing_urls:
            skipped_count += 1
            continue

        job = Job(
            user_id=user.id,
            url=u,
            title=job_req.title,
            company=job_req.company,
            location=job_req.location,
            work_type=job_req.work_type,
            experience_level=job_req.experience_level,
            skills=job_req.skills,
            description=job_req.description,
            salary=job_req.salary,
            application_url=job_req.application_url,
            application_method=job_req.application_method,
            status="ready",
        )
        db.add(job)
        existing_urls.add(u)
        saved_jobs.append(job)
        saved_pairs.append((job, job_req))

    db.commit()
    for j in saved_jobs:
        db.refresh(j)

    for j, job_req in saved_pairs:
        if job_req.company_intelligence:
            try:
                from app.services.company_intelligence_service import persist_company_intelligence_from_data
                persist_company_intelligence_from_data(db, j.id, job_req.company_intelligence)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("[BULK_SAVE] Failed to persist inline company intelligence: %s", e)

    return BulkJobSaveResponse(
        saved_count=len(saved_jobs),
        skipped_count=skipped_count,
        saved_jobs=[JobResponse.model_validate(j) for j in saved_jobs],
    )

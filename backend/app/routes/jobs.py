"""Job API endpoints for Job Seekers."""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.job import (
    JobExtractRequest,
    JobExtractedResponse,
    JobSaveRequest,
    JobUpdateRequest,
    JobResponse,
    JobListResponse,
    BulkJobExtractRequest,
    BulkJobExtractResponse,
    BulkJobSaveRequest,
    BulkJobSaveResponse,
)
from app.schemas.company_intelligence import (
    CompanyIntelligenceResponse,
    CompanyContactResponse,
    CompanyContactUpdate,
)
from app.services import job_service, company_intelligence_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/bulk-extract", response_model=BulkJobExtractResponse)
async def bulk_extract_jobs(
    data: BulkJobExtractRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract multiple job postings in bulk concurrently with deduplication."""
    return await job_service.bulk_extract_jobs(db, user, data.urls)


@router.post("/bulk-save", response_model=BulkJobSaveResponse)
def bulk_save_jobs(
    data: BulkJobSaveRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save multiple reviewed jobs in bulk to the user's job list."""
    res = job_service.bulk_save_jobs(db, user, data)
    for saved_job in res.saved_jobs:
        background_tasks.add_task(company_intelligence_service.run_company_intelligence_task, saved_job.id)
    return res


@router.post("/extract", response_model=JobExtractedResponse)
def extract_job_from_url(
    data: JobExtractRequest,
    user: User = Depends(get_current_user),
):
    """Submit a URL to extract job posting data (preview — not saved yet)."""
    try:
        result = job_service.extract_job(data.url)
        return JobExtractedResponse(url=data.url, **result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extraction failed: {str(e)}"
        )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def save_job(
    data: JobSaveRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a reviewed job to the user's job list and trigger company intelligence."""
    try:
        job = job_service.save_job(db, user, data)
        background_tasks.add_task(company_intelligence_service.run_company_intelligence_task, job.id)
        return job
    except ValueError as e:
        error_msg = str(e)
        if "already added" in error_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except ValueError as e:
        error_msg = str(e)
        if "already added" in error_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


@router.get("", response_model=JobListResponse)
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Search keyword"),
    search: str | None = Query(None, description="Search keyword alias"),
    location: str | None = Query(None),
    work_type: str | None = Query(None),
    experience_level: str | None = Query(None),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List jobs with search, filtering, sorting, and pagination."""
    keyword = q or search
    return job_service.list_jobs(
        db, user,
        q=keyword,
        location=location,
        work_type=work_type,
        experience_level=experience_level,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single job by ID."""
    try:
        return job_service.get_job(db, user, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    data: JobUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing job's fields."""
    try:
        return job_service.update_job(db, user, job_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a job from the user's list."""
    try:
        job_service.delete_job(db, user, job_id)
        return {"message": "Job deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{job_id}/company-intelligence", response_model=CompanyIntelligenceResponse)
def get_company_intelligence(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve company intelligence and discovered contacts for a job."""
    try:
        intel = company_intelligence_service.get_company_intelligence_for_job(db, job_id, user.id)
        if not intel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company intelligence not found.")
        return intel
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{job_id}/company-intelligence/refresh", response_model=CompanyIntelligenceResponse)
def refresh_company_intelligence(
    job_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-trigger background company intelligence research for a job."""
    try:
        intel = company_intelligence_service.get_company_intelligence_for_job(db, job_id, user.id)
        if not intel:
            job = job_service.get_job(db, user, job_id)
            intel = company_intelligence_service.process_company_intelligence(db, job)
        else:
            intel.status = "RESEARCHING"
            intel.error_message = None
            db.commit()
            background_tasks.add_task(company_intelligence_service.run_company_intelligence_task, job_id)
        return intel
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{job_id}/company-intelligence/contacts/{contact_id}", response_model=CompanyContactResponse)
def update_contact_relevance(
    job_id: int,
    contact_id: int,
    data: CompanyContactUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle whether a discovered contact is marked relevant."""
    try:
        return company_intelligence_service.update_contact_relevance(
            db, job_id, contact_id, user.id, data.is_relevant
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{job_id}/company-intelligence/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    job_id: int,
    contact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a contact from company intelligence."""
    try:
        company_intelligence_service.delete_contact(db, job_id, contact_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

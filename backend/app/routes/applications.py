import os
import math
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.application import Application, ApplicationStatusHistory
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    ApplicationStatusUpdateRequest,
    ApplicationCoverLetterUpdate,
    ApplicationResponse,
    ApplicationDetailResponse,
    ApplicationListResponse,
    DailyQuotaResponse,
    BatchSubmitRequest,
    BatchDeleteRequest,
    AutomationSubmitResponse,
    AutomationDiagnosticsResponse,
    LinkedInCookieRequest,
)
from app.services import application_service, automation_service
from app.services.application_service import (
    ApplicationPrerequisiteError,
    ApplicationDuplicateError,
    RequestDuplicateError,
    DailyQuotaExceededError,
    InvalidStatusTransitionError,
    InvalidOperationError,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", response_model=ApplicationCreateResponse, status_code=status.HTTP_201_CREATED)
def create_applications(
    data: ApplicationCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create application(s) for the specified job IDs.
    Tailored cover letters are generated synchronously.
    All-or-nothing validation: zero records created on any validation failure.
    """
    try:
        app_ids = application_service.validate_and_create_applications(
            db=db, user=user, job_ids=data.job_ids
        )
        return ApplicationCreateResponse(
            message=f"Successfully created {len(app_ids)} application(s).",
            application_ids=app_ids,
            count=len(app_ids),
        )
    except ApplicationPrerequisiteError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RequestDuplicateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ApplicationDuplicateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DailyQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/quota", response_model=DailyQuotaResponse)
def get_daily_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current UTC calendar day's application limit, usage, and remaining quota."""
    quota_info = application_service.get_daily_quota(db, user.id)
    return DailyQuotaResponse(**quota_info)


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List applications for the current user with optional status filter and pagination."""
    items, total = application_service.list_applications(
        db=db,
        user_id=user.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 1
    return ApplicationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
def get_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get application details with full cover letter and status history timeline."""
    app = application_service.get_application_detail(db, user.id, application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found."
        )
    has_screenshot = bool(app.screenshot_path and os.path.exists(app.screenshot_path))
    res = ApplicationDetailResponse.model_validate(app)
    res.has_screenshot = has_screenshot
    return res


@router.get("/{application_id}/diagnostics", response_model=AutomationDiagnosticsResponse)
def get_application_diagnostics(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve structured diagnostics, action log, and error details for an application."""
    app = application_service.get_application_detail(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    action_log = []
    if app.action_log:
        try:
            action_log = json.loads(app.action_log)
        except Exception:
            pass

    error_details = None
    if app.error_details:
        try:
            error_details = json.loads(app.error_details)
        except Exception:
            pass

    has_screenshot = bool(app.screenshot_path and os.path.exists(app.screenshot_path))

    return AutomationDiagnosticsResponse(
        application_id=app.id,
        execution_id=app.execution_id,
        status=app.status,
        phase=app.error_phase,
        error_type=app.error_type,
        failure_reason=app.failure_reason,
        technical_error=app.technical_error,
        last_action=app.last_action,
        discovery_step=app.discovery_step,
        manual_intervention_required=app.manual_intervention_required,
        has_screenshot=has_screenshot,
        action_log=action_log,
        error_details=error_details,
    )


@router.get("/{application_id}/screenshot")
def get_application_screenshot(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the failure screenshot image captured during automation, if available."""
    app = application_service.get_application_detail(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    if not app.screenshot_path or not os.path.exists(app.screenshot_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No screenshot available for this application."
        )

    return FileResponse(app.screenshot_path, media_type="image/png")


@router.put("/{application_id}/status", response_model=ApplicationDetailResponse)
def update_application_status(
    application_id: int,
    data: ApplicationStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually update application status (Job Seekers may only set: interview, offer, rejected).
    """
    try:
        updated_app = application_service.update_application_status(
            db=db,
            user_id=user.id,
            application_id=application_id,
            new_status=data.status,
            notes=data.notes,
        )
        return updated_app
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{application_id}/cover-letter", response_model=ApplicationDetailResponse)
def update_application_cover_letter(
    application_id: int,
    data: ApplicationCoverLetterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Edit cover letter text. Only permitted when application status is 'ready'.
    """
    try:
        updated_app = application_service.update_cover_letter(
            db=db,
            user_id=user.id,
            application_id=application_id,
            new_cover_letter=data.cover_letter,
        )
        return updated_app
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidOperationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{application_id}", status_code=status.HTTP_200_OK)
def delete_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete an application. Cannot delete while automation is actively running ('applying').
    """
    try:
        application_service.delete_application(db=db, user_id=user.id, application_id=application_id)
        return {"message": "Application deleted successfully.", "application_id": application_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidOperationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/submit", response_model=AutomationSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_application(
    application_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger automated browser submission for a single application (AUT-01).
    Dispatches task in background and returns 202 Accepted.
    """
    app = db.query(Application).filter(Application.id == application_id, Application.user_id == user.id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    if app.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit application with status '{app.status}'. Only 'ready' or 'failed' applications can be submitted or retried."
        )

    background_tasks.add_task(automation_service.run_single_application_automation, application_id)

    return AutomationSubmitResponse(
        message="Application queued for automated submission.",
        application_ids=[application_id],
        status="queued",
    )


@router.post("/{application_id}/retry", response_model=AutomationSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_application(
    application_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry automated browser submission for a failed or ready application.
    """
    app = db.query(Application).filter(Application.id == application_id, Application.user_id == user.id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    if app.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry application with status '{app.status}'. Only 'failed' or 'ready' applications can be retried."
        )

    background_tasks.add_task(automation_service.run_single_application_automation, application_id)

    return AutomationSubmitResponse(
        message="Application queued for automated retry.",
        application_ids=[application_id],
        status="queued",
    )


@router.post("/batch-submit", response_model=AutomationSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def batch_submit_applications(
    data: BatchSubmitRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger sequential batch automation for multiple applications (AUT-02, AUT-03).
    Validates ownership and ready/failed status; dispatches sequential runner in background.
    """
    if not data.application_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No application IDs provided.")

    apps = db.query(Application).filter(
        Application.id.in_(data.application_ids),
        Application.user_id == user.id,
    ).all()

    if len(apps) != len(data.application_ids):
        found_ids = {a.id for a in apps}
        missing_ids = [aid for aid in data.application_ids if aid not in found_ids]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application(s) not found: {missing_ids}")

    not_eligible = [a.id for a in apps if a.status not in ("ready", "failed")]
    if not_eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All applications must be in 'ready' or 'failed' status. Ineligible applications: {not_eligible}"
        )

    background_tasks.add_task(automation_service.run_batch_applications_automation, data.application_ids)

    return AutomationSubmitResponse(
        message=f"Batch automation queued for {len(data.application_ids)} application(s).",
        application_ids=data.application_ids,
        status="queued",
    )


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
def batch_delete_applications(
    data: BatchDeleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Batch delete multiple applications.
    """
    if not data.application_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No application IDs provided.")

    count = application_service.batch_delete_applications(
        db=db, user_id=user.id, application_ids=data.application_ids
    )
    return {"message": f"Successfully deleted {count} application(s).", "count": count}


@router.post("/{application_id}/cancel")
def cancel_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel an ongoing (applying) automated application.
    Terminates the Playwright browser session and resets application status to 'ready'.
    """
    app = db.query(Application).filter(Application.id == application_id, Application.user_id == user.id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    if app.status != "applying":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel application with status '{app.status}'. Only 'applying' applications can be cancelled."
        )

    was_active = automation_service.cancel_application_automation(application_id)
    if not was_active:
        # If not actively in memory (e.g. process was restarted or background worker stopped), reset directly in DB
        app.status = "ready"
        app.failure_reason = "Cancelled by user"
        app.updated_at = datetime.utcnow()
        history = ApplicationStatusHistory(
            application_id=app.id,
            status="ready",
            notes="Application reset to ready upon cancellation request.",
        )
        db.add(history)
        db.commit()
        db.refresh(app)

    return {"message": "Application automation cancellation requested.", "status": "cancelled"}


@router.post("/{application_id}/open-login-browser")
def open_login_browser(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Launch Brave browser with the user's persistent automation profile so they can
    log into LinkedIn, Indeed, etc. All credentials and cookies remain saved permanently.
    """
    app = db.query(Application).filter(Application.id == application_id, Application.user_id == user.id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    app_url = app.job.application_url if (app.job and app.job.application_url and not automation_service._is_auth_redirect_url(app.job.application_url)) else None
    target_url = app_url or (app.job.url if app.job else "https://www.linkedin.com/login")
    automation_service.launch_standalone_browser_for_login(user.id, target_url)

    return {
        "message": "Browser opened for login. Please sign in to your account. Your session and cookies will be saved permanently.",
        "url": target_url,
    }


@router.post("/save-linkedin-cookie")
def save_linkedin_cookie(
    data: LinkedInCookieRequest,
    user: User = Depends(get_current_user),
):
    """
    Save user's li_at session cookie to their persistent automation profile.
    """
    clean_cookie = data.cookie_value.strip()
    automation_service.save_user_linkedin_cookie(user.id, clean_cookie)
    return {"message": "LinkedIn session cookie saved successfully! It will be used for all automated applications."}



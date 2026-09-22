"""CV API endpoints for Job Seekers."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.cv import CVResponse, ParsedDataUpdateRequest
from app.services import cv_service

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/upload", response_model=CVResponse)
def upload_cv(
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cv, is_created = cv_service.save_and_parse_cv(db, user, file)
        # 201 Created for first upload, 200 OK when replacing existing CV
        response.status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK
        return cv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=CVResponse)
def get_cv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return cv_service.get_cv(db, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/parsed-data", response_model=CVResponse)
def update_parsed_data(
    data: ParsedDataUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return cv_service.update_parsed_data(db, user, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("")
def delete_cv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cv_service.delete_cv(db, user)
        return {"message": "CV deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

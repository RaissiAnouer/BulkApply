"""Profile API endpoints for Job Seekers."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileUpdateRequest, ProfileResponse
from app.services import profile_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_or_create_profile(db, user)
    return profile_service.to_profile_response(user, profile)


@router.put("", response_model=ProfileResponse)
def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = profile_service.update_profile(db, user, data)
    return profile_service.to_profile_response(user, profile)

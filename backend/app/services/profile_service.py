"""Business logic for Job Seeker Profiles."""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.schemas.profile import ProfileUpdateRequest, ProfileResponse


def get_or_create_profile(db: Session, user: User) -> JobSeekerProfile:
    """Retrieve existing profile or create a default one for the user."""
    profile = db.query(JobSeekerProfile).filter(JobSeekerProfile.user_id == user.id).first()
    if not profile:
        profile = JobSeekerProfile(
            user_id=user.id,
            full_name=user.name,
            phone=user.phone or "",
            location=user.location or "",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, data: ProfileUpdateRequest) -> JobSeekerProfile:
    """Update profile with validated data."""
    profile = get_or_create_profile(db, user)

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(profile, key, value)

    # Sync primary contact fields back to user record for consistency
    if "full_name" in update_dict and update_dict["full_name"]:
        user.name = update_dict["full_name"]
    if "phone" in update_dict:
        user.phone = update_dict["phone"]
    if "location" in update_dict:
        user.location = update_dict["location"]

    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    db.refresh(user)
    return profile


def to_profile_response(user: User, profile: JobSeekerProfile) -> ProfileResponse:
    """Combine user account metadata with profile data into response."""
    return ProfileResponse(
        id=profile.id,
        user_id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        full_name=profile.full_name,
        phone=profile.phone,
        location=profile.location,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        work_authorization=profile.work_authorization,
        requires_sponsorship=profile.requires_sponsorship,
        years_of_experience=profile.years_of_experience,
        salary_expectation=profile.salary_expectation,
        education_level=profile.education_level,
        languages=profile.languages,
        target_job_title=profile.target_job_title,
        work_preference=profile.work_preference,
        employment_type=profile.employment_type,
        preferred_locations=profile.preferred_locations,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )

"""Auth business logic — registration, login, verification, password reset."""

import secrets
import hashlib
from datetime import datetime, timedelta

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import JWT_SECRET, JWT_EXPIRY_HOURS
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.services.email_service import send_verification_email, send_password_reset_email


# --- Token helpers ---


def _generate_token() -> tuple[str, str]:
    """Generate a cryptographically secure token and its SHA-256 hash.
    Returns (raw_token, token_hash). Only the hash is stored in the database."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def _hash_token(raw_token: str) -> str:
    """Hash a raw token with SHA-256 for database lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_jwt(user: User) -> str:
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# --- Lockout ---

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _is_locked(user: User) -> bool:
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False


def _lockout_remaining_minutes(user: User) -> int:
    if user.locked_until:
        remaining = (user.locked_until - datetime.utcnow()).total_seconds() / 60
        return max(1, int(remaining) + 1)
    return 0


# --- Public functions ---


def register_user(db: Session, name: str, email: str, password: str) -> User:
    """Create a new Job Seeker and send verification email."""
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise ValueError("Email already registered")

    raw_token, token_hash = _generate_token()

    user = User(
        email=email.lower(),
        password_hash=_hash_password(password),
        name=name,
        role="job_seeker",
        verification_token_hash=token_hash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize Job Seeker profile
    profile = JobSeekerProfile(
        user_id=user.id,
        full_name=user.name,
        phone=user.phone or "",
        location=user.location or "",
    )
    db.add(profile)
    db.commit()

    send_verification_email(user.email, raw_token)
    return user


def login_user(db: Session, email: str, password: str) -> tuple[str, User]:
    """Validate credentials and return (jwt_token, user)."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise ValueError("Invalid email or password")

    # Check lockout
    if _is_locked(user):
        minutes = _lockout_remaining_minutes(user)
        raise PermissionError(f"Account locked. Try again in {minutes} minutes")

    # Check password
    if not _verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        db.commit()
        raise ValueError("Invalid email or password")

    # Check active
    if not user.is_active:
        raise PermissionError("Your account has been suspended")

    # Check verified
    if not user.is_verified:
        raise PermissionError("Please verify your email before logging in")

    # Success — reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    token = _create_jwt(user)
    return token, user


def verify_email(db: Session, raw_token: str) -> None:
    """Verify a user's email using the token from the verification link."""
    token_hash = _hash_token(raw_token)
    user = db.query(User).filter(User.verification_token_hash == token_hash).first()
    if not user:
        raise ValueError("Invalid or expired verification token")

    user.is_verified = True
    user.verification_token_hash = None
    db.commit()


def request_password_reset(db: Session, email: str) -> None:
    """Generate a reset token and send it via email.
    Always returns success to prevent email enumeration."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        return  # Silent — don't reveal whether email exists

    raw_token, token_hash = _generate_token()
    user.reset_token_hash = token_hash
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    send_password_reset_email(user.email, raw_token)


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    """Reset a user's password using the token from the reset link."""
    token_hash = _hash_token(raw_token)
    user = db.query(User).filter(User.reset_token_hash == token_hash).first()
    if not user:
        raise ValueError("Invalid or expired reset token")

    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        user.reset_token_hash = None
        user.reset_token_expires = None
        db.commit()
        raise ValueError("Invalid or expired reset token")

    user.password_hash = _hash_password(new_password)
    user.reset_token_hash = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

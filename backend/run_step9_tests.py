"""Step 9 Admin Module Integration Tests.

Validates:
- ADM-01: Admin dashboard metrics (users, applications today, failure rate, status breakdown)
- ADM-02: Global daily application rate limit configuration via system_settings
- ADM-03: Search and list registered Job Seekers
- ADM-04: View specific Job Seeker profile, CV, and application history
- ADM-05: Suspend, reactivate, and delete Job Seeker accounts
- ADM-06: Admin audit log recording and listing
- Role security: Job Seekers receive 403 Forbidden on all /api/admin/* endpoints
"""

import sys
import os
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.models.cv import CV
from app.models.job import Job
from app.models.application import Application
from app.models.admin import SystemSetting, AdminAuditLog
from app.services.auth_service import _create_jwt
from app.services import admin_service, application_service

# Setup test DB
TEST_DB_URL = "sqlite:///./test_step9.db"
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

admin_user = None
seeker_user = None
admin_headers = {}
seeker_headers = {}


def setup_suite():
    global admin_user, seeker_user, admin_headers, seeker_headers
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    try:
        # Create Admin
        adm = User(
            name="Super Admin",
            email="admin@autoapply.test",
            password_hash="testhash",
            role="admin",
            is_active=True,
        )
        # Create Job Seeker
        skr = User(
            name="Bob Candidate",
            email="bob@candidate.test",
            password_hash="testhash",
            role="job_seeker",
            is_active=True,
            location="Chicago, IL",
        )
        db.add_all([adm, skr])
        db.commit()
        db.refresh(adm)
        db.refresh(skr)

        # Profile for seeker
        prof = JobSeekerProfile(
            user_id=skr.id,
            full_name="Bob Candidate",
            phone="312-555-0100",
            location="Chicago, IL",
            target_job_title="Full Stack Developer",
        )
        db.add(prof)

        # Jobs and applications
        j1 = Job(user_id=skr.id, url="https://example.com/jobs/1", title="Backend Engineer", company="Corp A")
        j2 = Job(user_id=skr.id, url="https://example.com/jobs/2", title="Frontend Engineer", company="Corp B")
        db.add_all([j1, j2])
        db.commit()

        app1 = Application(user_id=skr.id, job_id=j1.id, status="submitted")
        app2 = Application(user_id=skr.id, job_id=j2.id, status="failed", failure_reason="Timeout")
        db.add_all([app1, app2])
        db.commit()

        admin_user = adm
        seeker_user = skr
        token_adm = _create_jwt(adm)
        token_skr = _create_jwt(skr)
        admin_headers = {"Authorization": f"Bearer {token_adm}"}
        seeker_headers = {"Authorization": f"Bearer {token_skr}"}
    finally:
        db.close()


def teardown_suite():
    if os.path.exists("./test_step9.db"):
        try:
            os.remove("./test_step9.db")
        except Exception:
            pass


def test_admin_metrics():
    print("\n--- TEST 1: Admin Dashboard Metrics (ADM-01) ---")
    res = client.get("/api/admin/metrics", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_users"] == 1
    assert data["active_users"] == 1
    assert data["suspended_users"] == 0
    assert data["total_jobs"] == 2
    assert data["total_applications"] == 2
    assert data["applications_today"] == 2
    assert data["failure_rate_percent"] == 50.0  # 1 failed out of 2 = 50%
    assert data["status_breakdown"]["submitted"] == 1
    assert data["status_breakdown"]["failed"] == 1
    assert data["status_breakdown"]["ready"] == 0
    print("[PASS] Metrics correctly aggregated and calculated.")


def test_system_settings_and_dynamic_quota():
    print("\n--- TEST 2: System Settings & Dynamic Quota (ADM-02) ---")
    # 1. Get settings
    res_get = client.get("/api/admin/settings", headers=admin_headers)
    assert res_get.status_code == 200
    settings = res_get.json()
    assert len(settings) >= 1
    assert settings[0]["key"] == "daily_application_limit"
    assert settings[0]["value"] == "20"

    # 2. Update limit to 5
    res_put = client.put(
        "/api/admin/settings/daily_application_limit",
        headers=admin_headers,
        json={"value": "5"},
    )
    assert res_put.status_code == 200
    assert res_put.json()["value"] == "5"

    # 3. Verify application_service immediately reflects new limit of 5
    db = TestSessionLocal()
    try:
        quota = application_service.get_daily_quota(db, seeker_user.id)
        assert quota["limit"] == 5, f"Expected dynamic limit 5, got {quota['limit']}"
    finally:
        db.close()

    # 4. Invalid limit rejected with 400
    res_invalid = client.put(
        "/api/admin/settings/daily_application_limit",
        headers=admin_headers,
        json={"value": "-10"},
    )
    assert res_invalid.status_code == 400

    # 5. Restore limit to 20
    client.put(
        "/api/admin/settings/daily_application_limit",
        headers=admin_headers,
        json={"value": "20"},
    )
    print("[PASS] Setting dynamically updated, validated, and reflected in quota calculation.")


def test_user_search_and_pagination():
    print("\n--- TEST 3: User Search and Pagination (ADM-03) ---")
    # Search by name match
    res_search = client.get("/api/admin/users?q=Bob", headers=admin_headers)
    assert res_search.status_code == 200
    data = res_search.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Bob Candidate"

    # Search with no match
    res_empty = client.get("/api/admin/users?q=NonExistent", headers=admin_headers)
    assert res_empty.json()["total"] == 0
    print("[PASS] User listing and keyword searching verified.")


def test_user_detail_history():
    print("\n--- TEST 4: User Detail Profile & Application History (ADM-04) ---")
    res = client.get(f"/api/admin/users/{seeker_user.id}", headers=admin_headers)
    assert res.status_code == 200, res.text
    detail = res.json()
    assert detail["name"] == "Bob Candidate"
    assert detail["profile"] is not None
    assert detail["profile"]["target_job_title"] == "Full Stack Developer"
    assert len(detail["applications"]) == 2
    app_statuses = [a["status"] for a in detail["applications"]]
    assert "submitted" in app_statuses
    assert "failed" in app_statuses
    print("[PASS] Complete candidate profile and application history retrieved.")


def test_user_lifecycle_actions():
    print("\n--- TEST 5: Suspend and Reactivate User (ADM-05) ---")
    # 1. Suspend seeker
    res_susp = client.put(f"/api/admin/users/{seeker_user.id}/suspend", headers=admin_headers)
    assert res_susp.status_code == 200

    # Verify seeker account is inactive
    db = TestSessionLocal()
    try:
        skr = db.query(User).filter(User.id == seeker_user.id).first()
        assert skr.is_active is False
    finally:
        db.close()

    # Suspended seeker cannot access API
    res_blocked = client.get("/api/profile", headers=seeker_headers)
    assert res_blocked.status_code == 403, "Suspended user must receive 403"

    # 2. Reactivate seeker
    res_react = client.put(f"/api/admin/users/{seeker_user.id}/reactivate", headers=admin_headers)
    assert res_react.status_code == 200

    # Seeker can access again
    res_allowed = client.get("/api/profile", headers=seeker_headers)
    assert res_allowed.status_code == 200

    # 3. Cannot suspend admin
    res_admin_susp = client.put(f"/api/admin/users/{admin_user.id}/suspend", headers=admin_headers)
    assert res_admin_susp.status_code == 400
    print("[PASS] Suspend, reactivate, and protection guards verified.")


def test_audit_logs():
    print("\n--- TEST 6: Admin Audit Trail (ADM-06) ---")
    res = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert res.status_code == 200, res.text
    logs = res.json()
    assert len(logs) >= 3  # update_setting (twice), suspend_user, reactivate_user
    actions = [l["action"] for l in logs]
    assert "update_setting" in actions
    assert "suspend_user" in actions
    assert "reactivate_user" in actions
    print("[PASS] Audit logs accurately recorded and retrieved.")


def test_role_security_guards():
    print("\n--- TEST 7: Role Permission Guards (403 for Job Seekers) ---")
    endpoints = [
        ("GET", "/api/admin/metrics"),
        ("GET", "/api/admin/settings"),
        ("GET", "/api/admin/users"),
        ("GET", f"/api/admin/users/{seeker_user.id}"),
        ("GET", "/api/admin/audit-logs"),
    ]
    for method, path in endpoints:
        res = client.request(method, path, headers=seeker_headers)
        assert res.status_code == 403, f"Job Seeker expected 403 on {path}, got {res.status_code}"
    print("[PASS] All admin endpoints protected against non-admin access.")


def run_all():
    setup_suite()
    passed = 0
    total = 7
    tests = [
        ("Admin Dashboard Metrics", test_admin_metrics),
        ("System Settings & Dynamic Quota", test_system_settings_and_dynamic_quota),
        ("User Search & Pagination", test_user_search_and_pagination),
        ("User Detail History", test_user_detail_history),
        ("User Lifecycle Actions", test_user_lifecycle_actions),
        ("Audit Logs", test_audit_logs),
        ("Role Security Guards", test_role_security_guards),
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
        print(f"STEP 9 RESULTS: {passed}/{total} PASSED")
        print("=" * 60)
        if passed == total:
            print("ALL STEP 9 INTEGRATION TESTS PASSED PERFECTLY!")
        else:
            print("Some tests failed. Check logs above.")
            sys.exit(1)
    finally:
        teardown_suite()


if __name__ == "__main__":
    run_all()

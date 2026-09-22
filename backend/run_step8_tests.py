"""Step 8 Notifications Module Integration Tests.

Validates:
- NTF-01: In-app notification on application submitted
- NTF-02: In-app notification on application failed
- NTF-03: In-app notification on manual intervention required (CAPTCHA)
- NTF-04: Email alert dispatched for failures and manual intervention
- NTF-05: Unread count endpoint for navbar bell badge
- NTF-06: Notification list with pagination and filtering
- NTF-07: Mark notification(s) as read (single and batch)
- NTF-08: Email notification preference toggle
- User isolation: Users only see and modify their own notifications
"""

import sys
import os
import io

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
from app.models.notification import Notification
from app.models.job import Job
from app.models.application import Application
from app.services.auth_service import _create_jwt
from app.services import notification_service

# Setup isolated test DB
TEST_DB_URL = "sqlite:///./test_step8.db"
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

user_a = None
user_b = None
token_a = None
token_b = None
headers_a = {}
headers_b = {}


def setup_suite():
    global user_a, user_b, token_a, token_b, headers_a, headers_b
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    try:
        u_a = User(
            name="Alice Candidate",
            email="alice@notifications.test",
            password_hash="testhash",
            role="job_seeker",
            is_active=True,
            email_notifications_enabled=True,
        )
        u_b = User(
            name="Bob Candidate",
            email="bob@notifications.test",
            password_hash="testhash",
            role="job_seeker",
            is_active=True,
            email_notifications_enabled=False,
        )
        db.add_all([u_a, u_b])
        db.commit()
        db.refresh(u_a)
        db.refresh(u_b)

        user_a = u_a
        user_b = u_b
        token_a = _create_jwt(u_a)
        token_b = _create_jwt(u_b)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
    finally:
        db.close()


def teardown_suite():
    if os.path.exists("./test_step8.db"):
        try:
            os.remove("./test_step8.db")
        except Exception:
            pass


def test_submission_notification():
    print("\n--- TEST 1: In-App Notification on Application Submitted (NTF-01) ---")
    db = TestSessionLocal()
    try:
        notif = notification_service.create_notification(
            db=db,
            user_id=user_a.id,
            type="app_submitted",
            title="Application Submitted",
            message="Your application for Senior Python Engineer at TechCorp was submitted!",
        )
        assert notif.id is not None
        assert notif.type == "app_submitted"
        assert notif.is_read is False
        assert notif.email_sent is False  # NTF-04: submitted does not dispatch email alert, only in-app
        print("[PASS] Submission notification created successfully.")
    finally:
        db.close()


def test_failure_and_email_alert():
    print("\n--- TEST 2: In-App + Email Alert on Failure & CAPTCHA (NTF-02, NTF-03, NTF-04) ---")
    db = TestSessionLocal()
    try:
        # Capture stdout to verify email alert output
        captured_out = io.StringIO()
        sys_stdout_orig = sys.stdout
        sys.stdout = captured_out
        try:
            notif_fail = notification_service.create_notification(
                db=db,
                user_id=user_a.id,
                type="app_failed",
                title="Application Failed",
                message="Submission timed out after 120 seconds.",
            )
            notif_captcha = notification_service.create_notification(
                db=db,
                user_id=user_a.id,
                type="manual_intervention",
                title="Manual Intervention Required",
                message="CAPTCHA challenge detected on application form.",
            )
        finally:
            sys.stdout = sys_stdout_orig

        output = captured_out.getvalue()
        assert notif_fail.email_sent is True, "Expected email_sent True for failure when enabled"
        assert notif_captcha.email_sent is True, "Expected email_sent True for CAPTCHA when enabled"
        assert "[EMAIL ALERT]" in output, "Expected [EMAIL ALERT] printed to console"
        assert "alice@notifications.test" in output
        print("[PASS] Failure and CAPTCHA alerts created in-app and dispatched email alert.")
    finally:
        db.close()


def test_opt_out_email_alert():
    print("\n--- TEST 3: Email Alert Opt-Out Respected (NTF-08) ---")
    db = TestSessionLocal()
    try:
        # User B has email_notifications_enabled = False
        captured_out = io.StringIO()
        sys_stdout_orig = sys.stdout
        sys.stdout = captured_out
        try:
            notif_b = notification_service.create_notification(
                db=db,
                user_id=user_b.id,
                type="app_failed",
                title="Application Failed",
                message="Error on submission.",
            )
        finally:
            sys.stdout = sys_stdout_orig

        output = captured_out.getvalue()
        assert notif_b.is_read is False
        assert notif_b.email_sent is False, "Email should NOT be sent when opt-out"
        assert "[EMAIL ALERT]" not in output, "No email should be printed when user opted out"
        print("[PASS] User with email opt-out receives in-app alert with email_sent=False.")
    finally:
        db.close()


def test_unread_count_endpoint():
    print("\n--- TEST 4: Unread Count Endpoint for Bell Badge (NTF-05) ---")
    res = client.get("/api/notifications/unread-count", headers=headers_a)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["unread_count"] == 3, f"Expected 3 unread for Alice, got {data['unread_count']}"
    print("[PASS] /api/notifications/unread-count accurately reports 3 unread.")


def test_list_notifications_and_filtering():
    print("\n--- TEST 5: List Notifications & Unread Filter (NTF-06) ---")
    res = client.get("/api/notifications?page=1&page_size=10", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert data["unread_count"] == 3
    assert len(data["items"]) == 3

    # Filter unread
    res_unread = client.get("/api/notifications?unread_only=true", headers=headers_a)
    assert res_unread.status_code == 200
    assert len(res_unread.json()["items"]) == 3
    print("[PASS] /api/notifications paginates and filters correctly.")


def test_mark_as_read_endpoints():
    print("\n--- TEST 6: Mark Single and Mark All As Read (NTF-07) ---")
    db = TestSessionLocal()
    try:
        # Get one of Alice's notifications
        first_notif = db.query(Notification).filter(Notification.user_id == user_a.id).first()
        notif_id = first_notif.id

        # 1. Mark single as read
        res_single = client.put(f"/api/notifications/{notif_id}/read", headers=headers_a)
        assert res_single.status_code == 200, res_single.text
        assert res_single.json()["is_read"] is True

        # Verify unread count decremented to 2
        res_count = client.get("/api/notifications/unread-count", headers=headers_a)
        assert res_count.json()["unread_count"] == 2

        # 2. Mark all as read
        res_all = client.put("/api/notifications/mark-all-read", headers=headers_a)
        assert res_all.status_code == 200
        assert res_all.json()["count"] == 2

        # Verify unread count is now 0
        res_count_0 = client.get("/api/notifications/unread-count", headers=headers_a)
        assert res_count_0.json()["unread_count"] == 0

        # Verify unread filter returns 0 items
        res_filter = client.get("/api/notifications?unread_only=true", headers=headers_a)
        assert len(res_filter.json()["items"]) == 0
        print("[PASS] Single mark-read and bulk mark-all-read work as expected.")
    finally:
        db.close()


def test_preferences_endpoint():
    print("\n--- TEST 7: Notification Preferences (NTF-08) ---")
    # 1. Get current preferences for Alice (True)
    res_get = client.get("/api/notifications/preferences", headers=headers_a)
    assert res_get.status_code == 200
    assert res_get.json()["email_notifications_enabled"] is True

    # 2. Update preference to False
    res_put = client.put(
        "/api/notifications/preferences",
        headers=headers_a,
        json={"email_notifications_enabled": False},
    )
    assert res_put.status_code == 200
    assert res_put.json()["email_notifications_enabled"] is False

    # 3. Verify updated in database
    res_verify = client.get("/api/notifications/preferences", headers=headers_a)
    assert res_verify.json()["email_notifications_enabled"] is False

    # 4. Toggle back to True
    client.put(
        "/api/notifications/preferences",
        headers=headers_a,
        json={"email_notifications_enabled": True},
    )
    print("[PASS] Notification email preferences can be retrieved and updated.")


def test_user_isolation():
    print("\n--- TEST 8: User Isolation & Security ---")
    db = TestSessionLocal()
    try:
        # User A's notification
        alice_notif = db.query(Notification).filter(Notification.user_id == user_a.id).first()

        # User B tries to mark Alice's notification as read -> 404
        res_cross = client.put(f"/api/notifications/{alice_notif.id}/read", headers=headers_b)
        assert res_cross.status_code == 404

        # User B cannot see Alice's notifications
        res_list_b = client.get("/api/notifications", headers=headers_b)
        items_b = res_list_b.json()["items"]
        for item in items_b:
            assert item["user_id"] == user_b.id
        print("[PASS] Cross-user access properly blocked with 404.")
    finally:
        db.close()


def run_all():
    setup_suite()
    passed = 0
    total = 8
    tests = [
        ("Submission Notification", test_submission_notification),
        ("Failure & CAPTCHA Email Alert", test_failure_and_email_alert),
        ("Email Alert Opt-Out", test_opt_out_email_alert),
        ("Unread Count Endpoint", test_unread_count_endpoint),
        ("List & Filtering", test_list_notifications_and_filtering),
        ("Mark as Read Endpoints", test_mark_as_read_endpoints),
        ("Preferences Endpoint", test_preferences_endpoint),
        ("User Isolation", test_user_isolation),
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
        print(f"STEP 8 RESULTS: {passed}/{total} PASSED")
        print("=" * 60)
        if passed == total:
            print("ALL STEP 8 INTEGRATION TESTS PASSED PERFECTLY!")
        else:
            print("Some tests failed. Check logs above.")
            sys.exit(1)
    finally:
        teardown_suite()


if __name__ == "__main__":
    run_all()

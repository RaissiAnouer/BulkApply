"""Step 4 Automated Comprehensive Test Suite."""

import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

BASE_URL = "http://localhost:8000"


def request(method, path, data=None, headers=None, is_json=True):
    url = f"{BASE_URL}{path}"
    req_headers = headers.copy() if headers else {}
    body = None

    if data is not None:
        if is_json:
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        else:
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            err_json = json.loads(content)
        except Exception:
            err_json = {"detail": content}
        return e.code, err_json


def upload_multipart(path, file_path, headers=None):
    url = f"{BASE_URL}{path}"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req_headers = headers.copy() if headers else {}
    req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            err_json = json.loads(content)
        except Exception:
            err_json = {"detail": content}
        return e.code, err_json


def run_tests():
    print("==========================================")
    print("     STEP 4 VERIFICATION TEST SUITE       ")
    print("==========================================")

    # 1. Health check regression
    st, data = request("GET", "/api/health")
    assert st == 200 and data.get("status") == "ok", "Step 1 Health failed"
    print("[PASS] Step 1 Health Check verified.")

    # 2. Admin Login regression
    st, data = request("POST", "/api/auth/login", {"email": "admin@autoapply.com", "password": "Admin123!"})
    assert st == 200, "Admin login failed"
    admin_token = data["access_token"]
    print("[PASS] Step 2 Admin Login verified.")

    # 3. Register Seeker 1
    ts = int(time.time())
    email1 = f"cv_seeker_{ts}@example.com"
    st, _ = request("POST", "/api/auth/register", {"name": "Morgan Davis", "email": email1, "password": "MorganPass123!"})
    assert st == 201, "Registration failed"

    # Verify email via backend DB update for speed
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.cv import CV

    db = SessionLocal()
    u1 = db.query(User).filter(User.email == email1).first()
    u1.is_verified = True
    db.commit()
    user1_id = u1.id
    db.close()

    st, data = request("POST", "/api/auth/login", {"email": email1, "password": "MorganPass123!"})
    assert st == 200, "Seeker 1 login failed"
    token1 = data["access_token"]
    auth1 = {"Authorization": f"Bearer {token1}"}
    print(f"[PASS] Seeker 1 created and logged in (ID {user1_id}).")

    # 4. Register Seeker 2 (for isolation check)
    email2 = f"cv_seeker2_{ts}@example.com"
    request("POST", "/api/auth/register", {"name": "Sam Taylor", "email": email2, "password": "SamPass123!"})
    db = SessionLocal()
    u2 = db.query(User).filter(User.email == email2).first()
    u2.is_verified = True
    db.commit()
    user2_id = u2.id
    db.close()
    _, data = request("POST", "/api/auth/login", {"email": email2, "password": "SamPass123!"})
    token2 = data["access_token"]
    auth2 = {"Authorization": f"Bearer {token2}"}
    print(f"[PASS] Seeker 2 created and logged in (ID {user2_id}).")

    # 5. Test PDF Upload (Initial -> 201 Created)
    print("\n--- Testing PDF Upload ---")
    st, cv_data = upload_multipart("/api/cv/upload", "test_fixtures/sample_resume.pdf", auth1)
    assert st == 201, f"Expected 201 Created on first upload, got {st}: {cv_data}"
    assert cv_data["file_name"] == "sample_resume.pdf"
    assert cv_data["file_type"] == "pdf"
    assert cv_data["file_size"] > 0
    print(f"[PASS] Initial PDF upload returned 201 Created.")

    # Check physical file exists
    db = SessionLocal()
    db_cv = db.query(CV).filter(CV.user_id == user1_id).first()
    assert db_cv is not None, "CV record not found in DB"
    initial_file_path = Path(db_cv.file_path)
    assert initial_file_path.exists(), f"Physical file does not exist: {initial_file_path}"
    assert "cv_" in initial_file_path.name, "File name should use secure generated name"
    db.close()
    print(f"[PASS] Physical file saved with secure UUID: {initial_file_path.name}")

    # 6. Verify Parsed Data
    parsed = cv_data["parsed_data"]
    assert parsed is not None, "Parsed data is None"
    assert "Python" in parsed["skills"], "Skills should contain Python"
    assert len(parsed["skills"]) >= 3, "Multiple skills parsed"
    assert len(parsed["work_experience"]) > 0, "Work experience parsed"
    assert len(parsed["education"]) > 0, "Education parsed"
    print(f"[PASS] Resume parsing verified: Skills={parsed['skills']}, Roles={len(parsed['work_experience'])}, Edu={len(parsed['education'])}")

    # 7. Test GET /api/cv
    print("\n--- Testing GET /api/cv ---")
    st, get_data = request("GET", "/api/cv", headers=auth1)
    assert st == 200, f"Expected 200, got {st}"
    assert get_data["id"] == cv_data["id"]
    print("[PASS] GET /api/cv returned active CV details.")

    # 8. Test PUT /api/cv/parsed-data (Manual Corrections)
    print("\n--- Testing Manual Corrections ---")
    corrections = {
        "contact_info": {
            "full_name": "Jane C. Candidate",
            "email": "jane.c@example.com",
            "phone": "+1 555-9999",
            "location": "Austin, TX",
        },
        "skills": ["Python", "FastAPI", "React", "TypeScript", "Docker", "PostgreSQL", "AWS"],
        "work_experience": [
            {
                "company": "Tech Innovators Inc",
                "title": "Lead Backend Engineer",
                "start_date": "2021",
                "end_date": "Present",
                "description": "Architected distributed services.",
            }
        ],
        "education": [
            {
                "institution": "University of Texas at Austin",
                "degree": "B.S. in Computer Science",
                "graduation_year": "2020",
            }
        ],
    }
    st, updated_cv = request("PUT", "/api/cv/parsed-data", corrections, headers=auth1)
    assert st == 200, f"Expected 200, got {st}"
    assert updated_cv["parsed_data"]["contact_info"]["full_name"] == "Jane C. Candidate"
    assert "AWS" in updated_cv["parsed_data"]["skills"]
    assert updated_cv["parsed_data"]["work_experience"][0]["title"] == "Lead Backend Engineer"
    print("[PASS] Manual corrections saved and verified.")

    # 9. Test Invalid File Type
    print("\n--- Testing Invalid File Type ---")
    st, err_data = upload_multipart("/api/cv/upload", "test_fixtures/not_a_cv.txt", auth1)
    assert st == 400, f"Expected 400 for txt file, got {st}"
    assert "Only PDF and DOCX" in err_data["detail"]
    print("[PASS] Invalid file rejected with 400 Bad Request.")

    # 10. Test Oversized File (> 5MB)
    print("\n--- Testing Oversized File ---")
    st, err_data = upload_multipart("/api/cv/upload", "test_fixtures/oversized_resume.pdf", auth1)
    assert st == 400, f"Expected 400 for >5MB file, got {st}"
    assert "exceeds the 5 MB limit" in err_data["detail"]
    print("[PASS] Oversized file rejected with 400 Bad Request.")

    # 11. Test Failed Replacement Preserves Existing CV (User Correction #1)
    print("\n--- Testing Failed Replacement Atomic Safety ---")
    # Verify existing CV is still intact before attempt
    st, before_data = request("GET", "/api/cv", headers=auth1)
    assert st == 200
    assert before_data["file_name"] == "sample_resume.pdf"
    assert initial_file_path.exists(), "Original physical file should still exist"

    # Attempt replacement with invalid file
    st, _ = upload_multipart("/api/cv/upload", "test_fixtures/not_a_cv.txt", auth1)
    assert st == 400

    # Verify existing CV is still 100% intact after failed attempt
    st, after_data = request("GET", "/api/cv", headers=auth1)
    assert st == 200
    assert after_data["file_name"] == "sample_resume.pdf"
    assert initial_file_path.exists(), "Original physical file must remain intact!"
    print("[PASS] Atomic safety verified: Failed replacement preserved original CV file and record.")

    # 12. Test Valid Replacement with DOCX (Returns 200 OK)
    print("\n--- Testing Valid Replacement with DOCX ---")
    st, replaced_cv = upload_multipart("/api/cv/upload", "test_fixtures/sample_resume.docx", auth1)
    assert st == 200, f"Expected 200 OK on replacement, got {st}"
    assert replaced_cv["file_name"] == "sample_resume.docx"
    assert replaced_cv["file_type"] == "docx"

    # Verify old physical file was cleaned up and new file exists
    assert not initial_file_path.exists(), "Old physical file should be deleted upon successful replacement"
    db = SessionLocal()
    db_cv2 = db.query(CV).filter(CV.user_id == user1_id).first()
    new_file_path = Path(db_cv2.file_path)
    assert new_file_path.exists(), "New physical file must exist"
    db.close()
    print("[PASS] Replacement succeeded (200 OK): Old file deleted, new file stored.")

    # 13. Test One Active CV Constraint
    db = SessionLocal()
    cv_count = db.query(CV).filter(CV.user_id == user1_id).count()
    assert cv_count == 1, f"Expected exactly 1 CV for user, found {cv_count}"
    db.close()
    print("[PASS] One-active-CV constraint verified (exactly 1 record in DB).")

    # 14. Test Cross-User Isolation & Authorization
    print("\n--- Testing Cross-User Isolation ---")
    # Seeker 2 has not uploaded a CV -> should get 404
    st, _ = request("GET", "/api/cv", headers=auth2)
    assert st == 404, f"Seeker 2 should get 404, got {st}"

    # Unauthenticated request -> 401/403
    st, _ = request("GET", "/api/cv")
    assert st in (401, 403), f"Unauthenticated request should fail, got {st}"
    print("[PASS] Cross-user isolation verified: Seeker 2 cannot access Seeker 1's CV.")

    # 15. Test CV Deletion
    print("\n--- Testing CV Deletion ---")
    st, del_resp = request("DELETE", "/api/cv", headers=auth1)
    assert st == 200, f"Expected 200 on delete, got {st}"
    assert not new_file_path.exists(), "Physical file must be unlinked from disk upon deletion"

    # Verify subsequent GET returns 404
    st, _ = request("GET", "/api/cv", headers=auth1)
    assert st == 404, "Subsequent GET after deletion should return 404"
    print("[PASS] CV deletion verified: Physical file unlinked and 404 returned.")

    # 16. Regression: Step 3 Profile & Admin
    print("\n--- Testing Step 3 Profile & Admin Regression ---")
    st, prof = request("GET", "/api/profile", headers=auth1)
    assert st == 200 and prof["full_name"] == "Morgan Davis"
    st, admin_users = request("GET", "/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert st == 200 and len(admin_users) >= 2
    print("[PASS] Step 3 Profile & Admin functionality 100% operational.")

    print("\n==========================================")
    print("   ALL STEP 4 TESTS PASSED (16/16)        ")
    print("==========================================")


if __name__ == "__main__":
    run_tests()

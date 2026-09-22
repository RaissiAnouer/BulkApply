"""Step 5 Automated Comprehensive Test Suite."""

import time
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.job import Job

client = TestClient(app)


def run_tests():
    print("==========================================")
    print("     STEP 5 VERIFICATION TEST SUITE       ")
    print("==========================================")

    # 0. Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # 1. Health check regression
    res = client.get("/api/health")
    assert res.status_code == 200 and res.json().get("status") == "ok", "Step 1 Health failed"
    print("[PASS] Step 1 Health Check verified.")

    # 2. Auth Protection Guards
    for method, path, body in [
        ("post", "/api/jobs/extract", {"url": "https://example.com"}),
        ("post", "/api/jobs", {"url": "https://example.com"}),
        ("get", "/api/jobs", None),
        ("get", "/api/jobs/999", None),
        ("put", "/api/jobs/999", {"title": "Test"}),
        ("delete", "/api/jobs/999", None),
    ]:
        func = getattr(client, method)
        kwargs = {"json": body} if body else {}
        resp = func(path, **kwargs)
        assert resp.status_code in (401, 403), f"{method.upper()} {path} expected 401/403, got {resp.status_code}"
    print("[PASS] Step 2 Auth Guards (401/403 Unauthorized) verified.")

    # 3. Create test users
    ts = int(time.time())
    email1 = f"job_seeker1_{ts}@example.com"
    email2 = f"job_seeker2_{ts}@example.com"

    client.post("/api/auth/register", json={"name": "Alex Hunter", "email": email1, "password": "Password123!"})
    client.post("/api/auth/register", json={"name": "Jordan Lee", "email": email2, "password": "Password123!"})

    db = SessionLocal()
    u1 = db.query(User).filter(User.email == email1).first()
    u2 = db.query(User).filter(User.email == email2).first()
    u1.is_verified = True
    u2.is_verified = True
    db.commit()
    u1_id = u1.id
    u2_id = u2.id
    db.close()

    res1 = client.post("/api/auth/login", json={"email": email1, "password": "Password123!"})
    token1 = res1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    res2 = client.post("/api/auth/login", json={"email": email2, "password": "Password123!"})
    token2 = res2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    print(f"[PASS] Created and authenticated test users: Seeker 1 (ID {u1_id}), Seeker 2 (ID {u2_id}).")

    # 4. Job Extraction Endpoint Validation
    invalid_url_res = client.post("/api/jobs/extract", json={"url": "not-a-valid-url"}, headers=headers1)
    assert invalid_url_res.status_code == 422, f"Expected 422 for invalid URL, got {invalid_url_res.status_code}"
    print("[PASS] Extract validation rejects invalid URLs.")

    # 5. Job Creation (POST /api/jobs)
    job_payload_1 = {
        "url": f"https://techjobs.example.com/posting-{ts}-1",
        "title": "Senior Python Backend Engineer",
        "company": "NeuralSystems AI",
        "location": "San Francisco, CA",
        "work_type": "remote",
        "experience_level": "senior",
        "skills": "Python, FastAPI, PostgreSQL, Docker, Redis",
        "salary": "$160,000 - $190,000",
        "description": "Architect high-performance distributed AI services.",
        "application_url": f"https://techjobs.example.com/posting-{ts}-1/apply",
        "application_method": "url",
    }
    create_res_1 = client.post("/api/jobs", json=job_payload_1, headers=headers1)
    assert create_res_1.status_code == 201, f"Job creation failed: {create_res_1.text}"
    job_1_data = create_res_1.json()
    job_1_id = job_1_data["id"]
    assert job_1_data["title"] == job_payload_1["title"]
    assert job_1_data["company"] == job_payload_1["company"]
    assert job_1_data["work_type"] == "remote"
    assert job_1_data["experience_level"] == "senior"
    assert job_1_data["status"] == "ready"
    assert job_1_data["user_id"] == u1_id
    print(f"[PASS] Successfully created Job #{job_1_id} for Seeker 1.")

    # 6. Duplicate URL prevention per user (409 Conflict)
    dup_res = client.post("/api/jobs", json=job_payload_1, headers=headers1)
    assert dup_res.status_code == 409, f"Expected 409 on duplicate URL, got {dup_res.status_code}"
    print("[PASS] Duplicate URL rejected with 409 Conflict for same user.")

    # 7. User-scoped uniqueness: Seeker 2 can save the same URL
    s2_dup_res = client.post("/api/jobs", json=job_payload_1, headers=headers2)
    assert s2_dup_res.status_code == 201, f"Seeker 2 should be able to save same URL, got {s2_dup_res.status_code}"
    s2_job_id = s2_dup_res.json()["id"]
    assert s2_dup_res.json()["user_id"] == u2_id
    print(f"[PASS] User-scoped uniqueness verified: Seeker 2 saved Job #{s2_job_id} with same URL.")

    # 8. Create additional jobs for Seeker 1 to test search, filtering, and sorting
    job_payload_2 = {
        "url": f"https://techjobs.example.com/posting-{ts}-2",
        "title": "Junior Frontend Developer",
        "company": "PixelCraft Studio",
        "location": "Austin, TX",
        "work_type": "onsite",
        "experience_level": "entry",
        "skills": "React, TypeScript, CSS, HTML",
        "salary": "$75,000 - $85,000",
        "description": "Design dynamic responsive client-side web components.",
    }
    job_payload_3 = {
        "url": f"https://techjobs.example.com/posting-{ts}-3",
        "title": "Fullstack Cloud Architect",
        "company": "Apex Cloud Systems",
        "location": "New York, NY",
        "work_type": "hybrid",
        "experience_level": "lead",
        "skills": "Go, Kubernetes, AWS, GraphQL",
        "salary": "$200,000 - $240,000",
        "description": "Lead enterprise cloud migration and microservices orchestration.",
    }
    res_j2 = client.post("/api/jobs", json=job_payload_2, headers=headers1)
    res_j3 = client.post("/api/jobs", json=job_payload_3, headers=headers1)
    assert res_j2.status_code == 201 and res_j3.status_code == 201
    job_2_id = res_j2.json()["id"]
    job_3_id = res_j3.json()["id"]
    print(f"[PASS] Created Job #{job_2_id} and #{job_3_id} for Seeker 1.")

    # 9. List & Pagination verification
    list_res = client.get("/api/jobs", headers=headers1)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 3
    assert len(list_data["items"]) == 3
    print("[PASS] List returns all 3 jobs for Seeker 1.")

    # Pagination: page_size=2
    page1_res = client.get("/api/jobs?page=1&page_size=2", headers=headers1)
    assert page1_res.status_code == 200
    p1_data = page1_res.json()
    assert len(p1_data["items"]) == 2
    assert p1_data["total_pages"] == 2
    assert p1_data["page"] == 1

    page2_res = client.get("/api/jobs?page=2&page_size=2", headers=headers1)
    assert page2_res.status_code == 200
    p2_data = page2_res.json()
    assert len(p2_data["items"]) == 1
    assert p2_data["page"] == 2
    print("[PASS] Pagination (page 1 & page 2) verified.")

    # 10. Search filtering
    search_res = client.get("/api/jobs?search=Python", headers=headers1)
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert s_data["total"] == 1
    assert s_data["items"][0]["id"] == job_1_id

    search_co = client.get("/api/jobs?search=PixelCraft", headers=headers1)
    assert search_co.json()["total"] == 1
    assert search_co.json()["items"][0]["id"] == job_2_id
    print("[PASS] Search filter by title/company/skills verified.")

    # 11. Work type & Experience level filtering
    filter_remote = client.get("/api/jobs?work_type=remote", headers=headers1)
    assert filter_remote.json()["total"] == 1
    assert filter_remote.json()["items"][0]["id"] == job_1_id

    filter_entry = client.get("/api/jobs?experience_level=entry", headers=headers1)
    assert filter_entry.json()["total"] == 1
    assert filter_entry.json()["items"][0]["id"] == job_2_id
    print("[PASS] Filtering by work_type and experience_level verified.")

    # 12. Sorting
    sort_asc = client.get("/api/jobs?sort_by=title&sort_order=asc", headers=headers1)
    titles_asc = [item["title"] for item in sort_asc.json()["items"]]
    assert titles_asc == sorted(titles_asc), f"Titles not sorted ascending: {titles_asc}"

    sort_desc = client.get("/api/jobs?sort_by=title&sort_order=desc", headers=headers1)
    titles_desc = [item["title"] for item in sort_desc.json()["items"]]
    assert titles_desc == sorted(titles_desc, reverse=True), f"Titles not sorted descending: {titles_desc}"
    print("[PASS] Sorting by title (asc/desc) verified.")

    # 13. Data Isolation: Seeker 2 only sees their own job
    s2_list = client.get("/api/jobs", headers=headers2)
    assert s2_list.status_code == 200
    assert s2_list.json()["total"] == 1
    assert s2_list.json()["items"][0]["id"] == s2_job_id
    print("[PASS] Data isolation verified: Seeker 2 only sees their own jobs.")

    # 14. Get Job Detail (GET /api/jobs/{id})
    get_res = client.get(f"/api/jobs/{job_1_id}", headers=headers1)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Senior Python Backend Engineer"

    # 404 for non-existent job
    assert client.get("/api/jobs/99999", headers=headers1).status_code == 404

    # 403 for Seeker 2 attempting to view Seeker 1's job
    cross_view = client.get(f"/api/jobs/{job_1_id}", headers=headers2)
    assert cross_view.status_code in (403, 404), f"Expected 403/404 on cross-user view, got {cross_view.status_code}"
    print("[PASS] Get job details and cross-user view protection verified.")

    # 15. Update Job (PUT /api/jobs/{id})
    update_payload = {
        "title": "Principal Python Systems Architect",
        "salary": "$210,000 - $250,000",
        "status": "applied",
    }
    upd_res = client.put(f"/api/jobs/{job_1_id}", json=update_payload, headers=headers1)
    assert upd_res.status_code == 200
    upd_data = upd_res.json()
    assert upd_data["title"] == "Principal Python Systems Architect"
    assert upd_data["salary"] == "$210,000 - $250,000"
    assert upd_data["status"] == "applied"
    assert upd_data["company"] == "NeuralSystems AI"  # Unmodified field preserved

    # Cross-user update blocked (403 or 404)
    cross_upd = client.put(f"/api/jobs/{job_1_id}", json={"title": "Hacked Title"}, headers=headers2)
    assert cross_upd.status_code in (403, 404), f"Expected 403/404 on cross-user update, got {cross_upd.status_code}"
    print("[PASS] Update job and cross-user edit protection verified.")

    # 16. Delete Job (DELETE /api/jobs/{id})
    # Cross-user delete blocked (403 or 404)
    cross_del = client.delete(f"/api/jobs/{job_1_id}", headers=headers2)
    assert cross_del.status_code in (403, 404), f"Expected 403/404 on cross-user delete, got {cross_del.status_code}"

    # Valid delete
    del_res = client.delete(f"/api/jobs/{job_1_id}", headers=headers1)
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json().get("message", "")

    # Verification that job is gone
    assert client.get(f"/api/jobs/{job_1_id}", headers=headers1).status_code == 404

    # List total decreased
    assert client.get("/api/jobs", headers=headers1).json()["total"] == 2
    print("[PASS] Delete job and cross-user delete protection verified.")

    print("\n==========================================")
    print("  ALL STEP 5 AUTOMATED TESTS PASSED!     ")
    print("==========================================")


if __name__ == "__main__":
    run_tests()

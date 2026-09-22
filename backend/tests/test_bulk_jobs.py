"""Test bulk job URLs extraction and batch saving."""

import asyncio
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.job import Job
from app.schemas.job import JobSaveRequest, BulkJobSaveRequest
from app.services import job_service


def test_bulk_operations():
    # Setup test in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        # Create test user
        user = User(
            email="bulk_test@example.com",
            name="Bulk Tester",
            role="job_seeker",
            is_active=True,
            is_verified=True,
            password_hash="test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Pre-seed one existing job
        existing_job = Job(
            user_id=user.id,
            url="https://example.com/jobs/existing-1",
            title="Existing Engineer",
            company="Legacy Corp",
            status="ready",
        )
        db.add(existing_job)
        db.commit()
        db.refresh(existing_job)

        # 1. Test bulk_extract_jobs with duplicate detection
        test_urls = [
            "https://example.com/jobs/existing-1",  # should be duplicate
            "https://example.com/jobs/new-job-1",   # new
            "https://example.com/jobs/new-job-2",   # new
            "not-a-url",                            # invalid, ignored
        ]

        def mock_extract(url: str):
            return {
                "title": f"Extracted for {url}",
                "company": "Test Company",
                "location": "Remote",
                "work_type": "remote",
                "experience_level": "mid",
                "skills": "Python, React",
                "description": "Great job",
                "salary": "$120k",
                "application_url": url,
                "application_method": "form",
                "extraction_method": "mock",
                "extraction_warning": None,
            }

        with patch("app.services.job_service.extract_job_from_url", side_effect=mock_extract):
            extract_res = asyncio.run(job_service.bulk_extract_jobs(db, user, test_urls))

        assert extract_res.total == 3, f"Expected 3 valid URLs, got {extract_res.total}"
        assert extract_res.duplicate_count == 1
        assert extract_res.extracted_count == 2
        assert extract_res.failed_count == 0

        dup_item = next(i for i in extract_res.items if i.url == "https://example.com/jobs/existing-1")
        assert dup_item.status == "duplicate"
        assert dup_item.existing_job_id == existing_job.id

        new_item = next(i for i in extract_res.items if i.url == "https://example.com/jobs/new-job-1")
        assert new_item.status == "extracted"
        assert new_item.data.title == "Extracted for https://example.com/jobs/new-job-1"

        # 2. Test bulk_save_jobs
        save_batch = BulkJobSaveRequest(
            jobs=[
                JobSaveRequest(
                    url="https://example.com/jobs/existing-1",  # duplicate, should be skipped
                    title="Should be skipped",
                    company="Legacy Corp",
                ),
                JobSaveRequest(
                    url="https://example.com/jobs/new-job-1",
                    title="Full Stack Engineer",
                    company="Stripe",
                    location="San Francisco",
                    work_type="remote",
                ),
                JobSaveRequest(
                    url="https://example.com/jobs/new-job-2",
                    title="Backend Engineer",
                    company="GitHub",
                    location="Remote",
                    work_type="remote",
                ),
            ]
        )

        save_res = job_service.bulk_save_jobs(db, user, save_batch)
        assert save_res.saved_count == 2, f"Expected 2 saved, got {save_res.saved_count}"
        assert save_res.skipped_count == 1, f"Expected 1 skipped, got {save_res.skipped_count}"
        assert len(save_res.saved_jobs) == 2

        # Verify in DB
        all_jobs = db.query(Job).filter(Job.user_id == user.id).all()
        assert len(all_jobs) == 3  # 1 initial + 2 new

        print("ALL BULK JOB TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_bulk_operations()

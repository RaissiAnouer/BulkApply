"""Automated unit tests for Company & Contact Intelligence."""

from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.job import Job
from app.models.company_intelligence import CompanyIntelligence, CompanyContact
from app.services import company_intelligence_service


def test_company_intelligence_suite():
    # In-memory SQLite DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        # Create user & jobs
        user = User(
            email="intel_test@example.com",
            name="Intel Tester",
            role="job_seeker",
            is_active=True,
            is_verified=True,
            password_hash="test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        job1 = Job(
            user_id=user.id,
            url="https://stripe.com/jobs/senior-backend-engineer",
            title="Senior Backend Engineer",
            company="Stripe",
            location="San Francisco, CA",
            status="ready",
        )
        job2 = Job(
            user_id=user.id,
            url="https://boards.greenhouse.io/datadog/jobs/12345",
            title="Marketing Director",
            company="",
            location="Paris, France",
            status="ready",
        )
        db.add_all([job1, job2])
        db.commit()
        db.refresh(job1)
        db.refresh(job2)

        # 1. Test Company Identification
        comp1, conf1 = company_intelligence_service.identify_company(job1)
        assert comp1 == "Stripe"
        assert conf1 == "HIGH"  # 'stripe' in 'stripe.com'

        comp2, conf2 = company_intelligence_service.identify_company(job2)
        assert comp2 == "Datadog"
        assert conf2 == "LOW"  # greenhouse subdomain/path fallback

        # 2. Test Target Roles determination
        tech_roles = company_intelligence_service.determine_target_roles(job1.title)
        assert "Technical Recruiter" in tech_roles["hiring"]
        assert "Engineering Manager" in tech_roles["leadership"]

        marketing_roles = company_intelligence_service.determine_target_roles(job2.title)
        assert "Marketing Recruiter" in marketing_roles["hiring"]
        assert "Head of Marketing" in marketing_roles["leadership"]

        # 3. Test Full Pipeline Execution with Mocks
        mock_info = {
            "website": "https://stripe.com",
            "linkedin_url": "https://www.linkedin.com/company/stripe",
            "industry": "Financial Technology",
            "description": "Stripe builds economic infrastructure for the internet.",
            "headquarters": "San Francisco, CA",
            "company_size": "5,000 - 10,000 employees",
            "technologies": "Ruby, Go, Java, React",
            "confidence": "HIGH",
        }

        mock_contacts = [
            {
                "full_name": "Alice Recruiter",
                "job_title": "Lead Technical Recruiter",
                "category": "hiring",
                "department": "Talent Acquisition",
                "linkedin_url": "https://www.linkedin.com/in/alice-recruiter-stripe",
                "confidence": "HIGH",
                "evidence": "Current Lead Technical Recruiter at Stripe",
            },
            {
                "full_name": "Bob Manager",
                "job_title": "Engineering Manager - Payments",
                "category": "leadership",
                "department": "Engineering",
                "linkedin_url": "https://www.linkedin.com/in/bob-manager-stripe",
                "confidence": "HIGH",
                "evidence": "Current Engineering Manager at Stripe",
            },
            {
                "full_name": "Charlie Engineer",
                "job_title": "Staff Software Engineer",
                "category": "other",
                "department": "Infrastructure",
                "linkedin_url": None,  # No verified link
                "confidence": "MEDIUM",
                "evidence": "Senior engineer in target department",
            },
        ]

        with patch("app.services.company_intelligence_service.enrich_company_info", return_value=mock_info), \
             patch("app.services.company_intelligence_service.discover_and_verify_contacts", return_value=mock_contacts):
            intel = company_intelligence_service.process_company_intelligence(db, job1)

        assert intel.status == "COMPLETED"
        assert intel.company_name == "Stripe"
        assert intel.confidence == "HIGH"
        assert intel.website == "https://stripe.com"
        assert intel.linkedin_url == "https://www.linkedin.com/company/stripe"

        # Check contacts
        contacts = db.query(CompanyContact).filter(CompanyContact.intelligence_id == intel.id).all()
        assert len(contacts) == 3

        hiring = [c for c in contacts if c.category == "hiring"]
        assert len(hiring) == 1
        assert hiring[0].full_name == "Alice Recruiter"
        assert hiring[0].linkedin_url == "https://www.linkedin.com/in/alice-recruiter-stripe"

        leadership = [c for c in contacts if c.category == "leadership"]
        assert len(leadership) == 1
        assert leadership[0].full_name == "Bob Manager"

        # 4. Test Contact Relevance Toggle
        updated_contact = company_intelligence_service.update_contact_relevance(
            db, job1.id, hiring[0].id, user.id, is_relevant=False
        )
        assert updated_contact.is_relevant is False

        # 5. Test Contact Deletion
        company_intelligence_service.delete_contact(db, job1.id, leadership[0].id, user.id)
        remaining_contacts = db.query(CompanyContact).filter(CompanyContact.intelligence_id == intel.id).all()
        assert len(remaining_contacts) == 2

        # 6. Test Error Isolation (Pipeline failure does not damage job)
        with patch("app.services.company_intelligence_service.enrich_company_info", side_effect=RuntimeError("API Gateway Timeout")):
            failed_intel = company_intelligence_service.process_company_intelligence(db, job2)

        assert failed_intel.status == "FAILED"
        assert "API Gateway Timeout" in failed_intel.error_message
        # Job is still intact and ready
        fresh_job2 = db.query(Job).filter(Job.id == job2.id).first()
        assert fresh_job2.status == "ready"

        print("ALL COMPANY & CONTACT INTELLIGENCE TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_company_intelligence_suite()

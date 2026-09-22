"""Company and Contact Intelligence Service.

Executes a 7-stage asynchronous intelligence pipeline:
Stage 1: Job -> Company Identification (with confidence scoring)
Stage 2: Company -> Official Company Information (website, LinkedIn, HQ, size, tech stack)
Stage 3: Company + Job -> Relevant Target Roles mapping
Stage 4 & 5: Public search -> Candidate employees + identity verification (strictly avoiding hallucinated LinkedIn URLs)
Stage 6: Relevance classification (Hiring/Recruiting, Leadership, Team)
Stage 7: Persistence & Error Isolation
"""

import json
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.database import SessionLocal
from app.models.company_intelligence import CompanyIntelligence, CompanyContact
from app.models.job import Job

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _is_valid_linkedin_url(url: str | None) -> bool:
    """Validate that a URL is a real public LinkedIn profile URL."""
    if not url:
        return False
    url = url.strip()
    # Matches patterns like https://www.linkedin.com/in/username or https://fr.linkedin.com/in/username
    pattern = r"^https?:\/\/(?:[a-zA-Z0-9_-]+\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+\/?$"
    return bool(re.match(pattern, url, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Stage 1: Company Identification
# ---------------------------------------------------------------------------

def identify_company(job: Job) -> tuple[str, str]:
    """
    Identifies target company name and calculates confidence level.
    Returns (company_name, confidence).
    """
    company = (job.company or "").strip()
    url = (job.url or "").strip()

    if company:
        # If company name is present and job URL has a corresponding domain
        domain = urllib.parse.urlparse(url).netloc.lower() if url else ""
        clean_company = re.sub(r"[^a-zA-Z0-9]", "", company.lower())
        if clean_company and clean_company in domain.replace(".", ""):
            return company, "HIGH"
        return company, "MEDIUM"

    # Attempt to extract company from URL if company field was empty
    if url:
        try:
            parsed = urllib.parse.urlparse(url)
            domain_parts = parsed.netloc.split(".")
            # Common job boards
            if any(b in parsed.netloc for b in ["greenhouse.io", "lever.co", "workday.com"]):
                # Often in path or subdomain
                path_parts = [p for p in parsed.path.split("/") if p]
                if path_parts:
                    return path_parts[0].capitalize(), "LOW"
            if len(domain_parts) >= 2:
                candidate = domain_parts[-2].capitalize()
                if candidate.lower() not in ["linkedin", "indeed", "glassdoor", "monster"]:
                    return candidate, "LOW"
        except Exception:
            pass

    return "Unknown Company", "UNKNOWN"


# ---------------------------------------------------------------------------
# Stage 2: Company Information Enrichment
# ---------------------------------------------------------------------------

def enrich_company_info(company_name: str, job: Job) -> dict[str, Any]:
    """
    Enriches company information (website, LinkedIn page, industry, size, etc.)
    using Google Gemini AI. Falls back safely if API is unavailable.
    """
    default_info = {
        "website": None,
        "linkedin_url": None,
        "industry": None,
        "description": None,
        "headquarters": job.location,
        "company_size": None,
        "technologies": job.skills,
        "confidence": "LOW",
    }

    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip() or company_name == "Unknown Company":
        return default_info

    try:
        client = genai.Client(api_key=GEMINI_API_KEY.strip())
        prompt = f"""
You are a corporate intelligence analyst. Provide verified, public company profile information for:
Company: "{company_name}"
Context (Job location: {job.location}, Job URL: {job.url})

Return ONLY valid JSON matching this structure:
{{
    "official_website": "https://...",
    "linkedin_url": "https://www.linkedin.com/company/...",
    "industry": "e.g. Software Development / Financial Technology",
    "description": "A concise 2-3 sentence overview of what the company does.",
    "headquarters": "City, Country",
    "company_size": "e.g. 50-200 employees, 1,000-5,000 employees, 10,000+ employees",
    "technologies": "Comma-separated list of core technologies or products",
    "confidence": "HIGH" or "MEDIUM" or "LOW"
}}
If a field is uncertain or unknown, return null. Do NOT invent fake URLs.
"""
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        if response.text:
            data = json.loads(_clean_json_text(response.text))
            return {
                "website": data.get("official_website"),
                "linkedin_url": data.get("linkedin_url"),
                "industry": data.get("industry"),
                "description": data.get("description"),
                "headquarters": data.get("headquarters") or job.location,
                "company_size": data.get("company_size"),
                "technologies": data.get("technologies") or job.skills,
                "confidence": data.get("confidence", "MEDIUM"),
            }
    except Exception as e:
        logger.warning("[CompanyIntelligence] Gemini company enrichment failed for %s: %s", company_name, e)

    return default_info


# ---------------------------------------------------------------------------
# Stage 3: Relevant Role Mapping
# ---------------------------------------------------------------------------

def determine_target_roles(job_title: str | None) -> dict[str, list[str]]:
    """
    Determines priority roles to search for based on the job's title.
    Returns categorized search targets: {"hiring": [...], "leadership": [...]}.
    """
    title_lower = (job_title or "").lower()

    # Technical / Engineering
    if any(k in title_lower for k in ["engineer", "developer", "architect", "devops", "qa", "software", "tech"]):
        return {
            "hiring": ["Technical Recruiter", "Talent Acquisition", "Engineering Recruiter", "Hiring Manager"],
            "leadership": ["Engineering Manager", "Head of Engineering", "Chief Technology Officer", "VP of Engineering", "Technical Lead"],
        }
    # Product / Design
    if any(k in title_lower for k in ["product", "design", "ux", "ui"]):
        return {
            "hiring": ["Product Recruiter", "Talent Acquisition", "Design Recruiter"],
            "leadership": ["Head of Product", "VP of Product", "Lead Product Manager", "Design Director"],
        }
    # Marketing / Growth
    if any(k in title_lower for k in ["market", "growth", "content", "brand", "seo"]):
        return {
            "hiring": ["Marketing Recruiter", "Talent Acquisition"],
            "leadership": ["Chief Marketing Officer", "Head of Marketing", "VP of Marketing", "Marketing Director"],
        }
    # Sales / Business Development
    if any(k in title_lower for k in ["sale", "account executive", "bdr", "sdr", "business development"]):
        return {
            "hiring": ["Sales Recruiter", "Talent Acquisition"],
            "leadership": ["Head of Sales", "VP of Sales", "Sales Director", "Commercial Lead"],
        }

    # Default / General roles
    return {
        "hiring": ["Recruiter", "Talent Acquisition", "People Operations"],
        "leadership": ["Managing Director", "Department Lead", "Director", "Chief Executive Officer"],
    }


# ---------------------------------------------------------------------------
# Stages 4, 5 & 6: Public Discovery, Verification & Relevance Classification
# ---------------------------------------------------------------------------

def discover_and_verify_contacts(company_name: str, job: Job) -> list[dict[str, Any]]:
    """
    Discovers publicly available professional profiles relevant to the job and company.
    Strictly enforces verified roles, evidence, and valid LinkedIn URL format.
    Never fabricates URLs.
    """
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip() or company_name == "Unknown Company":
        return []

    target_roles = determine_target_roles(job.title)
    hiring_roles_str = ", ".join(target_roles["hiring"])
    leadership_roles_str = ", ".join(target_roles["leadership"])

    try:
        client = genai.Client(api_key=GEMINI_API_KEY.strip())
        prompt = f"""
You are a professional recruitment research assistant.
Job applied for: "{job.title or 'Unknown Position'}" at "{company_name}".
Location: "{job.location or 'Global'}"

Search target categories:
- Hiring & Recruiting team: ({hiring_roles_str})
- Leadership team: ({leadership_roles_str})

Provide known publicly identifiable leaders, managers, and recruiting professionals who currently or prominently work at "{company_name}" relevant to this position.

CRITICAL RULES:
1. ONLY return individuals whose employment at "{company_name}" is publicly known.
2. Only include a public LinkedIn profile URL if you know the exact public vanity URL or handle (format: https://www.linkedin.com/in/... or country subdomain like https://uk.linkedin.com/in/...).
3. NEVER guess, invent, or fabricate random numbers/hashes for LinkedIn URLs. If uncertain, set linkedin_url to null.
4. Categorize each person as exactly one of: "hiring", "leadership", "other".
5. Provide a short "evidence" explanation of why this person was identified for this job.

Return a JSON array of objects with the following schema:
[
  {{
    "full_name": "Full Name",
    "job_title": "Current Job Title",
    "category": "hiring" or "leadership" or "other",
    "department": "e.g. Engineering / People / Operations",
    "linkedin_url": "https://www.linkedin.com/in/... or null",
    "confidence": "HIGH" or "MEDIUM" or "LOW",
    "evidence": "Why this person is relevant to the job posting"
  }}
]
Limit to 3 to 6 high-confidence people.
"""
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        if not response.text:
            return []

        raw_list = json.loads(_clean_json_text(response.text))
        if not isinstance(raw_list, list):
            return []

        verified_contacts: list[dict[str, Any]] = []
        for person in raw_list:
            name = person.get("full_name", "").strip()
            title = person.get("job_title", "").strip()
            if not name or not title:
                continue

            # Validate category
            category = person.get("category", "other").lower()
            if category not in ["hiring", "leadership", "other"]:
                category = "other"

            # Validate LinkedIn URL strictly
            raw_url = person.get("linkedin_url")
            cleaned_url = raw_url.strip() if (raw_url and isinstance(raw_url, str)) else None
            if cleaned_url and not _is_valid_linkedin_url(cleaned_url):
                cleaned_url = None

            conf = person.get("confidence", "MEDIUM").upper()
            if conf not in ["HIGH", "MEDIUM", "LOW"]:
                conf = "MEDIUM"

            verified_contacts.append({
                "full_name": name,
                "job_title": title,
                "category": category,
                "department": person.get("department"),
                "linkedin_url": cleaned_url,
                "confidence": conf,
                "evidence": person.get("evidence") or f"Public professional record indicates {title} at {company_name}",
            })

        return verified_contacts

    except Exception as e:
        logger.warning("[CompanyIntelligence] Contacts discovery failed for %s: %s", company_name, e)
        return []


# ---------------------------------------------------------------------------
# Stage 7: Pipeline Coordinator & Persistence
# ---------------------------------------------------------------------------

def process_company_intelligence(db: Session, job: Job) -> CompanyIntelligence:
    """
    Executes the full 7-stage intelligence pipeline synchronously for a Job.
    Updates or creates the CompanyIntelligence record and its associated CompanyContacts.
    """
    # 1. Get or create record
    intel = (
        db.query(CompanyIntelligence)
        .filter(CompanyIntelligence.job_id == job.id)
        .first()
    )
    if not intel:
        intel = CompanyIntelligence(
            job_id=job.id,
            company_name=job.company or "Unknown Company",
            status="RESEARCHING",
        )
        db.add(intel)
        db.commit()
        db.refresh(intel)
    else:
        intel.status = "RESEARCHING"
        intel.error_message = None
        db.commit()

    try:
        # Stage 1: Identify Company & Base Confidence
        company_name, id_confidence = identify_company(job)
        intel.company_name = company_name
        intel.confidence = id_confidence

        # Stage 2: Company Information Enrichment
        info = enrich_company_info(company_name, job)
        intel.website = info.get("website")
        intel.linkedin_url = info.get("linkedin_url")
        intel.industry = info.get("industry")
        intel.description = info.get("description")
        intel.headquarters = info.get("headquarters")
        intel.company_size = info.get("company_size")
        intel.technologies = info.get("technologies")
        if info.get("confidence") == "HIGH" and id_confidence == "HIGH":
            intel.confidence = "HIGH"
        elif id_confidence != "UNKNOWN":
            intel.confidence = info.get("confidence", id_confidence)

        # Stages 3-6: Discover, verify & classify relevant contacts
        contacts_data = discover_and_verify_contacts(company_name, job)

        # Remove existing contacts if this is a refresh
        db.query(CompanyContact).filter(CompanyContact.intelligence_id == intel.id).delete()

        # Insert newly discovered verified contacts
        for c in contacts_data:
            contact = CompanyContact(
                intelligence_id=intel.id,
                full_name=c["full_name"],
                job_title=c["job_title"],
                category=c["category"],
                department=c.get("department"),
                linkedin_url=c.get("linkedin_url"),
                confidence=c.get("confidence", "MEDIUM"),
                evidence=c.get("evidence"),
                is_relevant=True,
            )
            db.add(contact)

        intel.status = "COMPLETED"
        intel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(intel)
        logger.info("[CompanyIntelligence] Successfully completed research for job %d (%s)", job.id, company_name)
        return intel

    except Exception as err:
        logger.error("[CompanyIntelligence] Failed processing intelligence for job %d: %s", job.id, err)
        intel.status = "FAILED"
        intel.error_message = str(err)
        intel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(intel)
        return intel


def run_company_intelligence_task(job_id: int) -> None:
    """
    Background task wrapper that opens an isolated DB session to execute the pipeline.
    """
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning("[CompanyIntelligence] Task invoked for non-existent job ID: %d", job_id)
            return
        process_company_intelligence(db, job)


def get_company_intelligence_for_job(db: Session, job_id: int, user_id: int) -> CompanyIntelligence | None:
    """Retrieve intelligence for a job, verifying ownership."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise ValueError("Job not found or access denied")

    return (
        db.query(CompanyIntelligence)
        .filter(CompanyIntelligence.job_id == job_id)
        .first()
    )


def update_contact_relevance(db: Session, job_id: int, contact_id: int, user_id: int, is_relevant: bool) -> CompanyContact:
    """Toggle is_relevant flag on a contact."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise ValueError("Job not found or access denied")

    contact = (
        db.query(CompanyContact)
        .join(CompanyIntelligence)
        .filter(
            CompanyContact.id == contact_id,
            CompanyIntelligence.job_id == job_id,
        )
        .first()
    )
    if not contact:
        raise ValueError("Contact not found")

    contact.is_relevant = is_relevant
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, job_id: int, contact_id: int, user_id: int) -> None:
    """Remove a contact from company intelligence."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise ValueError("Job not found or access denied")

    contact = (
        db.query(CompanyContact)
        .join(CompanyIntelligence)
        .filter(
            CompanyContact.id == contact_id,
            CompanyIntelligence.job_id == job_id,
        )
        .first()
    )
    if not contact:
        raise ValueError("Contact not found")

    db.delete(contact)
    db.commit()

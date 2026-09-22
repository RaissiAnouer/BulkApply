"""Job extraction service — fetches job posting data from a URL using Gemini AI.

Strategy:
1. Primary: Gemini URL Context tool (Gemini fetches the page natively).
2. Fallback: requests + BeautifulSoup → extract text → Gemini text parsing.
3. Final fallback: return empty data so user can fill manually.
"""

import json
import re
import logging

import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas.job import GeminiJobExtraction

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are an expert job posting parser. Analyze the provided job posting and extract "
    "accurate structured data. For work_type use exactly one of: remote, hybrid, onsite. "
    "For experience_level use exactly one of: entry, mid, senior, lead, executive. "
    "For application_method use exactly one of: form, email, external_link. "
    "For skills, return a comma-separated string. "
    "If a field cannot be determined, return null."
)

# Timeout for HTTP requests (seconds)
_HTTP_TIMEOUT = 15


def extract_job_from_url(url: str) -> dict:
    """
    Extract structured job data from a URL.

    Returns a dict with the extracted fields plus 'extraction_method' and
    'extraction_warning' metadata keys.
    """
    # Try primary approach: Gemini URL Context
    result = _try_gemini_url_context(url)
    if result is not None:
        result["extraction_method"] = "gemini_url_context"
        result["extraction_warning"] = None
        logger.info("[JOB_EXTRACT] Gemini URL Context succeeded for %s", url)
    else:
        # Fallback: fetch HTML manually, extract text, send to Gemini
        result = _try_html_text_gemini(url)
        if result is not None:
            result["extraction_method"] = "gemini_text_fallback"
            result["extraction_warning"] = (
                "Extracted using fallback method. Some fields may be less accurate."
            )
            logger.info("[JOB_EXTRACT] Gemini text fallback succeeded for %s", url)
        else:
            # Final fallback: empty data
            logger.warning("[JOB_EXTRACT] All extraction methods failed for %s", url)
            result = {
                "title": None,
                "company": None,
                "location": None,
                "work_type": None,
                "experience_level": None,
                "skills": None,
                "description": None,
                "salary": None,
                "application_url": None,
                "application_method": None,
                "extraction_method": "manual",
                "extraction_warning": (
                    "We could not extract job information from this page. "
                    "You can enter the details manually."
                ),
            }

    # Perform inline company & employees intelligence during job extraction
    company_name = result.get("company")
    if company_name or url:
        try:
            from app.services.company_intelligence_service import run_inline_company_intelligence
            intel = run_inline_company_intelligence(
                company_name=company_name,
                job_title=result.get("title"),
                job_location=result.get("location"),
                job_url=url,
                job_skills=result.get("skills"),
            )
            result["company_intelligence"] = intel
        except Exception as e:
            logger.warning("[JOB_EXTRACT] Inline company intelligence failed for %s: %s", url, e)
            result["company_intelligence"] = None
    else:
        result["company_intelligence"] = None

    return result


def _try_gemini_url_context(url: str) -> dict | None:
    """Use Gemini's URL Context tool to fetch and parse the job page."""
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        logger.warning("[JOB_EXTRACT] GEMINI_API_KEY not configured, skipping URL Context.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY.strip())

        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=GeminiJobExtraction,
            temperature=0.1,
            tools=[types.Tool(url_context=types.UrlContext())],
        )

        prompt = f"Extract structured job posting data from this URL: {url}"

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        return _parse_gemini_response(response)

    except Exception as e:
        logger.warning("[JOB_EXTRACT] Gemini URL Context failed: %s", e)
        return None


def _try_html_text_gemini(url: str) -> dict | None:
    """Fetch the page with requests, extract text, send to Gemini for parsing."""
    # Step 1: Fetch HTML
    page_text = _fetch_page_text(url)
    if not page_text:
        return None

    # Step 2: Send to Gemini
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        logger.warning("[JOB_EXTRACT] GEMINI_API_KEY not configured, skipping text parsing.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY.strip())

        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=GeminiJobExtraction,
            temperature=0.1,
        )

        # Truncate to avoid token limits (approx 15k chars)
        truncated = page_text[:15000]
        prompt = f"Extract structured job posting data from this text:\n\n{truncated}"

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        return _parse_gemini_response(response)

    except Exception as e:
        logger.warning("[JOB_EXTRACT] Gemini text fallback failed: %s", e)
        return None


def _fetch_page_text(url: str) -> str | None:
    """Fetch a URL and extract visible text using BeautifulSoup."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=_HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-visible elements
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        if len(text) < 50:
            logger.warning("[JOB_EXTRACT] Page text too short (%d chars) for %s", len(text), url)
            return None

        return text

    except Exception as e:
        logger.warning("[JOB_EXTRACT] Failed to fetch page %s: %s", url, e)
        return None


def _parse_gemini_response(response) -> dict | None:
    """Parse and validate a Gemini response into a dict."""
    if not response.text:
        return None

    cleaned = response.text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    data = json.loads(cleaned)
    validated = GeminiJobExtraction.model_validate(data)
    return validated.model_dump()

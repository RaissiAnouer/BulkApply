"""Cover Letter Generation Service — synthesizes candidate CV data and job description.

Explicitly tracks and logs the generation source: 'gemini' vs 'fallback'.
Never logs or exposes GEMINI_API_KEY.
"""

import logging
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_COVER_LETTER_SYSTEM_INSTRUCTION = (
    "You are an expert executive cover letter writer. Your task is to craft a highly compelling, "
    "tailored, professional cover letter for a candidate applying to a specific job.\n"
    "Guidelines:\n"
    "1. Synthesize the candidate's actual background, skills, and work experiences with the target job requirements.\n"
    "2. Keep the tone professional, confident, and engaging.\n"
    "3. Keep the total length concise, strictly under 400 words.\n"
    "4. Highlight relevant accomplishments and skills directly relevant to the role.\n"
    "5. Format cleanly with standard business letter greeting and closing (do not include markdown headers like '# Cover Letter')."
)


def _generate_fallback_cover_letter(
    candidate_name: str,
    job_title: str | None,
    company: str | None,
    skills_summary: str | None,
) -> str:
    """Generate a clean, structured fallback cover letter template when Gemini is unavailable."""
    target_role = job_title or "the open position"
    target_company = company or "your organization"
    key_skills = skills_summary or "relevant domain experience and technical proficiencies"

    return (
        f"Dear Hiring Team at {target_company},\n\n"
        f"I am writing to express my strong interest in the {target_role} position. "
        f"With a solid background in {key_skills}, I am excited about the opportunity "
        f"to contribute meaningfully to your team's goals at {target_company}.\n\n"
        "Throughout my professional career, I have dedicated myself to delivering high-quality "
        "results, solving complex challenges, and continuously learning emerging technologies "
        "and methodologies. My experience aligns closely with the core qualifications required "
        "for this role, and I am confident in my ability to make an immediate, positive impact.\n\n"
        f"Thank you for your time and consideration. I welcome the opportunity to discuss how "
        f"my skills and background match the needs of {target_company}.\n\n"
        "Sincerely,\n"
        f"{candidate_name}"
    )


def generate_cover_letter(
    cv_parsed_data: dict,
    candidate_name: str,
    job_title: str | None,
    company: str | None,
    job_description: str | None,
    job_skills: str | None,
) -> tuple[str, str]:
    """
    Generate a tailored cover letter.

    Returns:
        tuple[str, str]: (cover_letter_text, source) where source is 'gemini' or 'fallback'.
    """
    # Check if Gemini API key is configured
    api_key = (GEMINI_API_KEY or "").strip()
    if not api_key:
        logger.warning(
            "[CoverLetterService] GEMINI_API_KEY is not configured. Source: fallback"
        )
        fallback_text = _generate_fallback_cover_letter(
            candidate_name=candidate_name,
            job_title=job_title,
            company=company,
            skills_summary=job_skills,
        )
        return fallback_text, "fallback"

    try:
        # Extract candidate highlights from parsed CV
        candidate_skills = cv_parsed_data.get("skills", [])
        if isinstance(candidate_skills, list):
            skills_str = ", ".join(candidate_skills[:15])
        else:
            skills_str = str(candidate_skills)

        candidate_experience = cv_parsed_data.get("experience", [])
        experience_snippets = []
        if isinstance(candidate_experience, list):
            for exp in candidate_experience[:3]:
                if isinstance(exp, dict):
                    title = exp.get("title", "")
                    comp = exp.get("company", "")
                    desc = exp.get("description", "")
                    experience_snippets.append(f"- {title} at {comp}: {desc[:120]}")
        exp_summary = "\n".join(experience_snippets)

        prompt = (
            f"Candidate Name: {candidate_name}\n"
            f"Candidate Key Skills: {skills_str}\n"
            f"Candidate Relevant Experience:\n{exp_summary}\n\n"
            f"Target Position: {job_title or 'Professional Role'}\n"
            f"Target Company: {company or 'Hiring Company'}\n"
            f"Target Required Skills: {job_skills or 'Not specified'}\n"
            f"Job Description Excerpt:\n{(job_description or '')[:1200]}\n\n"
            "Generate the tailored cover letter now:"
        )

        client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            system_instruction=_COVER_LETTER_SYSTEM_INSTRUCTION,
            temperature=0.7,
            max_output_tokens=800,
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        if response.text and response.text.strip():
            letter_text = response.text.strip()
            logger.info(
                "[CoverLetterService] Cover letter generated successfully for candidate '%s' "
                "for job '%s' at '%s'. Source: gemini",
                candidate_name,
                job_title,
                company,
            )
            return letter_text, "gemini"
        else:
            raise ValueError("Gemini returned empty response text")

    except Exception as exc:
        # Never log API key or secret values
        logger.warning(
            "[CoverLetterService] Gemini call failed (%s: %s). Falling back to template. Source: fallback",
            type(exc).__name__,
            str(exc),
        )
        fallback_text = _generate_fallback_cover_letter(
            candidate_name=candidate_name,
            job_title=job_title,
            company=company,
            skills_summary=job_skills,
        )
        return fallback_text, "fallback"

"""AI Service using Google Gemini for semantic CV parsing."""

import json
import re
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas.cv import ParsedDataSchema


def parse_cv_with_gemini(raw_text: str) -> dict:
    """
    Calls Google Gemini using the official google-genai SDK to semantically
    structure resume text into the approved ParsedDataSchema JSON.
    """
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=GEMINI_API_KEY.strip())

    system_instruction = (
        "You are an expert resume parsing engine. Analyze the provided resume text and extract "
        "accurate candidate contact information, technical and professional skills, work experience history "
        "(with company, title, start date, end date, and description), and education history "
        "(institution, degree, and graduation year)."
    )

    prompt = f"Extract structured candidate data from this resume text:\n\n{raw_text}"

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=ParsedDataSchema,
        temperature=0.1,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    cleaned_text = response.text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\n?", "", cleaned_text)
        cleaned_text = re.sub(r"\n?```$", "", cleaned_text)

    data = json.loads(cleaned_text)

    # Validate against our Pydantic schema to ensure strict type compliance
    validated = ParsedDataSchema.model_validate(data)
    return validated.model_dump()

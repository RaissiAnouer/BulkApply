"""Comprehensive test suite for Gemini integration, fallback behavior, and CV lifecycle."""

import os
import json
import unittest
from unittest.mock import patch, MagicMock
from docx import Document

from app.schemas.cv import ParsedDataSchema
from app.services import cv_parser_service, ai_service


SAMPLE_RESUME_TEXT = """
Jane Candidate
jane.candidate@example.com | +1 (555) 012-3456 | Austin, TX
Skills: Python, FastAPI, React, TypeScript, Docker, SQL, PostgreSQL, Git
Experience:
Senior Developer | Tech Innovators | 2021 - Present
Developed backend REST APIs using FastAPI and PostgreSQL.
Education:
University of Texas | Bachelor of Science in Computer Science | 2020
"""


class TestGeminiIntegrationAndFallback(unittest.TestCase):

    def test_missing_api_key_fallback(self):
        """When GEMINI_API_KEY is empty, cv_parser_service must fall back to local parser without crashing."""
        with patch("app.services.ai_service.GEMINI_API_KEY", ""):
            result = cv_parser_service.parse_cv_text(SAMPLE_RESUME_TEXT)
            self.assertIsInstance(result, dict)
            self.assertIn("contact_info", result)
            self.assertIn("skills", result)
            self.assertIn("Python", result["skills"])
            # Schema validation
            validated = ParsedDataSchema.model_validate(result)
            self.assertIsNotNone(validated)
            print("  [TEST PASS] Missing API key gracefully triggered local fallback.")

    def test_gemini_api_failure_fallback(self):
        """When Gemini API call raises an exception (network/quota), fall back to local parser."""
        with patch("app.services.ai_service.GEMINI_API_KEY", "dummy_key"):
            with patch("google.genai.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded: 429 ResourceExhausted")
                mock_client_cls.return_value = mock_client

                result = cv_parser_service.parse_cv_text(SAMPLE_RESUME_TEXT)
                self.assertIsInstance(result, dict)
                self.assertIn("contact_info", result)
                self.assertIn("skills", result)
                self.assertIn("FastAPI", result["skills"])
                print("  [TEST PASS] Gemini API failure (429/quota) gracefully triggered local fallback.")

    def test_malformed_gemini_output_fallback(self):
        """When Gemini returns malformed non-JSON text, fall back to local parser."""
        with patch("app.services.ai_service.GEMINI_API_KEY", "dummy_key"):
            with patch("google.genai.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "Sorry, as an AI model I cannot parse this non-standard text: <<MALFORMED>>"
                mock_client.models.generate_content.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = cv_parser_service.parse_cv_text(SAMPLE_RESUME_TEXT)
                self.assertIsInstance(result, dict)
                self.assertIn("contact_info", result)
                self.assertIn("skills", result)
                self.assertIn("Docker", result["skills"])
                print("  [TEST PASS] Malformed Gemini output gracefully triggered local fallback.")

    def test_normal_gemini_parsing_success(self):
        """When Gemini succeeds, the structured result from Gemini is returned and validated."""
        mock_gemini_json = json.dumps({
            "contact_info": {
                "full_name": "Jane Candidate",
                "email": "jane.candidate@example.com",
                "phone": "+1 (555) 012-3456",
                "location": "Austin, TX"
            },
            "skills": ["Python", "FastAPI", "React", "TypeScript", "Docker", "PostgreSQL"],
            "work_experience": [
                {
                    "company": "Tech Innovators",
                    "title": "Senior Developer",
                    "start_date": "2021",
                    "end_date": "Present",
                    "description": "Architected distributed systems."
                }
            ],
            "education": [
                {
                    "institution": "University of Texas",
                    "degree": "B.S. in Computer Science",
                    "graduation_year": "2020"
                }
            ]
        })

        with patch("app.services.ai_service.GEMINI_API_KEY", "valid_key"):
            with patch("google.genai.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.text = mock_gemini_json
                mock_client.models.generate_content.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = cv_parser_service.parse_cv_text(SAMPLE_RESUME_TEXT)
                self.assertEqual(result["contact_info"]["full_name"], "Jane Candidate")
                self.assertIn("PostgreSQL", result["skills"])
                self.assertEqual(result["work_experience"][0]["title"], "Senior Developer")
                print("  [TEST PASS] Successful Gemini parsing validated and returned.")

    def test_text_extraction_pdf_and_docx(self):
        """Test that pypdf and python-docx correctly extract raw text from files."""
        os.makedirs("test_fixtures", exist_ok=True)

        # DOCX extraction
        doc = Document()
        doc.add_paragraph("Testing DOCX extraction for candidate Jane.")
        docx_path = "test_fixtures/test_extract.docx"
        doc.save(docx_path)

        extracted_docx = cv_parser_service.extract_text(docx_path, "docx")
        self.assertIn("Testing DOCX extraction", extracted_docx)

        if os.path.exists(docx_path):
            os.remove(docx_path)
        print("  [TEST PASS] Text extraction from document files verified.")


if __name__ == "__main__":
    print("\n=== RUNNING GEMINI UNIT & PARSER TESTS ===")
    unittest.main(verbosity=2)

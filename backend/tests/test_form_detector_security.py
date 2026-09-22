"""Unit tests for form detector security classification and heuristics."""

import unittest
from app.services.form_detector import (
    SecurityClassification,
    split_name,
    matches_any_pattern,
    NAME_PATTERNS,
    APPLY_BUTTON_PATTERNS,
    DENY_BUTTON_PATTERNS,
)


class TestFormDetectorSecurity(unittest.TestCase):
    def test_security_classification_enum(self):
        self.assertEqual(SecurityClassification.PUBLIC_APPLICATION_FORM, "PUBLIC_APPLICATION_FORM")
        self.assertEqual(SecurityClassification.AUTHENTICATION_REQUIRED, "AUTHENTICATION_REQUIRED")
        self.assertEqual(SecurityClassification.CAPTCHA_CHALLENGE, "CAPTCHA_CHALLENGE")
        self.assertEqual(SecurityClassification.OPEN_PAGE, "OPEN_PAGE")

    def test_split_name(self):
        first, last = split_name("Anouer Raissi")
        self.assertEqual(first, "Anouer")
        self.assertEqual(last, "Raissi")

        first, last = split_name("John")
        self.assertEqual(first, "John")
        self.assertEqual(last, "")

        first, last = split_name("Jean-Luc Picard")
        self.assertEqual(first, "Jean-Luc")
        self.assertEqual(last, "Picard")

    def test_name_patterns_multilingual(self):
        self.assertTrue(matches_any_pattern("first_name", NAME_PATTERNS["first_name"]))
        self.assertTrue(matches_any_pattern("candidate_first_name", NAME_PATTERNS["first_name"]))
        self.assertTrue(matches_any_pattern("prénom", NAME_PATTERNS["first_name"]))
        self.assertTrue(matches_any_pattern("nom de famille", NAME_PATTERNS["last_name"]))
        self.assertTrue(matches_any_pattern("candidate[email]", NAME_PATTERNS["email"]))
        self.assertTrue(matches_any_pattern("candidate[phone]", NAME_PATTERNS["phone"]))
        self.assertTrue(matches_any_pattern("téléphone", NAME_PATTERNS["phone"]))
        self.assertTrue(matches_any_pattern("candidate_location", NAME_PATTERNS["location"]))
        self.assertTrue(matches_any_pattern("address", NAME_PATTERNS["location"]))

    def test_apply_button_patterns(self):
        # Allowed
        self.assertTrue(matches_any_pattern("Apply for this job", APPLY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Postuler maintenant", APPLY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Candidater", APPLY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Easy Apply", APPLY_BUTTON_PATTERNS))

        # Denied
        self.assertTrue(matches_any_pattern("Save job", DENY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Sign in", DENY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Se connecter", DENY_BUTTON_PATTERNS))
        self.assertTrue(matches_any_pattern("Similar jobs", DENY_BUTTON_PATTERNS))


if __name__ == "__main__":
    unittest.main()

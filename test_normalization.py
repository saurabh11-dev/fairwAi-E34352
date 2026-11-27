"""Unit tests for field normalization in pipeline.py
"""

import unittest
from pipeline import clean_name, clean_email, is_usable_email, clean_phone, clean_state


class TestFieldNormalization(unittest.TestCase):

    def test_clean_name(self):
        self.assertEqual(clean_name("Marcus Patel"), "Marcus Patel")
        self.assertEqual(clean_name("  KHAN, Sofia "), "Sofia Khan")
        self.assertEqual(clean_name("zoe haddad"), "Zoe Haddad")
        self.assertEqual(clean_name("  REID, Jonas "), "Jonas Reid")
        self.assertEqual(clean_name(""), "")
        self.assertEqual(clean_name(None), "")

    def test_clean_email(self):
        self.assertEqual(clean_email("  DANA.MOREAU464@EXAMPLE.COM "), "dana.moreau464@example.com")
        self.assertEqual(clean_email(""), "")
        self.assertEqual(clean_email(None), "")

    def test_is_usable_email(self):
        self.assertTrue(is_usable_email("dana.moreau464@example.com"))
        self.assertTrue(is_usable_email("marcus.shah783+b@example.com"))
        self.assertFalse(is_usable_email("james.cruz399example.com"))  # Missing @
        self.assertFalse(is_usable_email("asdf"))
        self.assertFalse(is_usable_email(""))
        self.assertFalse(is_usable_email(None))

    def test_clean_phone(self):
        # 10 digit plain
        e164, flag = clean_phone("6174651312")
        self.assertEqual(e164, "+16174651312")
        self.assertIsNone(flag)

        # Dot format
        e164, flag = clean_phone("615.328.4539")
        self.assertEqual(e164, "+16153284539")
        self.assertIsNone(flag)

        # Parentheses format
        e164, flag = clean_phone("(303) 692-2636")
        self.assertEqual(e164, "+13036922636")
        self.assertIsNone(flag)

        # Country code prefix
        e164, flag = clean_phone("+1 3127911453")
        self.assertEqual(e164, "+13127911453")
        self.assertIsNone(flag)

        # Fictitious 999 area code
        e164, flag = clean_phone("9990007010")
        self.assertEqual(e164, "+19990007010")
        self.assertEqual(flag, "suspicious_phone_number")

        # Invalid short phone
        raw, flag = clean_phone("000")
        self.assertEqual(raw, "000")
        self.assertEqual(flag, "invalid_phone_digits_3")

    def test_clean_state(self):
        self.assertEqual(clean_state("Washington"), ("WA", None))
        self.assertEqual(clean_state("tn"), ("TN", None))
        self.assertEqual(clean_state("CO"), ("CO", None))
        self.assertEqual(clean_state("California"), ("CA", None))
        self.assertEqual(clean_state("ZZ"), ("ZZ", "unrecognized_state_code_ZZ"))


if __name__ == "__main__":
    unittest.main()

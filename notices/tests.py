"""
Unit tests for notices service and ReportLab PDF document export.
"""

from django.test import TestCase
from notices.services.pdf import generate_notice_pdf, MANDATORY_DISCLAIMER
from notices.services.generator import build_fallback_notice


class NoticePdfTest(TestCase):

    def test_pdf_generation_structure_and_disclaimer(self):
        draft_text = """
LEGAL DEMAND NOTICE
Date: 2026-11-10

TO:
Suresh Gupta, Landlord
Flat 101, New Delhi

1. That you have unlawfully withheld my security deposit of Rs 40,000.
2. That you are called upon to refund the same within 15 days under Model Tenancy Act, 2021.
"""
        pdf_buffer = generate_notice_pdf(draft_text, "SECURITY DEPOSIT DEMAND NOTICE")
        pdf_bytes = pdf_buffer.getvalue()

        # Verify PDF header
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output is not a valid PDF document!")

        # Verify PDF size is substantial
        self.assertGreater(len(pdf_bytes), 1000)

        # Verify buffer position is at 0
        self.assertEqual(pdf_buffer.tell(), 0)

    def test_fallback_notice_builder(self):
        form_data = {
            "notice_date": "2026-11-10",
            "sender_name": "Rohan Sharma",
            "sender_address": "Delhi",
            "recipient_name": "Gupta Landlord",
            "recipient_address": "Noida",
            "facts": "Security deposit not returned after vacating.",
            "relief_demanded": "Refund Rs 35,000 within 15 days."
        }
        fallback_text = build_fallback_notice("security_deposit", form_data)
        self.assertIn("Rohan Sharma", fallback_text)
        self.assertIn("Gupta Landlord", fallback_text)
        self.assertIn("Refund Rs 35,000 within 15 days.", fallback_text)
        self.assertIn("15 (fifteen) days", fallback_text)

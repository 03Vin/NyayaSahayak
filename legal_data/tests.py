"""
Unit tests for legal_data ingestion, cleaning, section-chunking, and definition clause splitting.
"""

from django.test import TestCase
from legal_data.services.ingest import (
    clean_statute_text,
    chunk_statute_by_sections,
    parse_definition_clauses,
    sub_split_large_text
)


class IngestServicesTest(TestCase):

    def test_clean_statute_text(self):
        sample_raw = """
        THE GAZETTE OF INDIA : EXTRAORDINARY
        [PART II—SEC. 3(i)]
        Page 12 of 45
        1. Short title, extent and commencement.
        (1) This Act may be called the Test Act, 2024.
        WWW.LIVELAW.IN
        """
        cleaned = clean_statute_text(sample_raw)
        self.assertNotIn("THE GAZETTE OF INDIA", cleaned)
        self.assertNotIn("[PART II—SEC. 3(i)]", cleaned)
        self.assertNotIn("Page 12 of 45", cleaned)
        self.assertNotIn("WWW.LIVELAW.IN", cleaned)
        self.assertIn("1. Short title", cleaned)

    def test_section_chunker(self):
        sample_statute = """
        1. Short title and extent.
        This Act applies to all consumers across India.

        3. Jurisdiction of District Commission.
        The District Commission shall have jurisdiction to entertain complaints where value does not exceed fifty lakh rupees.
        """
        meta = {
            "act_name": "Test Consumer Act",
            "act_year": 2024,
            "legal_area": "consumer",
            "legal_status": "in_force",
            "source_file": "consumer/test.txt"
        }
        chunks = chunk_statute_by_sections(sample_statute, meta, "test_act")
        self.assertGreaterEqual(len(chunks), 2)
        sec_numbers = [c["section_number"] for c in chunks]
        self.assertIn("1", sec_numbers)
        self.assertIn("3", sec_numbers)

    def test_definitions_clause_split(self):
        sample_sec2 = """
        2. Definitions.- In this Act, unless the context otherwise requires,--
        (1) "consumer" means any person who buys any goods for a consideration;
        (2) "defect" means any fault, imperfection or shortcoming in the quality;
        (3) "service" means service of any description which is made available to potential users.
        """
        meta = {
            "act_name": "Test Definitions Act",
            "act_year": 2024,
            "legal_area": "consumer",
            "legal_status": "in_force",
            "source_file": "consumer/test.txt"
        }
        chunks = parse_definition_clauses(sample_sec2, "test_slug", meta)
        self.assertGreaterEqual(len(chunks), 3)

        clause_ids = [c["section_number"] for c in chunks]
        self.assertIn("2(1)", clause_ids)
        self.assertIn("2(2)", clause_ids)
        self.assertIn("2(3)", clause_ids)

        titles = [c["section_title"] for c in chunks]
        self.assertTrue(any("consumer" in t.lower() for t in titles))
        self.assertTrue(any("defect" in t.lower() for t in titles))

    def test_sub_split_large_text(self):
        words = ["word" for _ in range(600)]
        long_text = " ".join(words[:250]) + "\n\n" + " ".join(words[250:500]) + "\n\n" + " ".join(words[500:])
        sub_chunks = sub_split_large_text(long_text, max_words=300)
        self.assertGreater(len(sub_chunks), 1)
        for part in sub_chunks:
            self.assertLessEqual(len(part.split()), 350)

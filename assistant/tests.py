"""
Unit tests for assistant services: temporal detector, status filtering,
confidence guardrails, citation validator, repealed statute warnings, and rate limiting.
All LLM provider calls are strictly mocked.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache

from assistant.services.temporal import is_pre_commencement_query
from assistant.services.rag import (
    validate_and_filter_citations,
    check_and_inject_repealed_warning,
    answer_legal_query
)
from assistant.services.rate_limiter import is_rate_limited, get_remaining_requests
from legal_data.models import LegalChunk


class TemporalDetectorTest(TestCase):

    def test_pre_commencement_phrases(self):
        # Questions with past years, old laws, or phrases before Nov 21, 2025
        self.assertTrue(is_pre_commencement_query("In 2023, my employer deducted salary."))
        self.assertTrue(is_pre_commencement_query("What were the rules under the old act?"))
        self.assertTrue(is_pre_commencement_query("Before the new code commenced in 2024"))
        self.assertTrue(is_pre_commencement_query("Deduction made under Payment of Wages Act 1936"))
        self.assertTrue(is_pre_commencement_query("Dispute dating back 3 years ago in 2022"))

    def test_current_commencement_phrases(self):
        # Current or forward-looking queries
        self.assertFalse(is_pre_commencement_query("My wages were not paid yesterday in 2026."))
        self.assertFalse(is_pre_commencement_query("What is the current minimum wage rate under Code on Wages?"))
        self.assertFalse(is_pre_commencement_query("Landlord is demanding 6 months deposit."))


class CitationValidatorTest(TestCase):

    def test_pruning_hallucinated_citations(self):
        retrieved_chunks = [
            {
                "act_name": "Consumer Protection Act, 2019",
                "section_number": "35",
                "section_title": "Manner of filing complaint",
                "legal_status": "in_force",
                "superseded_by": None
            },
            {
                "act_name": "Model Tenancy Act, 2021",
                "section_number": "11",
                "section_title": "Security deposit",
                "legal_status": "in_force",
                "superseded_by": None
            }
        ]

        raw_llm_citations = [
            {"act": "Consumer Protection Act, 2019", "section": "35"},      # Valid retrieved
            {"act": "Indian Penal Code", "section": "420"},                 # Hallucinated / Out-of-scope
            {"act": "Model Tenancy Act, 2021", "section": "11(1)(a)"},       # Valid sub-clause
            {"act": "Arbitration Act", "section": "34"}                     # Hallucinated
        ]

        validated = validate_and_filter_citations(raw_llm_citations, retrieved_chunks)
        self.assertEqual(len(validated), 2)
        acts = [v["act"] for v in validated]
        self.assertIn("Consumer Protection Act, 2019", acts)
        self.assertIn("Model Tenancy Act, 2021", acts)
        self.assertNotIn("Indian Penal Code", acts)
        self.assertNotIn("Arbitration Act", acts)


class RepealedWarningTest(TestCase):

    def test_warning_injected_when_repealed_act_cited(self):
        answer = "Under the Payment of Wages Act, 1936, Section 7, deductions are restricted to specified heads."
        citations = [
            {
                "act": "Payment of Wages Act, 1936",
                "section": "7",
                "legal_status": "repealed"
            }
        ]
        retrieved_chunks = [
            {
                "act_name": "Payment of Wages Act, 1936",
                "legal_status": "repealed",
                "section_number": "7"
            }
        ]

        result_answer = check_and_inject_repealed_warning(answer, citations, retrieved_chunks)
        self.assertTrue(result_answer.startswith("Note: the Payment of Wages Act, 1936 was repealed on 21 November 2025"))
        self.assertIn("replaced by the Code on Wages, 2019", result_answer)

    def test_warning_not_duplicated_if_already_present(self):
        existing_warning = (
            "Note: the Payment of Wages Act, 1936 was repealed on 21 November 2025 and replaced by the Code on Wages, 2019. "
            "For current situations, the Code on Wages applies.\n\nExplanation text..."
        )
        citations = [{"act": "Payment of Wages Act, 1936", "section": "7", "legal_status": "repealed"}]
        result_answer = check_and_inject_repealed_warning(existing_warning, citations, [])
        # Check that warning count does not double
        self.assertEqual(result_answer.lower().count("repealed on 21 november 2025"), 1)


class GuardrailAndRAGTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testcitizen", password="password123")

    @patch('assistant.services.rag.retrieve_relevant_chunks')
    @patch('assistant.services.rag.get_llm_provider')
    def test_guardrail_refusal_without_llm_call(self, mock_get_llm, mock_retrieve):
        """
        CRITICAL GUARDRAIL TEST: When top similarity score is below threshold,
        the system MUST refuse and MUST NEVER call the LLM provider.
        """
        mock_retrieve.return_value = {
            "chunks": [],
            "top_score": 0.22,  # Well below 0.35 threshold
            "confidence_label": "Low",
            "is_pre_commencement": False,
            "allow_repealed": False,
            "direct_hits_count": 0
        }

        res = answer_legal_query(
            question="What is the punishment for murder under IPC?",
            threshold=0.35,
            user=self.user
        )

        self.assertTrue(res["refused"])
        self.assertEqual(res["confidence_label"], "Refused")
        self.assertIn("I couldn't find a reliable legal basis", res["answer"])
        self.assertIn("15100", res["answer"])

        # Verify LLM provider was NEVER instantiated or invoked
        mock_get_llm.assert_not_called()

    @patch('assistant.services.rag.retrieve_relevant_chunks')
    @patch('assistant.services.rag.get_llm_provider')
    def test_successful_rag_flow_with_mocked_llm(self, mock_get_llm, mock_retrieve):
        mock_retrieve.return_value = {
            "chunks": [
                {
                    "act_name": "Consumer Protection Act, 2019",
                    "act_year": 2019,
                    "legal_area": "consumer",
                    "legal_status": "in_force",
                    "section_number": "35",
                    "section_title": "Manner in which complaint shall be made",
                    "text": "A complaint in relation to any goods sold or delivered...",
                    "chunk_id": "consumer_35",
                    "score": 0.65,
                    "is_direct_hit": False
                }
            ],
            "top_score": 0.65,
            "confidence_label": "High",
            "is_pre_commencement": False,
            "allow_repealed": False,
            "direct_hits_count": 0
        }

        mock_provider = MagicMock()
        mock_provider.generate_json.return_value = {
            "answer": "You can file a complaint before the District Commission under [Consumer Protection Act, 2019, Section 35].",
            "citations": [{"act": "Consumer Protection Act, 2019", "section": "35"}],
            "next_steps": ["Submit form electronically on e-Daakhil", "Attach proof of payment"],
            "answerable": True
        }
        mock_get_llm.return_value = mock_provider

        res = answer_legal_query(
            question="How do I file a consumer case against a company?",
            threshold=0.35,
            user=self.user
        )

        self.assertFalse(res["refused"])
        self.assertEqual(res["confidence_label"], "High")
        self.assertEqual(len(res["citations"]), 1)
        self.assertEqual(res["citations"][0]["section"], "35")
        mock_provider.generate_json.assert_called_once()


class RateLimiterTest(TestCase):

    def setUp(self):
        cache.clear()

    def test_hourly_rate_limiter(self):
        user_id = 9999
        # First 20 requests should be permitted
        for _ in range(20):
            self.assertFalse(is_rate_limited(user_id))

        # 21st request must be rate-limited
        self.assertTrue(is_rate_limited(user_id))
        self.assertEqual(get_remaining_requests(user_id), 0)

"""
Temporal Dispute Detection Helper for NyayaSahayak.
Detects whether a user query refers to a retrospective dispute or events
occurring before the Code on Wages commencement date (21 November 2025).
"""

import re
from datetime import date
from django.conf import settings

# Key phrases indicating historical or pre-commencement context
PRE_COMMENCEMENT_PHRASES = [
    r'\bbefore\s+(?:the\s+)?(?:new\s+)?code\b',
    r'\bbefore\s+2025\b',
    r'\bbefore\s+november\s+2025\b',
    r'\bbefore\s+21(?:\s*st)?\s+nov(?:ember)?(?:\s+2025)?\b',
    r'\bunder\s+(?:the\s+)?old\s+(?:act|law)\b',
    r'\bpending\s+(?:case|dispute|matter)\b',
    r'\bpayment\s+of\s+wages\s+act\s*,?\s*1936\b',
    r'\bminimum\s+wages\s+act\s*,?\s*1948\b',
    r'\b1936\s+act\b',
    r'\b1948\s+act\b',
    r'\bin\s+(?:19\d{2}|20[01]\d|202[0-4])\b',  # in 1900-2024
    r'\b(back\s+in|during|around)\s+(?:19\d{2}|20[01]\d|202[0-4])\b',
    r'\bjan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?\s+2025\b',
    r'\blast\s+year\b',
    r'\btwo\s+years\s+ago\b',
    r'\b3\s+years\s+ago\b',
    r'\byears\s+ago\b',
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PRE_COMMENCEMENT_PHRASES]


def is_pre_commencement_query(question: str) -> bool:
    """
    Returns True if the question mentions dates, years, or phrases prior to 21 Nov 2025.
    """
    if not question:
        return False

    q_lower = question.lower()

    for pattern in COMPILED_PATTERNS:
        if pattern.search(q_lower):
            return True

    # Check for specific year mentions like 2020, 2021, 2022, 2023, 2024
    year_matches = re.findall(r'\b(20[0-2][0-4])\b', q_lower)
    if year_matches:
        return True

    # Check for specific date before Nov 21, 2025
    # e.g., "15 October 2025", "10/05/2024"
    date_patterns = [
        r'\b(\d{1,2})[-/](\d{1,2})[-/](20[0-2][0-4])\b',
    ]
    for dp in date_patterns:
        if re.search(dp, q_lower):
            return True

    return False


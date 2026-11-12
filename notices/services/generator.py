"""
Legal Notice Draft Generation Service for NyayaSahayak.
Constructs formal legal notice demand letters using citizen-submitted facts
and retrieved statutory provisions.
"""

import logging
from typing import Dict, Any
from django.conf import settings
from assistant.services.llm import get_llm_provider
from assistant.services.temporal import is_pre_commencement_query

logger = logging.getLogger(__name__)

NOTICE_TEMPLATES_CONFIG = {
    "security_deposit": {
        "title": "Security Deposit Refund Demand Notice",
        "default_act": "Model Tenancy Act, 2021",
        "key_sections": "Section 11 (Security deposit limits and refund upon handing over vacant possession)",
        "area": "tenancy"
    },
    "defective_product": {
        "title": "Defective Product / Deficient Service Demand Notice",
        "default_act": "Consumer Protection Act, 2019",
        "key_sections": "Sections 2(9), 2(11), 35, and 84 (Deficiency of service, product liability, consumer compensation)",
        "area": "consumer"
    },
    "unpaid_wages": {
        "title": "Demand Notice for Unpaid Wages and Statutory Dues",
        "default_act": "Code on Wages, 2019",
        "key_sections": "Sections 17, 18, and 45 (Payment of wages, permissible deductions, and claims recovery)",
        "area": "labour"
    }
}


def build_notice_system_prompt() -> str:
    return """You are a senior legal draftsman specializing in Indian statutory notices.
Your task is to draft a formal, professional Legal Demand Notice based SOLELY on the user-provided facts and relevant statutes.

RULES:
1. Use a standard Indian legal notice structure:
   - SENDER DETAILS
   - RECIPIENT DETAILS (To, Name, Address)
   - SUBJECT LINE: Formal demand notice
   - BODY PARAGRAPHS:
     * Para 1: Client's capacity and relationship with the recipient.
     * Para 2: Sequence of facts, transaction details, specific dates, and amounts exactly as provided by the user.
     * Para 3: Statutory violation and relevant act and sections.
     * Para 4: Formal demand for relief and specific timeline (usually 15 days) to comply.
     * Para 5: Explicit warning that failure to comply will initiate civil and statutory proceedings before the appropriate forum/court at the recipient's sole risk and cost.
2. DO NOT invent facts, dates, invoice numbers, or monetary amounts. Use ONLY what the user provided.
3. Always include statutory citations:
   - Tenancy: Model Tenancy Act, 2021.
   - Consumer: Consumer Protection Act, 2019.
   - Labour: Code on Wages, 2019 by default.
4. For wages disputes: If the due date is before 21 November 2025, cite the Payment of Wages Act, 1936 or Minimum Wages Act, 1948 and add a line stating that the act was repealed on 21 November 2025 and that savings provisions apply to prior causes of action.
5. Tone: Formal, polite, firm, and legally precise.
6. Return output in JSON format with key "draft_text".
"""


def generate_notice_draft(notice_type: str, form_data: Dict[str, Any]) -> str:
    """
    Calls the LLM provider to draft the formal legal demand notice.
    """
    config = NOTICE_TEMPLATES_CONFIG.get(notice_type, NOTICE_TEMPLATES_CONFIG["security_deposit"])
    sender_name = form_data.get("sender_name", "")
    sender_address = form_data.get("sender_address", "")
    recipient_name = form_data.get("recipient_name", "")
    recipient_address = form_data.get("recipient_address", "")
    notice_date = form_data.get("notice_date", "")
    facts = form_data.get("facts", "")
    relief_demanded = form_data.get("relief_demanded", "")
    due_date = form_data.get("due_date", "")

    # Check temporal applicability for wages
    is_pre_2025 = False
    if notice_type == "unpaid_wages" and due_date:
        is_pre_2025 = is_pre_commencement_query(due_date)

    prompt = f"""
NOTICE TYPE: {config['title']}
STATUTORY BASIS: {config['default_act']} ({config['key_sections']})
PRE-COMMENCEMENT HISTORICAL DISPUTE: {is_pre_2025}

USER FACTS (USE ONLY THESE FACTS, DO NOT INVENT ANY INFORMATION):
- Date of Notice: {notice_date}
- Sender: {sender_name}, Address: {sender_address}
- Recipient: {recipient_name}, Address: {recipient_address}
- Date due / Event date: {due_date if due_date else 'As stated in facts'}
- Summary of Facts & Grievance:
{facts}

- Relief Demanded (Amounts, Actions, Timeline):
{relief_demanded}

Draft the complete legal demand notice in formal legal English.
Return JSON: {{"draft_text": "<full formal notice text here>"}}
"""

    llm = get_llm_provider()
    system_instruction = build_notice_system_prompt()

    try:
        response = llm.generate_json(prompt, system_instruction)
        draft = response.get("draft_text", "")
        if not draft:
            draft = response.get("answer", "")
        return draft.strip()
    except Exception as e:
        logger.error(f"Error drafting legal notice via LLM: {e}")
        # Fallback template if API fails
        return build_fallback_notice(notice_type, form_data)


def build_fallback_notice(notice_type: str, form_data: Dict[str, Any]) -> str:
    """
    Deterministic template fallback in case of LLM outage.
    """
    return f"""LEGAL DEMAND NOTICE
(Under Applicable Indian Statutory Provisions)

Date: {form_data.get('notice_date', '')}

FROM:
{form_data.get('sender_name', '')}
{form_data.get('sender_address', '')}

TO:
{form_data.get('recipient_name', '')}
{form_data.get('recipient_address', '')}

SUBJECT: FORMAL DEMAND NOTICE REGARDING {notice_type.upper().replace('_', ' ')}

Sir/Madam,

Under instructions from my client and on my own behalf, I hereby serve upon you this formal legal demand notice:

1. That the relevant facts and transaction details are as follows:
{form_data.get('facts', '')}

2. That your actions constitute a direct violation of statutory obligations under Indian law.

3. That you are hereby called upon to grant the following relief within 15 (fifteen) days of receipt of this notice:
{form_data.get('relief_demanded', '')}

4. Take notice that in the event of your failure to comply with the demands within the stipulated period of 15 days, appropriate legal proceedings, civil and statutory, shall be initiated against you before the competent forum at your sole risk, cost, and consequences.

Yours faithfully,

{form_data.get('sender_name', '')}
(Complainant / Claimant)
"""


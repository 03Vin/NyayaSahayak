"""
RAG Orchestration Service for NyayaSahayak.
Connects retrieval, confidence guardrail check, LLM generation, citation post-validation,
repealed law warnings injection, and cross-statutory section mapping.
"""

import csv
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from django.conf import settings

from assistant.services.retriever import retrieve_relevant_chunks
from assistant.services.llm import (
    get_llm_provider,
    build_system_instruction,
    format_context_prompt
)

logger = logging.getLogger(__name__)

# Cache for section mapping CSV
_SECTION_MAPPINGS: Optional[List[Dict[str, str]]] = None


def load_section_mappings() -> List[Dict[str, str]]:
    """
    Loads cross-statute section mappings from /data/acts/labour/section_mapping.csv.
    """
    global _SECTION_MAPPINGS
    if _SECTION_MAPPINGS is not None:
        return _SECTION_MAPPINGS

    mapping_file = settings.ACTS_DIR / "labour" / "section_mapping.csv"
    mappings = []
    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mappings.append(row)
        except Exception as e:
            logger.error(f"Error loading section mappings: {e}")

    _SECTION_MAPPINGS = mappings
    return _SECTION_MAPPINGS


def find_section_replacement(act_name: str, section_num: str) -> Optional[Dict[str, str]]:
    """
    Finds if an older repealed section has been mapped to a newer Code on Wages section.
    """
    mappings = load_section_mappings()
    for m in mappings:
        old_act = m.get("old_act", "").lower()
        old_sec = m.get("old_section", "").lower().replace("section", "").replace("sec", "").strip()
        sec_clean = section_num.lower().replace("section", "").replace("sec", "").strip()

        if old_act in act_name.lower() and (old_sec == sec_clean or old_sec in sec_clean):
            return m
    return None


def validate_and_filter_citations(raw_citations: List[Dict[str, str]], retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Post-validates citations: every cited (act, section) MUST exist among retrieved chunks.
    Discards hallucinated citations. Matches base section numbers and sub-clauses.
    """
    validated = []
    for cite in raw_citations:
        act = cite.get("act", "").strip()
        sec = cite.get("section", "").strip()
        if not act or not sec:
            continue

        # Extract base digits from section (e.g. '11(1)(a)' -> '11', 'Sched-11' -> '11')
        sec_clean = re.sub(r'[^0-9a-zA-Z]', '', sec).lower()
        sec_base_digits = re.search(r'\d+', sec)
        sec_base = sec_base_digits.group(0) if sec_base_digits else sec_clean

        # Check against retrieved chunks
        match_found = False
        for chunk in retrieved_chunks:
            chunk_act = chunk.get("act_name", "").lower()
            chunk_sec_raw = str(chunk.get("section_number", ""))
            chunk_sec_clean = re.sub(r'[^0-9a-zA-Z]', '', chunk_sec_raw).lower()
            chunk_digits = re.search(r'\d+', chunk_sec_raw)
            chunk_base = chunk_digits.group(0) if chunk_digits else chunk_sec_clean

            # Check if act name matches
            act_matches = (act.lower() in chunk_act or chunk_act in act.lower())

            # Check if section number matches either exact, substring, or same base section number
            sec_matches = (
                sec_clean == chunk_sec_clean
                or chunk_sec_clean in sec_clean
                or (sec_base and chunk_base and sec_base == chunk_base)
            )

            if act_matches and sec_matches:
                match_found = True
                validated.append({
                    "act": chunk.get("act_name"),
                    "section": chunk.get("section_number"),
                    "legal_status": chunk.get("legal_status", "in_force"),
                    "superseded_by": chunk.get("superseded_by"),
                    "title": chunk.get("section_title", "")
                })
                break

        if not match_found:
            logger.warning(f"Discarded hallucinated or non-retrieved citation: [{act}, Section {sec}]")

    return validated


def check_and_inject_repealed_warning(answer: str, citations: List[Dict[str, Any]], retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Ensures that any answer citing a repealed act begins with the mandatory warning.
    If LLM omitted the warning, injects it programmatically.
    """
    # Detect if any cited chunk or used chunk is repealed
    repealed_acts = set()
    for c in citations:
        if c.get("legal_status") == "repealed":
            repealed_acts.add(c.get("act"))

    if not repealed_acts:
        # Check retrieved chunks that might be cited in text
        for chunk in retrieved_chunks:
            if chunk.get("legal_status") == "repealed" and chunk.get("act_name") in answer:
                repealed_acts.add(chunk.get("act_name"))

    if not repealed_acts:
        return answer

    # Build warning for all cited repealed acts
    warnings = []
    for act_name in repealed_acts:
        warning_msg = (
            f"Note: the {act_name} was repealed on 21 November 2025 and replaced by the Code on Wages, 2019. "
            "This applies only to events before that date. For current situations, the Code on Wages, 2019 applies."
        )
        if "repealed on 21 november 2025" not in answer.lower():
            warnings.append(warning_msg)

    if warnings:
        full_warning = "\n\n".join(warnings) + "\n\n"
        return full_warning + answer

    return answer


def answer_legal_query(
    question: str,
    legal_area: str = "auto",
    include_repealed: bool = False,
    threshold: float = None,
    user: Any = None
) -> Dict[str, Any]:
    """
    Full end-to-end RAG pipeline:
    1. Retrieval & Confidence Scoring.
    2. Guardrail: Refusal when confidence is below threshold (NO LLM CALL).
    3. LLM Generation via JSON mode.
    4. Post-validation: Prune hallucinated citations.
    5. Repealed statute warning injection.
    6. Attaching model law & section replacement notes.
    """
    start_time = time.time()

    if threshold is None:
        threshold = settings.DEFAULT_CONFIDENCE_THRESHOLD

    # 1. Retrieve relevant statutory chunks
    retrieval_res = retrieve_relevant_chunks(
        question=question,
        legal_area=legal_area,
        include_repealed=include_repealed,
        threshold=threshold
    )

    chunks = retrieval_res["chunks"]
    top_score = retrieval_res["top_score"]
    confidence_label = retrieval_res["confidence_label"]
    is_pre_commencement = retrieval_res["is_pre_commencement"]

    # 2. GUARDRAIL: Refusal when top similarity score is below threshold
    # If below threshold, DO NOT CALL LLM
    if top_score < threshold and not any(c.get("is_direct_hit") for c in chunks):
        latency_ms = int((time.time() - start_time) * 1000)
        refusal_msg = (
            "I couldn't find a reliable legal basis for this question in the laws I have. "
            "Please consult a lawyer or a legal aid clinic. You can reach the National Legal Services Authority "
            "(NALSA) free legal aid helpline at 15100 or approach your District Legal Services Authority (DLSA)."
        )
        return {
            "question": question,
            "legal_area": legal_area,
            "answer": refusal_msg,
            "citations": [],
            "next_steps": [
                "Call the NALSA Free Legal Aid Helpline: 15100",
                "Visit your local District Legal Services Authority (DLSA) office located in the District Court complex.",
                "Consult a licensed advocate to evaluate specific remedy under state-specific laws."
            ],
            "retrieved_chunks": chunks,
            "retrieved_chunk_ids": [c["chunk_id"] for c in chunks],
            "top_score": top_score,
            "confidence_label": "Refused",
            "refused": True,
            "is_pre_commencement": is_pre_commencement,
            "has_repealed_citations": False,
            "has_model_law": False,
            "latency_ms": latency_ms
        }

    # 3. LLM Generation
    system_instruction = build_system_instruction()
    prompt = format_context_prompt(question, chunks)
    llm = get_llm_provider()

    try:
        llm_response = llm.generate_json(prompt, system_instruction)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": question,
            "legal_area": legal_area,
            "answer": "An error occurred while generating the legal analysis. Please try again or consult a legal aid clinic.",
            "citations": [],
            "next_steps": ["Retry your query in a few moments.", "Contact DLSA / NALSA (15100)."],
            "retrieved_chunks": chunks,
            "retrieved_chunk_ids": [c["chunk_id"] for c in chunks],
            "top_score": top_score,
            "confidence_label": confidence_label,
            "refused": False,
            "is_pre_commencement": is_pre_commencement,
            "has_repealed_citations": False,
            "has_model_law": False,
            "latency_ms": latency_ms,
            "error": str(e)
        }

    raw_answer = llm_response.get("answer", "")
    answerable = llm_response.get("answerable", True)
    raw_citations = llm_response.get("citations", [])
    next_steps = llm_response.get("next_steps", [])

    # If LLM itself reports that the sections don't answer the question
    if not answerable:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": question,
            "legal_area": legal_area,
            "answer": raw_answer or "The indexed statutes do not contain specific provisions answering this query. Please consult an advocate.",
            "citations": [],
            "next_steps": next_steps or ["Call NALSA helpline: 15100"],
            "retrieved_chunks": chunks,
            "retrieved_chunk_ids": [c["chunk_id"] for c in chunks],
            "top_score": top_score,
            "confidence_label": "Refused",
            "refused": True,
            "is_pre_commencement": is_pre_commencement,
            "has_repealed_citations": False,
            "has_model_law": False,
            "latency_ms": latency_ms
        }

    # 4. Post-Validate Citations (prune hallucinations)
    validated_citations = validate_and_filter_citations(raw_citations, chunks)

    # 5. Check and Inject Repealed Statute Warning
    final_answer = check_and_inject_repealed_warning(raw_answer, validated_citations, chunks)

    # 6. Check for Model Tenancy Act note
    has_model_law = any("model tenancy act" in c.get("act_name", "").lower() for c in chunks)
    has_repealed_citations = any(c.get("legal_status") == "repealed" for c in validated_citations)

    # Enrich chunks with replacement info from section_mapping.csv
    for chunk in chunks:
        if chunk.get("legal_status") == "repealed":
            mapping = find_section_replacement(chunk.get("act_name", ""), str(chunk.get("section_number", "")))
            if mapping and not mapping.get("new_section", "").startswith("TODO"):
                chunk["replacement_note"] = f"Now covered by {mapping['new_act']}, Section {mapping['new_section']}"

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "question": question,
        "legal_area": legal_area,
        "answer": final_answer,
        "citations": validated_citations,
        "next_steps": next_steps,
        "retrieved_chunks": chunks,
        "retrieved_chunk_ids": [c["chunk_id"] for c in chunks],
        "top_score": top_score,
        "confidence_label": confidence_label,
        "refused": False,
        "is_pre_commencement": is_pre_commencement,
        "has_repealed_citations": has_repealed_citations,
        "has_model_law": has_model_law,
        "latency_ms": latency_ms
    }


"""
Retriever Service for NyayaSahayak.
Combines exact statutory section lookup with semantic FAISS vector search,
incorporating legal domain filtering, temporal status gating (in_force vs. repealed),
and similarity confidence scoring.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
from django.conf import settings

from legal_data.models import LegalChunk
from legal_data.services.index_loader import get_faiss_index_and_metadata, get_embedding_model
from assistant.services.temporal import is_pre_commencement_query

logger = logging.getLogger(__name__)


def extract_direct_section_mentions(query: str) -> List[Dict[str, str]]:
    """
    Detects explicit mentions of sections and acts in query text.
    e.g. 'Section 17 of the Code on Wages', 'sec 11 model tenancy', 'section 35 Consumer Protection'
    """
    results = []
    # Pattern to capture "Section X of <Act Name>" or "Sec X <Act>"
    patterns = [
        re.compile(r'\b(?:section|sec\.?)\s*(\d+[A-Za-z]?)\s+(?:of\s+(?:the\s+)?)?([A-Za-z\s,]+?)(?:\.|$|,|\b(?:says|states|means|provides|applies)\b)', re.IGNORECASE),
        re.compile(r'\b([A-Za-z\s,]+?)\s+(?:section|sec\.?)\s*(\d+[A-Za-z]?)\b', re.IGNORECASE),
    ]

    for p in patterns:
        for match in p.finditer(query):
            groups = match.groups()
            if len(groups) == 2:
                # Determine which group is section number and which is act name
                if re.match(r'^\d+[A-Za-z]?$', groups[0]):
                    sec, act = groups[0].strip(), groups[1].strip()
                else:
                    act, sec = groups[0].strip(), groups[1].strip()

                if len(act) >= 4:
                    results.append({"section": sec, "act_keyword": act})

    return results


def lookup_direct_sections(mentions: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Fetches exact LegalChunk records from SQLite for identified direct section mentions.
    """
    chunks = []
    for item in mentions:
        sec = item["section"]
        act_kw = item["act_keyword"]
        # Search DB for matching section_number and act_name containing keyword
        matches = LegalChunk.objects.filter(
            section_number__iexact=sec,
            act_name__icontains=act_kw[:15]
        )
        for m in matches:
            chunks.append({
                "act_name": m.act_name,
                "act_year": m.act_year,
                "legal_area": m.legal_area,
                "legal_status": m.legal_status,
                "repealed_on": str(m.repealed_on) if m.repealed_on else None,
                "superseded_by": m.superseded_by,
                "section_number": m.section_number,
                "section_title": m.section_title,
                "text": m.text,
                "chunk_id": m.chunk_id,
                "source_file": m.source_file,
                "score": 1.0,  # Exact direct hit gets perfect score
                "is_direct_hit": True
            })
    return chunks


def compute_confidence(score: float, threshold: float = None) -> str:
    """
    Maps similarity score to confidence label (High / Medium / Low / Refused).
    """
    if threshold is None:
        threshold = settings.DEFAULT_CONFIDENCE_THRESHOLD

    bands = settings.CONFIDENCE_BANDS
    if score >= bands.get("high", 0.60):
        return "High"
    elif score >= bands.get("medium", 0.40):
        return "Medium"
    elif score >= threshold:
        return "Low"
    else:
        return "Low"


def retrieve_relevant_chunks(
    question: str,
    legal_area: str = "auto",
    include_repealed: bool = False,
    top_k: int = None,
    threshold: float = None
) -> Dict[str, Any]:
    """
    Main retrieval orchestrator:
    1. Detects direct section mentions.
    2. Determines temporal status gating (includes repealed only if pre-commencement or user opted in).
    3. Runs normalized vector search on FAISS index.
    4. Filters and ranks top-k chunks.
    5. Returns chunks with similarity scores and confidence label.
    """
    if top_k is None:
        top_k = settings.TOP_K
    if threshold is None:
        threshold = settings.DEFAULT_CONFIDENCE_THRESHOLD

    # Step 1: Temporal detection
    is_pre_commencement = is_pre_commencement_query(question)
    allow_repealed = include_repealed or is_pre_commencement

    # Step 2: Direct section lookup
    direct_mentions = extract_direct_section_mentions(question)
    direct_chunks = lookup_direct_sections(direct_mentions)

    # Step 3: Load FAISS index & metadata
    index, metadata = get_faiss_index_and_metadata()
    if index is None or not metadata:
        logger.warning("FAISS index or metadata unavailable.")
        return {
            "chunks": direct_chunks,
            "top_score": 1.0 if direct_chunks else 0.0,
            "confidence_label": "High" if direct_chunks else "Low",
            "is_pre_commencement": is_pre_commencement,
            "allow_repealed": allow_repealed,
        }

    # Step 4: Semantic Embedding & Search
    model = get_embedding_model()
    q_vec = model.encode([question], convert_to_numpy=True)
    faiss.normalize_L2(q_vec)

    # Search top candidates (search up to 40 candidates to allow area & status filtering)
    search_k = min(40, index.ntotal)
    scores, indices = index.search(q_vec.astype(np.float32), search_k)

    selected_chunks = []
    seen_chunk_ids = {c["chunk_id"] for c in direct_chunks}

    # Include direct chunks first
    selected_chunks.extend(direct_chunks)

    # Filter vector search results
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(metadata):
            continue

        chunk_meta = metadata[idx].copy()
        chunk_id = chunk_meta.get("chunk_id")

        if chunk_id in seen_chunk_ids:
            continue

        # Area filtering (if not auto)
        if legal_area and legal_area != "auto":
            if chunk_meta.get("legal_area") != legal_area:
                continue

        # Legal status filtering
        chunk_status = chunk_meta.get("legal_status", "in_force")
        if chunk_status == "repealed" and not allow_repealed:
            # Skip repealed chunks unless explicitly allowed
            continue

        chunk_meta["score"] = float(score)
        chunk_meta["is_direct_hit"] = False
        selected_chunks.append(chunk_meta)
        seen_chunk_ids.add(chunk_id)

        if len(selected_chunks) >= top_k:
            break

    # Determine top similarity score (from semantic candidates or direct hits)
    semantic_scores = [c["score"] for c in selected_chunks if not c.get("is_direct_hit")]
    top_score = max(semantic_scores) if semantic_scores else (1.0 if direct_chunks else 0.0)

    confidence = compute_confidence(top_score, threshold)

    return {
        "chunks": selected_chunks[:top_k],
        "top_score": float(top_score),
        "confidence_label": confidence,
        "is_pre_commencement": is_pre_commencement,
        "allow_repealed": allow_repealed,
        "direct_hits_count": len(direct_chunks)
    }


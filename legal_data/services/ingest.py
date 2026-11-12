"""
Ingestion Service for NyayaSahayak.
Extracts text from statutory PDF/TXT files, cleans gazette/page artifacts,
chunks text by legal sections (including sub-splitting definition clauses),
generates normalized multilingual embeddings, and builds a FAISS IndexFlatIP index.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from django.conf import settings
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extracts raw text from a PDF using pypdf, falling back to pdfplumber if needed.
    """
    text_parts = []
    try:
        reader = PdfReader(str(pdf_path))
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    except Exception as e:
        logger.warning(f"pypdf extraction failed for {pdf_path}: {e}. Attempting fallback to pdfplumber.")
        try:
            import pdfplumber
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e2:
            logger.error(f"pdfplumber extraction also failed for {pdf_path}: {e2}")
            raise RuntimeError(f"Could not extract text from {pdf_path}: {e2}")

    return "\n".join(text_parts)


def extract_text_from_file(file_path: Path) -> str:
    """
    Extracts text from .pdf or .txt file.
    """
    suffix = file_path.suffix.lower()
    if suffix == '.pdf':
        return extract_text_from_pdf(file_path)
    elif suffix in ('.txt', '.text'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def clean_statute_text(raw_text: str) -> str:
    """
    Cleans official gazette artifacts, repeated headers, footers, page numbers,
    and removes initial Table of Contents / Arrangement of Clauses tables
    so substantive sections are accurately indexed.
    """
    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove Gazette of India headers and Part II notifications
    text = re.sub(r'THE\s+GAZETTE\s+OF\s+INDIA\s*:\s*EXTRAORDINARY', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[PART\s+II—SEC\.\s*3\(i\)\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[PART\s+II—SEC\.\s*1\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'EXTRAORDINARY\s+PART\s+II', '', text, flags=re.IGNORECASE)
    text = re.sub(r'MINISTRY\s+OF\s+LAW\s+AND\s+JUSTICE.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'REGD\.\s*NO\.\s*[A-Z0-9\-\/]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'WWW\.LIVELAW\.IN', '', text, flags=re.IGNORECASE)

    # Remove page numbers like "Page 12 of 45" or bare digits on standalone lines
    text = re.sub(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Strip Table of Contents / Arrangement of Sections if present before substantive enactment
    toc_match = re.search(r'(?:ARRANGEMENT OF SECTIONS|ARRANGEMENT OF CLAUSES|\bClauses\s*\n\s*1\.)', text, re.IGNORECASE)
    body_start = re.search(r'\b(?:THE\s+[A-Z\s,]+ACT,\s*\d{4}\s*\n\s*ACT\s+NO\.|An\s+Act\s+to\b|BE\s+it\s+enacted\s+by\s+Parliament\b)', text, re.IGNORECASE)
    if toc_match and body_start and body_start.start() > toc_match.start():
        text = text[body_start.start():]

    # Normalize excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_definition_clauses(sec2_text: str, act_slug: str, base_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Sub-splits Section 2 (Definitions) by clause so terms can be searched semantically.
    Matches clauses like '(1) "consumer" means...', '(a) "wages" means...', '(za) "landlord"...'
    """
    clause_pattern = re.compile(
        r'^\s*(?:\(([a-z0-9]+)\))\s*(?:“|"|\'|‘)?([^"”\'’\n]+?)(?:”|"|\'|’)?\s+means\b',
        re.MULTILINE | re.IGNORECASE
    )

    matches = list(clause_pattern.finditer(sec2_text))
    if not matches:
        clause_pattern = re.compile(r'^\s*(?:\(([a-z0-9]+)\))\s+', re.MULTILINE)
        matches = list(clause_pattern.finditer(sec2_text))

    if not matches:
        return [{
            **base_meta,
            "section_number": "2",
            "section_title": "Definitions",
            "text": sec2_text.strip(),
            "chunk_id": f"{act_slug}_sec_2_0"
        }]

    chunks = []
    for i, match in enumerate(matches):
        clause_id = match.group(1)
        start_idx = match.start()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(sec2_text)
        clause_text = sec2_text[start_idx:end_idx].strip()

        term_match = re.search(r'(?:“|"|\'|‘)([^"”\'’]+?)(?:”|"|\'|’)', clause_text)
        defined_term = term_match.group(1).strip() if term_match else f"Clause ({clause_id})"

        chunks.append({
            **base_meta,
            "section_number": f"2({clause_id})",
            "section_title": f"Definitions - {defined_term}",
            "text": clause_text,
            "chunk_id": f"{act_slug}_sec_2_clause_{clause_id}"
        })

    return chunks


def sub_split_large_text(text: str, max_words: int = 400) -> List[str]:
    """
    Sub-splits section text exceeding max_words into contiguous paragraphs or sentences.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current_para = []
    current_count = 0

    for para in paragraphs:
        para_word_count = len(para.split())
        if current_count + para_word_count > max_words and current_para:
            chunks.append("\n\n".join(current_para).strip())
            current_para = [para]
            current_count = para_word_count
        else:
            current_para.append(para)
            current_count += para_word_count

    if current_para:
        chunks.append("\n\n".join(current_para).strip())

    return chunks if chunks else [text]


def chunk_statute_by_sections(cleaned_text: str, act_metadata: Dict[str, Any], act_slug: str) -> List[Dict[str, Any]]:
    """
    Parses cleaned statute text into section-level chunks.
    Recognizes patterns such as:
    - '12. Short title...' or '12. Title.-'
    - 'Section 12. Title'
    - '11. (1) The security deposit...'
    """
    # Detect if and where schedules start to avoid numbering confusion
    sched_match = re.search(r'\b(?:THE FIRST SCHEDULE|THE SCHEDULE)\b', cleaned_text, re.IGNORECASE)
    sched_pos = sched_match.start() if sched_match else len(cleaned_text)

    section_pattern = re.compile(
        r'^\s*(?:Section\s+)?(\d{1,3}[A-Z]?)\.\s*(?:\([0-9a-zA-Z]+\)\s*)?([^\n]{2,80}?)(?:[\.\—\-]+|\n|$)',
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(cleaned_text))

    if len(matches) < 5:
        section_pattern = re.compile(
            r'^\s*(?:Section\s+)?(\d{1,3}[A-Z]?)\.\s+([^\n]{3,60}?)(?:[\.\—\-]+|\n)',
            re.MULTILINE
        )
        matches = list(section_pattern.finditer(cleaned_text))

    chunks: List[Dict[str, Any]] = []

    if not matches:
        logger.warning(f"Could not parse section headings for {act_metadata['act_name']}. Chunking by fixed size.")
        paragraphs = sub_split_large_text(cleaned_text, max_words=350)
        for idx, p in enumerate(paragraphs):
            chunks.append({
                **act_metadata,
                "section_number": f"General-{idx+1}",
                "section_title": "General Text",
                "text": p,
                "chunk_id": f"{act_slug}_gen_{idx}"
            })
    else:
        for i, match in enumerate(matches):
            sec_num = match.group(1).strip()
            sec_title = match.group(2).strip().rstrip('.-—')
            start_idx = match.start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned_text)

            # Check if this match is in the Schedules section
            if start_idx >= sched_pos:
                sec_num = f"Sched-{sec_num}"

            sec_body = cleaned_text[start_idx:end_idx].strip()

            if sec_num == "2":
                def_chunks = parse_definition_clauses(sec_body, act_slug, act_metadata)
                chunks.extend(def_chunks)
                continue

            word_count = len(sec_body.split())
            if word_count > 420:
                sub_parts = sub_split_large_text(sec_body, max_words=380)
                for part_idx, part_text in enumerate(sub_parts):
                    chunks.append({
                        **act_metadata,
                        "section_number": sec_num,
                        "section_title": sec_title[:100],
                        "text": part_text,
                        "chunk_id": f"{act_slug}_sec_{sec_num}_p{part_idx}"
                    })
            else:
                chunks.append({
                    **act_metadata,
                    "section_number": sec_num,
                    "section_title": sec_title[:100],
                    "text": sec_body,
                    "chunk_id": f"{act_slug}_sec_{sec_num}_0"
                })

    # Guarantee chunk_id uniqueness across all chunks
    seen_ids = set()
    for c in chunks:
        base_id = c["chunk_id"]
        candidate = base_id
        counter = 1
        while candidate in seen_ids:
            candidate = f"{base_id}_{counter}"
            counter += 1
        c["chunk_id"] = candidate
        seen_ids.add(candidate)

    return chunks


def build_faiss_index(chunks: List[Dict[str, Any]], output_dir: Path) -> Tuple[int, Path, Path]:
    """
    Encodes chunk texts using sentence-transformers, normalizes vectors,
    builds FAISS IndexFlatIP (cosine similarity), and saves index + metadata JSON.
    """
    import faiss
    from sentence_transformers import SentenceTransformer

    output_dir.mkdir(parents=True, exist_ok=True)
    index_file = output_dir / "acts.index"
    metadata_file = output_dir / "metadata.json"

    if not chunks:
        dim = 384
        index = faiss.IndexFlatIP(dim)
        faiss.write_index(index, str(index_file))
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump([], f)
        return 0, index_file, metadata_file

    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

    texts_to_embed = [
        f"Act: {c['act_name']}. Section {c['section_number']}: {c['section_title']}.\n{c['text']}"
        for c in chunks
    ]

    logger.info(f"Encoding {len(texts_to_embed)} chunks on CPU...")
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32, convert_to_numpy=True)

    # Normalize vectors for Inner Product = Cosine Similarity
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    faiss.write_index(index, str(index_file))

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    logger.info(f"FAISS index successfully saved to {index_file} ({index.ntotal} vectors).")
    return index.ntotal, index_file, metadata_file

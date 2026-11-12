# NyayaSahayak System Architecture

**NyayaSahayak** is a specialized Retrieval-Augmented Generation (RAG) legal aid platform designed for ordinary Indian citizens. It enforces strict statutory grounding, temporal enforceability awareness (in force vs. repealed acts), confidence-based refusal guardrails, and deterministic post-validation to eliminate hallucinations.

---

## 1. Offline Ingestion Pipeline

The ingestion pipeline transforms raw statutory documents (`.pdf` or `.txt`) from `data/acts/` into section-level indexed chunks with complete enforceability metadata.

```mermaid
flowchart TD
    A["Official Statutory Texts (/data/acts/)<br/>Consumer / Tenancy / Labour"] --> B["act_status.json<br/>Metadata Registry Validation"]
    B --> C["PDF / TXT Text Extraction<br/>pypdf + pdfplumber fallback"]
    C --> D["Statute Text Cleaning<br/>Strip Gazette lines, Page headers, TOC"]
    D --> E["Section-Level Chunker<br/>Regex pattern: ^\s*(Section)? \d+[A-Z]?\."]
    E --> F["Definitions Splitter (Section 2)<br/>Clause-by-clause sub-splitting: (1), (a), (b)"]
    E --> G["Long Section Sub-Splitter<br/>Split sections > 400 words"]
    F --> H["Normalized Chunk Assembly<br/>act_name, year, status, section, text, chunk_id"]
    G --> H
    H --> I["SQLite Database<br/>LegalChunk Model"]
    H --> J["Multilingual Sentence Transformer<br/>paraphrase-multilingual-MiniLM-L12-v2"]
    J --> K["L2 Vector Normalization"]
    K --> L["FAISS IndexFlatIP (Cosine Similarity)<br/>/data/index/acts.index"]
    H --> M["Metadata JSON<br/>/data/index/metadata.json"]
```

### Ingestion Stages
1. **Registry Verification:** Every file must match an entry in `act_status.json` with an explicit enforceability status (`in_force` or `repealed`), repealed date, and superseding law.
2. **Table of Contents Stripping:** Initial legislative arrangements of clauses are removed so that substantive statutory provisions are not shadowed by TOC entries.
3. **Clause-Level Definition Splitting:** Section 2 definitions (e.g. "consumer", "wages", "defect", "tenant") are sub-chunked by clause, enabling high-precision semantic lookup.
4. **Vector Embedding:** Chunks are embedded on CPU using `paraphrase-multilingual-MiniLM-L12-v2` and indexed via an inner product FAISS index (`IndexFlatIP`).

---

## 2. Online Citizen Query & RAG Workflow

The online flow handles plain-language legal queries in English or Hindi, enforces confidence guardrails, executes strict LLM inference, and validates citations.

```mermaid
flowchart TD
    U["Citizen Submits Dispute Query<br/>(Optional: Domain & Include Repealed)"] --> T["Temporal Dispute Detector<br/>Detects pre-Nov 21, 2025 phrases & dates"]
    U --> D["Direct Section Mention Lookup<br/>e.g. 'Section 11 Model Tenancy'"]
    U --> E["Query Vector Embedding<br/>paraphrase-multilingual-MiniLM-L12-v2"]
    
    E --> F["FAISS Vector Search<br/>Inner Product Cosine Similarity"]
    D --> G["Candidate Merging & Domain Filter<br/>(Consumer / Tenancy / Labour / Auto)"]
    F --> G
    
    G --> H{"Legal Status Filter<br/>Is chunk repealed?"}
    H -- "Repealed AND<br/>(pre-2025 OR user checked)" --> I["Include in Top-K Set"]
    H -- "Repealed AND current situation" --> J["Exclude Chunk (Suppress)"]
    H -- "In Force" --> I
    
    I --> K["Top-K Statutory Chunks (k=5)<br/>Compute Top Similarity Score"]
    
    K --> L{"Confidence Guardrail Check<br/>Is Top Score >= 0.35 Threshold?"}
    
    L -- "NO (Below Threshold)" --> M["REFUSAL GUARDRAIL<br/>DO NOT CALL LLM<br/>Advise DLSA & NALSA Toll-Free 15100"]
    
    L -- "YES (Passed)" --> N["Construct Context Prompt<br/>+ Strict System Prompt"]
    N --> O["Google Gemini API (JSON Mode)<br/>gemini-2.5-flash via google-genai SDK"]
    
    O --> P["JSON Repair & Parsing"]
    P --> Q["Citation Post-Validator<br/>Prune any citation not in retrieved chunks"]
    
    Q --> R{"Repealed Statute Cited?"}
    R -- "Yes" --> S["Inject Mandatory Warning:<br/>Repealed on 21 Nov 2025 by Code on Wages"]
    R -- "No" --> T2["Check Model Law Notice<br/>(Model Tenancy Act)"]
    S --> T2
    
    T2 --> V["Save Query & Latency in Database"]
    V --> W["Render Clean Bootstrap 5 UI<br/>Citations, Collapsible Source Text & Next Steps"]
```

---

## 3. Legal Notice Generation Flow

Citizens can generate formal demand letters based on structured dispute facts.

```mermaid
sequenceDiagram
    autonumber
    actor User as Citizen
    participant UI as Django View (notices)
    participant Gen as Generator Service
    participant LLM as Google Gemini (v1beta JSON)
    participant PDF as ReportLab PDF Engine

    User->>UI: Select Notice Type & Submit Facts Form
    Note over UI: Validates inputs, dates, and relief amounts
    UI->>Gen: generate_notice_draft(notice_type, form_data)
    Gen->>Gen: Check temporal applicability (pre-2025 wages)
    Gen->>LLM: Prompt with user facts & statutory requirements
    LLM-->>Gen: Return structured draft notice
    Gen-->>UI: Save NoticeDraft to SQLite
    UI-->>User: Display editable draft preview
    User->>UI: Request PDF Download
    UI->>PDF: generate_notice_pdf(draft_text, title)
    PDF-->>User: Stream printable A4 PDF with Advocate Review Disclaimer
```


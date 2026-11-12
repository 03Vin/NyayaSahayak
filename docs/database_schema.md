# NyayaSahayak Database Schema

The NyayaSahayak database is implemented in SQLite (default for development and evaluation) using Django ORM.

---

## Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    auth_user ||--o{ assistant_query : "submits"
    auth_user ||--o{ notices_noticedraft : "drafts"
    evaluation_evalrun ||--o{ evaluation_evalresult : "records"
    evaluation_evalquestion ||--o{ evaluation_evalresult : "evaluated_in"

    auth_user {
        int id PK
        string username
        string email
        string password
        boolean is_staff
        datetime date_joined
    }

    legal_data_legalchunk {
        int id PK
        string act_name
        int act_year
        string legal_area "consumer | tenancy | labour"
        string legal_status "in_force | repealed"
        date repealed_on
        string superseded_by
        string section_number
        string section_title
        text text
        string chunk_id UK
        string source_file
        datetime created_at
    }

    assistant_query {
        int id PK
        int user_id FK
        text question
        string legal_area "auto | consumer | tenancy | labour"
        boolean include_repealed
        text answer
        json citations
        json next_steps
        json retrieved_chunk_ids
        float top_score
        string confidence_label "High | Medium | Low | Refused"
        boolean refused
        int latency_ms
        datetime created_at
    }

    notices_noticedraft {
        int id PK
        int user_id FK
        string notice_type "security_deposit | defective_product | unpaid_wages"
        json form_data
        text draft_text
        datetime created_at
    }

    evaluation_evalquestion {
        int id PK
        text question
        string expected_act
        string expected_section
        boolean should_refuse
        string legal_area
        boolean expects_repealed_allowed
        boolean needs_verification
        datetime created_at
    }

    evaluation_evalrun {
        int id PK
        float threshold
        float top1_accuracy
        float top3_accuracy
        float refusal_precision
        float refusal_recall
        float repealed_misuse_rate
        float avg_latency_ms
        text notes
        datetime created_at
    }

    evaluation_evalresult {
        int id PK
        int run_id FK
        int question_id FK
        json retrieved
        float top_score
        boolean correct_top1
        boolean correct_top3
        boolean refused
        boolean passed
    }
```

---

## Model Specifications & Indexes

### 1. `LegalChunk` (`legal_data`)
- **Indexes:**
  - `(legal_area, legal_status)` compound index for accelerated filtered vector search matching.
  - `(act_name, section_number)` compound index for direct section lookups.
  - `chunk_id` unique index.

### 2. `Query` (`assistant`)
- **Indexes:**
  - `created_at` index for historical sorting.
  - `refused` index for audit and evaluation queries.
  - Foreign key on `auth_user`.

### 3. `NoticeDraft` (`notices`)
- **Indexes:**
  - `created_at` descending index.
  - Foreign key on `auth_user`.

### 4. `EvalRun` and `EvalResult` (`evaluation`)
- Captures automated benchmark execution metrics (Top-1, Top-3, Refusal Precision/Recall, Repealed Misuse Rate, Latency).
- Linked through `run_id` and `question_id` foreign keys.


# Legal Acts Repository (NyayaSahayak)

This directory stores official Indian statutory texts in `.pdf` or `.txt` format across the three supported domains.

## Directory Structure & Required Filenames

Place the official statutory acts under their respective legal area subdirectories using these exact filenames:

### 1. Consumer Law (`data/acts/consumer/`)
- `consumer_protection_act_2019.pdf` (or `.txt`)
  - **Act Title**: Consumer Protection Act, 2019 (Act No. 35 of 2019)
  - **Source**: [India Code - Consumer Protection Act 2019](https://www.indiacode.nic.in/handle/123456789/15256)
  - **Status**: **In Force**

### 2. Tenancy Law (`data/acts/tenancy/`)
- `model_tenancy_act_2021.pdf` (or `.txt`)
  - **Act Title**: Model Tenancy Act, 2021
  - **Source**: Ministry of Housing and Urban Affairs (MoHUA) / India Code
  - **Status**: **In Force (Model Law)**
  - *Note*: As a model act, state-level adoptions or state rent control legislation may govern local disputes.

### 3. Labour & Wages (`data/acts/labour/`)
- `code_on_wages_2019.pdf` (or `.txt`)
  - **Act Title**: Code on Wages, 2019 (Act No. 29 of 2019)
  - **Source**: [India Code - Code on Wages 2019](https://www.indiacode.nic.in/handle/123456789/15298)
  - **Status**: **In Force** (Commenced 21 November 2025)
  - Primary governing statute for all wage disputes, deductions, and minimum wage norms.

- `payment_of_wages_act_1936.pdf` (or `.txt`)
  - **Act Title**: Payment of Wages Act, 1936 (Act No. 4 of 1936)
  - **Source**: [India Code - Payment of Wages Act 1936](https://www.indiacode.nic.in/handle/123456789/2387)
  - **Status**: **Repealed** on 21 November 2025 by Code on Wages, 2019.
  - Used solely for pre-commencement retrospective dispute queries.

- `minimum_wages_act_1948.pdf` (or `.txt`)
  - **Act Title**: Minimum Wages Act, 1948 (Act No. 11 of 1948)
  - **Source**: [India Code - Minimum Wages Act 1948](https://www.indiacode.nic.in/handle/123456789/2393)
  - **Status**: **Repealed** on 21 November 2025 by Code on Wages, 2019.
  - Used solely for pre-commencement retrospective dispute queries.

---

## Metadata & Legal Status Registry

The `act_status.json` file in this directory maintains the canonical metadata for all files. The ingestion pipeline (`python manage.py ingest_acts`) reads `act_status.json` and verifies that every ingested file has a registered legal status.

## Section Mapping for Repealed Labour Acts

See `data/acts/labour/section_mapping.csv` for cross-statute section mappings (e.g. mapping older Payment of Wages sections to their corresponding sections under the Code on Wages, 2019).


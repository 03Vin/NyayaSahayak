# NyayaSahayak: 5-Minute Final-Year Project Demo Script

This script provides an interactive step-by-step walkthrough for project presentation, faculty viva, or client demonstration.

---

## Pre-Demo Setup
1. Ensure the development server is running:
   ```bash
   python manage.py runserver
   ```
2. Open your web browser to `http://127.0.0.1:8000/`.
3. Sign in using the pre-seeded demo accounts (`python manage.py seed_demo`):
   - **Citizen Account:** `citizen_demo` / `DemoUser@123`
   - **Admin / Staff Account:** `admin` / `NyayaAdmin@123`

---

## Minute 1: The Problem & System Landing Page
1. **Explain the Motivation:**
   > *"Ordinary Indian citizens struggle to understand their rights in tenancy disputes, consumer grievances, and unpaid wage claims. Standard chatbots hallucinate laws, cite non-existent sections, and frequently present repealed statutes as active law. NyayaSahayak solves this by grounding answers strictly in verified Indian statutes using RAG, enforcing confidence refusal guardrails, and recognizing temporal legal enforceability."*
2. **Show the Home Page:**
   - Point out the 3 covered legal domains (Consumer, Tenancy, Labour).
   - Point out the statutory status indicators (`In Force`, `Model Law`, `Repealed`).
   - Highlight the persistent legal disclaimer and NALSA toll-free helpline `15100`.

---

## Minute 2: Scenario 1 — In-Force Tenancy Question
1. Navigate to **"Ask Question"** (`/assistant/ask/`).
2. **Submit Question:**
   > *"What is the maximum security deposit a landlord can demand in advance under the tenancy law, and when must it be refunded?"*
3. **Point out the Output Highlights:**
   - **Confidence Indicator:** Displays `Medium` or `High` Confidence score.
   - **Statutory Analysis:** Readable plain-language explanation citing **Model Tenancy Act, 2021, Section 11** (not exceeding 2 months for residential, 6 months for non-residential, and refunded upon handing over vacant possession).
   - **Model Law Warning:** The amber banner noting that the Model Tenancy Act is a model law and local state rent acts may apply.
   - **Expandable Citation Badges:** Click the citation badge to expand and display the exact statutory source text.
   - **Next Steps:** Actionable steps for the citizen.

---

## Minute 3: Scenario 2 — Out-of-Scope Guardrail Refusal
1. In the Ask form, submit an out-of-scope question:
   > *"How do I file for mutual consent divorce under the Hindu Marriage Act?"*
2. **Point out the Guardrail Behavior:**
   - **No LLM Hallucination:** The system checks similarity score against indexed consumer, tenancy, and labour statutes.
   - **Automated Refusal:** The system triggers the guardrail:
     > *"I couldn't find a reliable legal basis for this question in the laws I have. Please consult a lawyer or a legal aid clinic."*
   - **Free Legal Aid Guidance:** Directs the citizen to the National Legal Services Authority (NALSA) toll-free helpline `15100` and the District Legal Services Authority (DLSA).
   - **Token & Cost Efficiency:** Because the score was below the threshold, the LLM was **not called**, preventing hallucinations and saving API quota.

---

## Minute 4: Scenario 3 — Retrospective Labour Dispute & Repealed Law Warning
1. Submit a historical dispute question:
   > *"In 2023, my employer made unauthorized deductions from my wages without notice."*
2. **Point out the Temporal Logic:**
   - **Automatic Pre-Commencement Detection:** The system detects `"In 2023"` as occurring before the Code on Wages commencement date (`2025-11-21`).
   - **Repealed Law Allowance:** Allows the Payment of Wages Act, 1936 to be retrieved for historical context.
   - **Mandatory Warning Banner:** The generated response begins with the visible statutory warning:
     > *"Note: the Payment of Wages Act, 1936 was repealed on 21 November 2025 and replaced by the Code on Wages, 2019. This applies only to events before that date. For current situations, the Code on Wages, 2019 applies."*
   - **Grey "Repealed" Citation Badge:** Distinguishes repealed law from in-force law.

---

## Minute 5: Scenario 4 & 5 — Legal Notice Generator & Evaluation Dashboard
1. **Notice Generator (`/notices/`):**
   - Click **"Draft Deposit Notice"**.
   - Show the pre-filled guided form (Sender, Landlord, Tenancy Date, Deposit Amount of Rs 40,000, Relief Demanded).
   - Click **"Generate Formal Notice Draft"**.
   - Show the formal legal demand notice citing the Model Tenancy Act.
   - Show that the user can edit text directly in the browser.
   - Click **"Download PDF"** and open the generated ReportLab PDF to display the formal formatting and the advocate review disclaimer.
2. **Staff Evaluation Dashboard (`/evaluation/results/`):**
   - Log in as `admin`.
   - Show the quantitative evaluation metrics across the 48 test cases:
     - Top-1 and Top-3 retrieval accuracy.
     - 100% Refusal Precision on out-of-scope questions.
     - 0% Repealed-law misuse on current situations.
   - Mention the management command `python manage.py run_eval --sweep` for automated threshold calibration.


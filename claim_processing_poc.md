# 🏥 Claim Processing — POC Design

> Mirrors the existing OCR workflow. Agent-based, explainable, report-driven.

---

## Workflow Overview

Just like the OCR workflow has agents calling tools, the Claim Processing workflow works the same way.

```
Documents (already OCR'd)
          │
          ▼
    OCR Text / Extracted Data
          │
          ▼
  ┌────────────────────────────┐
  │   Claim Processing         │
  │        Workflow            │
  │                            │
  │  ┌─────────────────────┐   │
  │  │ Agent 1: Integrity  │   │
  │  │   └── tools         │   │
  │  ├─────────────────────┤   │
  │  │ Agent 2: Medical    │   │
  │  │   └── tools         │   │
  │  ├─────────────────────┤   │
  │  │ Agent 3: Treatment  │   │
  │  │   └── tools         │   │
  │  ├─────────────────────┤   │
  │  │ Agent 4: Disability │   │
  │  │   └── tools         │   │
  │  ├─────────────────────┤   │
  │  │ Agent 5: Litigation │   │
  │  │   └── tools         │   │
  │  └─────────────────────┘   │
  └────────────────────────────┘
          │
          ▼
    📋 Claim Report
    (Not a decision — a full explainable report
     with a suggestion at the end)
```

---

## How Each Agent Works

Each agent is responsible for **one validator check**. It has:
- A **system prompt** defining what to check and how to reason
- A set of **tools** to fetch data from the DB (field-value pairs saved by OCR)
- An **output** with full explainability — what it checked, what it found, and why it passed or failed

```
Agent starts
        │
        ▼
  Calls fetch tools → gets field-value pairs from DB
  (only the documents it needs)
        │
        ▼
  LLM reads the fetched data
  and performs all checks as per system prompt
        │
        ▼
  Returns structured result:
  {
    check_name,
    status,       ← PASS / FAIL
    checks[],     ← each individual check done
    reason,       ← plain English explanation
    evidence      ← specific field values that led to this
  }
```

---

## Shared Tools (3 Total)

These are the only tools across all 5 agents. All are **data fetchers only** — the LLM does all reasoning.

| Tool | What it fetches | Who uses it |
|---|---|---|
| `get_claim_documents_data(claim_id, doc_types[])` | Field-value pairs from OCR output for specified document types | All agents |
| `get_claimant_history(claimant_id)` | Prior claims count and dates from DB | Integrity, Litigation |
| `get_policy_details(policy_id)` | Policy start/end date, coverage type from DB | Integrity |

---

## The 5 Agents & Their Tools

---

### Agent 1 — Claim Integrity Agent

**Job**: Verify the claim is complete, consistent, and not a duplicate.

**Documents Fetched**:
- `claim_form` — claimant name, DOB, policy number, incident date, submission date
- `policy_document` — policy start/end date, coverage details
- `id_proof` — claimant identity fields

**Tools Called**:
```
get_claim_documents_data(claim_id, ["claim_form", "policy_document", "id_proof"])
get_claimant_history(claimant_id)
get_policy_details(policy_id)
```

**Checks it runs**:

| Check | What it looks for |
|---|---|
| Required fields | Name, DOB, policy number, incident date all present |
| Date consistency | Dates are in logical order |
| Policy active | Policy was valid on incident date |
| Duplicate check | Not already submitted |

**Output**:
```json
{
  "agent": "Claim Integrity Agent",
  "status": "PASS",
  "checks": [
    {
      "name": "Required Fields",
      "result": "PASS",
      "explanation": "All fields — name, DOB, policy number, and incident date — were found in the claim form."
    },
    {
      "name": "Date Logic",
      "result": "PASS",
      "explanation": "Incident date (Jan 5) is before treatment date (Jan 8), which is before submission date (Jan 15). Order is valid."
    },
    {
      "name": "Duplicate Check",
      "result": "PASS",
      "explanation": "No prior claim found with the same policy number and incident date."
    }
  ],
  "overall_reason": "Claim is complete and all fields are consistent. No integrity issues found."
}
```

---

### Agent 2 — Medical Agent

**Job**: Check if the medical information in the documents is valid and complete.

**Documents Fetched**:
- `medical_report` — diagnosis, ICD code, doctor name, hospital, SOAP notes
- `lab_reports` — test names, results, dates, referring doctor

**Tools Called**:
```
get_claim_documents_data(claim_id, ["medical_report", "lab_reports"])
```

**Checks it runs**:

| Check | What it looks for |
|---|---|
| Diagnosis present | A clear diagnosis is stated |
| ICD code format | Code follows correct format |
| Provider mentioned | Doctor or hospital name present |
| Medical report | Report or SOAP notes are attached |

**Output**:
```json
{
  "agent": "Medical Agent",
  "status": "FAIL",
  "checks": [
    {
      "name": "Diagnosis Present",
      "result": "PASS",
      "explanation": "Diagnosis 'Lumbar Disc Herniation' was clearly stated in the medical report."
    },
    {
      "name": "ICD Code Format",
      "result": "FAIL",
      "explanation": "ICD code 'M5116' found in document does not match standard ICD-10 format (e.g. M51.16). Likely a formatting error in the document."
    },
    {
      "name": "Provider Mentioned",
      "result": "PASS",
      "explanation": "Dr. Ramesh Mehta, City Hospital is mentioned as the treating physician."
    }
  ],
  "overall_reason": "Diagnosis and provider are present, but ICD code format is incorrect. Manual verification of the code is recommended."
}
```

---

### Agent 3 — Treatment Agent

**Job**: Ensure the treatment aligns with the diagnosis and the billing is documented.

**Documents Fetched**:
- `prescription_records` — medications, dosage, duration, prescribing doctor
- `bills_invoices` — procedures performed, billed amounts, dates
- `medical_report` — diagnosis (to cross-check treatment alignment)

**Tools Called**:
```
get_claim_documents_data(claim_id, ["prescription_records", "bills_invoices", "medical_report"])
```

**Checks it runs**:

| Check | What it looks for |
|---|---|
| Treatment documented | Procedure or medication is clearly mentioned |
| Treatment matches diagnosis | Treatment logically fits the diagnosis |
| Billing present | Invoice or bill is attached |
| Amount documented | A billed amount is mentioned |

---

### Agent 4 — Disability Agent

**Job**: Validate the disability claim is supported by proper documentation.

**Documents Fetched**:
- `disability_certificate` — disability type, severity, issuing doctor, date
- `medical_report` — diagnosis and functional limitations to cross-check

**Tools Called**:
```
get_claim_documents_data(claim_id, ["disability_certificate", "medical_report"])
```

**Checks it runs**:

| Check | What it looks for |
|---|---|
| Disability certificate | Certificate from licensed physician present |
| Severity mentioned | Severity level stated in document |
| Limitations consistent | Claimed limitations match the medical diagnosis |

---

### Agent 5 — Litigation Agent

**Job**: Detect legal involvement or fraud red flags.

**Documents Fetched**:
- `legal_letter` — attorney name, legal notice text, court references (if submitted)
- `claim_form` — submission notes, any remarks section

**Tools Called**:
```
get_claim_documents_data(claim_id, ["legal_letter", "claim_form"])
get_claimant_history(claimant_id)
```

**Checks it runs**:

| Check | What it looks for |
|---|---|
| Attorney involvement | Legal letter or attorney name detected |
| Multiple recent claims | More than 2 claims in last 12 months |
| Suspicious language | Legal/fraud-related keywords in documents |

---

## Final Report Structure

The workflow does **not make a decision**. It produces a **report** with a **suggestion**.

```
📋 CLAIM REPORT
──────────────────────────────────────────

Claim ID     : CLM-001
Claimant     : John Doe
Processed At : 2026-07-09 18:30:00

──────────────────────────────────────────
AGENT RESULTS
──────────────────────────────────────────

✅ Claim Integrity   → PASS
   All fields present, dates consistent, no duplicate found.

❌ Medical           → FAIL
   ICD code format is incorrect. Manual verification needed.

✅ Treatment         → PASS
   Treatment aligns with diagnosis. Billing invoice present.

✅ Disability        → PASS
   Disability certificate present. Severity documented.

⚠️  Litigation        → FLAG
   Attorney name detected in attached legal letter.

──────────────────────────────────────────
DETAILED CHECK BREAKDOWN
──────────────────────────────────────────

[Claim Integrity]
  ✅ Required Fields     — All mandatory fields found
  ✅ Date Logic          — Dates are in correct order
  ✅ Duplicate Check     — No prior identical claim found

[Medical]
  ✅ Diagnosis Present   — Lumbar Disc Herniation identified
  ❌ ICD Code Format     — 'M5116' is not valid ICD-10 format
  ✅ Provider Mentioned  — Dr. Ramesh Mehta, City Hospital

[Treatment]
  ✅ Treatment Documented — Physiotherapy sessions noted
  ✅ Treatment-Diagnosis Match — Physiotherapy appropriate for disc herniation
  ✅ Billing Present     — Invoice of ₹45,000 attached

[Disability]
  ✅ Certificate Present — Signed by Dr. Ramesh Mehta
  ✅ Severity Mentioned  — Moderate disability stated
  ✅ Limitations Match   — Limited mobility consistent with diagnosis

[Litigation]
  ⚠️  Attorney Detected   — "Mr. Arjun Shah, Advocate" found in letter
  ✅ Prior Claims        — Only 1 prior claim in last 12 months
  ✅ Suspicious Keywords — None detected

──────────────────────────────────────────
💡 SUGGESTION
──────────────────────────────────────────

Suggestion  : REVIEW BEFORE APPROVAL

Explanation :
  The claim is largely well-documented and treatment aligns with
  the diagnosis. However, two issues require attention before
  a final decision:

  1. The ICD code (M5116) appears to have a formatting error.
     This should be verified with the treating physician before
     approval. It may simply be a transcription mistake.

  2. An attorney is involved in this claim. While this alone
     does not indicate fraud, it is standard practice to have
     such claims reviewed by a senior adjuster before proceeding.

  If the ICD code is confirmed and no legal complications arise,
  this claim is likely valid and should be approved.

──────────────────────────────────────────
```

---

## What to Build (POC Steps)

```
1. Claim Processing Workflow
   └── Same structure as OCR workflow
   └── Takes claim_id as input
   └── Runs 5 agents sequentially

2. 3 Shared Fetch Tools
   └── get_claim_documents_data(claim_id, doc_types[])
         → queries DB for OCR field-value pairs of given doc types
         → returns structured JSON per document
   └── get_claimant_history(claimant_id)
         → returns prior claims list from DB
   └── get_policy_details(policy_id)
         → returns policy coverage info from DB

3. 5 Validator Agents
   └── Each agent has a system prompt (what + how to check)
   └── Each agent fetches only its needed documents
   └── LLM reads fetched data and performs all checks
   └── Returns per-check explainable result

4. Report Generator
   └── Collects all 5 agent outputs
   └── Formats into the final report structure
   └── LLM generates the final "Suggestion" paragraph

5. Store Report
   └── Save to DB against the claim_id
   └── Make available via API
```

---

## Database — Still Simple (One Table Added)

```
claim_reports
─────────────
claim_id
claimant_name
submitted_at
agent_results     ← JSON: all 5 agent outputs with checks
suggestion        ← text: final suggestion paragraph
processed_at
```

---

*POC — Document-AI Claim Processing Module*

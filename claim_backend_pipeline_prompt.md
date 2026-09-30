# Prompt: Backend Claim Processing Pipeline (Agents + Activities)

> Scope: **backend only**. No frontend, UI, or dashboard work. The API exposes the data; how it is displayed is out of scope.

---

## Role & Goal

You are a senior Python backend engineer. Build the backend for an autonomous insurance **Claim Processing Pipeline**. A claim is a set of insurance documents that an upstream OCR/IDP pipeline has already processed into structured key-value fields. The pipeline takes a `claim_id`, runs **five specialised validator agents** one after another (each calls data-fetching tools), then has a **Claim Report Agent** combine their findings into a recommendation, and saves an explainable report for a human adjuster.

The pipeline only *suggests* an outcome. A human records the final approve/reject decision through the API.

---

## Tech Stack

- **Python 3.11+**, **FastAPI** (async endpoints, Pydantic request/response models).
- **Workflow orchestration**: Mistral Workflows SDK (`mistralai.workflows`), which is Temporal-compatible. Use `@workflows.workflow.define`, `@workflows.workflow.entrypoint`, and `@workflows.activity()`.
- **Agents**: Mistral AI Studio Agents, called with `client.agents.complete_async(agent_id=..., messages=..., tools=...)`. Model `mistral-small-latest`, `temperature=0.1`, `top_p=1.0`, `max_tokens=20480`, `tool_choice="auto"`. Read temperature and max tokens from the `LLM_TEMPERATURE` and `LLM_MAX_TOKENS` env vars.
- **Database**: SQLAlchemy 2.0 async (PostgreSQL via `asyncpg`; SQLite via `aiosqlite` for dev), with Alembic migrations.
- **Queue**: Redis + `arq`. `EXECUTION_MODE=queue` enqueues a dispatch job. `EXECUTION_MODE=inline` starts the run inside the request.
- **Resilience**: wrap the Mistral client (`get_mistral_client()`) with retries, a circuit breaker, and a fallback.

---

## Pipeline Overview

```
POST /claims                      → claim created (status: creating)
POST /documents/upload?claim_id=  → document linked to claim (status: extracting)
      │   OCR pipeline runs per document (existing, out of scope)
      │   multi-doc packets are split; child docs inherit the claim link
      ▼
GET /claims/{id}/status           → checklist evaluated; when all required docs
                                    are extracted → status: ready (+ claimant/policy/amount
                                    back-filled from claim_form / policy_document)
      ▼
POST /claims/{id}/run             → submit_claim_run → dispatch → Studio execution
      ▼
claim_processing_workflow(claim_id, claimant_id, policy_id)
   ├─ Step 1  Claim Integrity Agent   (status: checking_integrity)
   ├─ Step 2  Medical Agent           (status: checking_medical)
   ├─ Step 3  Treatment Agent         (status: checking_treatment)
   ├─ Step 4  Disability Agent        (status: checking_disability)
   ├─ Step 5  Litigation Agent        (status: checking_litigation)
   │     after each step → upsert_agent_result (incremental report row)
   ├─ Step 6  Claim Report Agent      (status: generating_report)
   └─ Step 7  save_claim_report       (status: completed)
      ▼
GET /claims/{id}/report  → POST /claims/{id}/decision (approved | rejected)
```

The workflow is **fully automated**, with no human-in-the-loop pauses inside it.

---

## 1. Data Model

Create these tables (SQLAlchemy models plus an Alembic migration):

| Table | Key columns | Purpose |
|---|---|---|
| `claims` | `id` (uuid PK), `claim_id` (unique, e.g. `CLM-2026-001`), `claimant_id` (e.g. `CLT-NAME-XXXX`), `policy_id`, `claimant_name`, `claim_type`, `amount`, `priority` (low/medium/high/urgent), `description`, `submitted_at`, `status`, `workflow_run_id`, `created_at`, `updated_at` | Top-level claim record |
| `claim_document_links` | `claim_id` (FK), `document_id` (FK → `documents.id`), `doc_type`, `synced` (pending/synced/failed) | Bridges the OCR `documents` table to a claim |
| `claim_documents` | `claim_id` (FK), `doc_type`, `fields` (JSON) | Optional cached/seeded field sets per doc type |
| `claimant_history` | `claimant_id` (indexed), `prior_claim_id`, `submitted_at`, `status` | Prior claims, used for duplicate and frequency checks |
| `policy_details` | `policy_id` (unique), `holder_name`, `coverage_type`, `start_date`, `end_date`, `details` (JSON) | Underwritten policy data |
| `claim_reports` | `claim_id` (FK, unique), `claimant_name`, `agent_results` (JSON keyed by agent), `suggestion` (text), `overall_status`, `processed_at` | Final report, written **incrementally** |

**Claim status lifecycle:**
`creating → extracting → ready → processing → checking_integrity → checking_medical → checking_treatment → checking_disability → checking_litigation → generating_report → completed → approved | rejected`. Any technical error moves the claim to `failed`. A `failed` claim can be re-run.

---

## 2. Document Requirements & Readiness

Keep a per-claim-type document checklist. Store it in `storage/claim_requirements.json` and fall back to built-in defaults when the file is missing:

- **Health Insurance / default**: claim_form, medical_report, bills_invoices (optional), policy_document, prescription_records, lab_reports, pan_card (ID proof), disability_certificate, legal_letter.
- **Motor Insurance**: claim_form, bills_invoices (optional), policy_document, pan_card, legal_letter.
- **Life Insurance**: claim_form, medical_report, policy_document, pan_card, legal_letter.

Look up the claim type in this order: exact match, then case-insensitive or substring match, then `default`.

`get_claim_extraction_status(claim_id)` must:
1. Load every `claim_document_links` row and its OCR `Document` status.
2. Match each requirement to one uploaded document. Check the link's `doc_type`, the OCR-classified `doc_type`, and the filename, using an alias-aware matcher (`_match_doc_type`). Each document can satisfy only one requirement.
3. Return `total_docs`, `completed_docs`, `failed_docs`, `required_docs[]` (each with is_uploaded, is_completed, status, filename, and document_id), `missing_required_count`, `all_required_completed`, and `ready_to_process`.
4. When the claim is ready and its status is `extracting`, set it to `ready` and back-fill `claimant_name`, `claim_type`, `amount`, and `policy_id` from the extracted `claim_form` / `policy_document` fields.

**Packet splitting:** if an uploaded PDF contains several documents, the split fan-out activity must create a `claim_document_links` row for every child document and delete the parent packet's link.

---

## 3. Shared Agent Tools (`tools/claim_tools.py`)

All five validator agents share three **pure data-fetch tools**. The tools do no reasoning; the LLM does all of it. Expose them as OpenAI-style function schemas (`CLAIM_TOOLS`) and route calls through `dispatch_claim_tool(name, args)`. Each tool catches its own exceptions and returns `{"error": "..."}` instead of raising.

| Tool | Args | Returns |
|---|---|---|
| `get_claim_documents_data` | `claim_id`, `doc_types: list[str]` | `{doc_type: validated_fields \| null}`. Uses one batched join across `claim_document_links → documents → extracted_data`. For each requested type, the first alias match on the link type or the OCR type wins. Logs a warning for each type it cannot find. |
| `get_claimant_history` | `claimant_id` | `{claimant_id, total_prior_claims, claims_last_12_months, prior_claims: [{claim_id, submitted_at, status}]}` |
| `get_policy_details` | `policy_id` | `{policy_id, found: true, holder_name, coverage_type, start_date, end_date, details}` or `{policy_id, found: false}` |

Valid `doc_types`: `claim_form, policy_document, id_proof, medical_report, lab_reports, prescription_records, bills_invoices, disability_certificate, legal_letter`.

---

## 4. The Agents

Each agent is a Mistral Studio agent. Its ID lives in an env var, and its config (name, description, instructions, model, completion_args) is defined in `agents_config.py`, with the instructions mirrored in `platform_core/prompts/<name>.md`. Provide a `create_or_update_agents.py` script that syncs these configs to Studio.

**Every validator agent must return exactly this JSON:**
```json
{
  "agent": "<Agent Name>",
  "status": "PASS | FAIL | FLAG",
  "checks": [{ "name": "...", "result": "PASS | FAIL | FLAG", "explanation": "cites actual field values" }],
  "overall_reason": "1–2 sentence summary"
}
```
Shared rules: never fabricate values. Name missing fields explicitly. Output only the JSON object. The top-level `status` is `FAIL` if any check fails, otherwise `FLAG` if any check is flagged, otherwise `PASS`.

### Agent 1: Claim Integrity Agent (`CLAIM_INTEGRITY_AGENT_ID`)
- **Input**: `claim_id`, `claimant_id`, `policy_id`
- **Tools**: `get_claim_documents_data(["claim_form","policy_document","id_proof"])`, `get_claimant_history`, `get_policy_details`
- **Checks**:
  1. *Required Fields*: claimant name, DOB, policy number, incident date, and submission date are all present.
  2. *Date Logic*: incident date < treatment date (if present) < submission date.
  3. *Policy Active*: the incident date falls within the policy's start and end dates. FAIL if the policy is not found.
  4. *Duplicate Check*: no prior claim has the same policy number and incident date.

### Agent 2: Medical Agent (`CLAIM_MEDICAL_AGENT_ID`)
- **Input**: `claim_id`
- **Tools**: `get_claim_documents_data(["medical_report","lab_reports"])`
- **Checks**:
  1. *Diagnosis Present*.
  2. *ICD Code Format*: valid ICD-10, i.e. a letter, 2 digits, a dot, then 1–4 alphanumerics (e.g. `M51.16`, `S72.001A`).
  3. *Provider Mentioned*: a doctor, hospital, or clinic is named.
  4. *Medical Documentation*: the report, SOAP notes, or lab content is present and not empty.

### Agent 3: Treatment Agent (`CLAIM_TREATMENT_AGENT_ID`)
- **Input**: `claim_id`
- **Tools**: `get_claim_documents_data(["prescription_records","bills_invoices","medical_report"])`
- **Checks**:
  1. *Treatment Documented*: a procedure or medication is named.
  2. *Treatment Matches Diagnosis*: clinical-reasoning cross-check against the medical_report.
  3. *Billing Present*: an invoice exists and is not empty.
  4. *Amount Documented*: a billed amount or total is stated.

### Agent 4: Disability Agent (`CLAIM_DISABILITY_AGENT_ID`)
- **Input**: `claim_id`
- **Tools**: `get_claim_documents_data(["disability_certificate","medical_report"])`
- **Checks**:
  1. *Disability Certificate Present*: at least one of `issuing_doctor`, `issuing_medical_board`, or a licensed authority is populated. FAIL only if the certificate is absent.
  2. *Severity Mentioned*: any one of `severity`, `disability_nature`, `percentage_of_disability`, or a severity keyword in `disability_type`.
  3. *Limitations Consistent with Diagnosis*: FAIL only on a clear, direct medical contradiction.

### Agent 5: Litigation Agent (`CLAIM_LITIGATION_AGENT_ID`)
- **Input**: `claim_id`, `claimant_id`
- **Tools**: `get_claim_documents_data(["legal_letter","claim_form"])`, `get_claimant_history`
- **Checks** (this agent may return **FLAG**):
  1. *Attorney Involvement*: a legal letter, attorney, law firm, or court reference is present → FLAG, not FAIL.
  2. *Multiple Recent Claims*: `claims_last_12_months` > 2 → FLAG; > 5 → FAIL.
  3. *Suspicious Language*: keywords such as lawsuit, legal action, court, negligence, damages, compensation demand, fraud, false claim, or fabricated → FLAG, listing the terms found.

### Agent 6: Claim Report Agent (`CLAIM_REPORT_AGENT_ID`), synthesis
- **Input**: a compact summary line per agent (`- agent: STATUS — overall_reason`) plus the full `agent_results` JSON. **No tools.**
- **Call** with `response_format={"type":"json_object"}`.
- **Output**:
  ```json
  { "overall_status": "APPROVE | REVIEW BEFORE APPROVAL | REJECT",
    "suggestion": "3–8 plain-English sentences addressed to an adjuster, naming each specific FAIL/FLAG issue" }
  ```
- It suggests an outcome but does not decide. It must be balanced and must not assume fraud without evidence.

---

## 5. Activities

### 5a. Agent activities (`activities/claim_<name>.py`), one per validator
Each is an `@workflows.activity()` async function that implements a **tool-call loop**:

1. Build a short user prompt containing the IDs and the instruction "use your tools… return ONLY the JSON result object".
2. Call `client.agents.complete_async(agent_id, messages, tools=CLAIM_TOOLS)`.
3. **While** `message.tool_calls` is set: append the assistant message with its `tool_calls`, execute each call via `dispatch_claim_tool`, append a `{"role":"tool","name","content":json.dumps(result),"tool_call_id"}` message for each, and call the agent again.
4. Normalise the content, which may be a string or a list of chunks, with `_extract_text`, then `json.loads` it.
5. **JSON repair**: if parsing fails, append "Please output only the JSON result object with no extra text." and call again with `response_format={"type":"json_object"}`.
6. If the agent ID env var is unset, raise.
7. **Never let an agent activity raise into the workflow.** Catch every exception and return `{"agent": "...", "status": "ERROR", "checks": [], "overall_reason": "Agent activity failed with error: ..."}`.

| Activity | Signature |
|---|---|
| `claim_integrity_activity` | `(claim_id, claimant_id, policy_id)` |
| `claim_medical_activity` | `(claim_id)` |
| `claim_treatment_activity` | `(claim_id)` |
| `claim_disability_activity` | `(claim_id)` |
| `claim_litigation_activity` | `(claim_id, claimant_id)` |

Consider factoring steps 2–7 into one shared `run_claim_agent(agent_id, agent_name, prompt)` helper so the five files don't repeat the same loop.

### 5b. Workflow support activities (in `claim_workflow.py`)
Run these DB activities through `workflows.run_activities_locally()` to avoid Temporal I/O errors inside the workflow sandbox.

| Activity | Purpose |
|---|---|
| `update_claim_status_activity(claim_id, status)` | Moves the claim to each sub-status |
| `upsert_agent_result_activity(claim_id, agent_key, result)` | Merges one agent's result into `claim_reports.agent_results`, creating a shell report row if none exists. Deep-copy the JSON and call `flag_modified` so SQLAlchemy persists the mutation. Lets `/status` show results while the run is still going. |
| `generate_claim_suggestion_activity(claim_id, agent_results)` | Calls the Claim Report Agent. Falls back to rules on a missing agent ID or any error. |
| `save_claim_report_activity(claim_id, agent_results, suggestion, overall_status)` | Writes the final report with `claimant_name`, returns `{claimant_name, processed_at}` |

### 5c. Rule-based fallback (`_fallback_suggestion`)
Used when the Report Agent is unavailable:
- Any agent `FAIL` → `REJECT`
- else any `FLAG` → `REVIEW BEFORE APPROVAL`
- else any `ERROR` → `REVIEW BEFORE APPROVAL` (manual check needed)
- else → `APPROVE`

Generate a suggestion paragraph that names the affected agents.

---

## 6. Workflow (`claim_workflow.py`)

`@workflows.workflow.define(name="claim_processing_workflow")`
`class ClaimProcessingWorkflow(workflows.InteractiveWorkflow)`
`async def run(self, claim_id, claimant_id, policy_id) -> dict`

1. Set status to `processing`.
2. For each agent in order (integrity → medical → treatment → disability → litigation): set the `checking_*` status, run the activity, then `upsert_agent_result` under keys `claim_integrity`, `medical`, `treatment`, `disability`, `litigation`.
3. Set status to `generating_report`, then run `generate_claim_suggestion_activity`. Default `overall_status` to `REVIEW BEFORE APPROVAL` if it is missing.
4. Run `save_claim_report_activity`, then set status to `completed`.
5. Return `{claim_id, claimant_name, processed_at, agent_results: {key: {status, overall_reason, checks}}, overall_status, suggestion}`. Coerce a missing or empty agent status to `UNKNOWN`.

Register the workflow alongside the document workflow in `workflow_worker.py` (and in `main.py` for local worker mode).

---

## 7. Dispatch & Queue

- **`platform_core/dispatch.py` → `start_claim_run(claim_id, claimant_id, policy_id)`**: starts `claim_processing_workflow` on Mistral Studio with execution ID `claim-{claim_id}-{uuid8}`. The ID must be unique per attempt because Studio rejects reused IDs. Pass `deployment_name` from config. Raise `DispatchError` on failure.
- **`api/queue.py` → `submit_claim_run(...)`**:
  - `inline` mode: call `start_claim_run`, then `set_claim_run_id(claim_id, run_id, "processing")` (one transaction), and return the `run_id`.
  - `queue` mode: enqueue the arq job `run_claim_pipeline` with `_job_id=f"claim-{claim_id}-{uuid8}"` and return `None`.
- **`worker.py` → `run_claim_pipeline(ctx, claim_id, claimant_id, policy_id)`**: the arq job that dispatches the run and records the run ID.

---

## 8. REST API (`api/routers/v1/claims.py`, tag `Claims`)

| Method | Path | Behaviour |
|---|---|---|
| POST | `/claims` | Body `CreateClaimRequest{claimant_name, claim_type?, policy_number?, description?, priority?, amount?}`. Generates `claim_id` and `claimant_id`. Status `creating`. |
| GET | `/claims` | Lists claims with status and `workflow_run_id`. |
| GET | `/claims/{id}/status` | Extraction/checklist status plus `claim_status` and any partial `agent_results` so far. 404 if the claim is unknown. |
| POST | `/claims/{id}/run` | 409 unless status is `ready` or `failed`. 400 if required documents are missing (unless the claim is `failed`). Calls `submit_claim_run`. Returns `{claim_id, workflow_run_id, status:"processing"}`. |
| POST | `/claims/{id}/rerun` | Deletes the existing report, resets the claim to `ready` with `workflow_run_id=None`, then re-submits. |
| GET | `/claims/{id}/report` | The final report. 404 if none exists yet. |
| POST | `/claims/{id}/decision` | Body `{decision: "approve"\|"reject", notes?}`. Sets `approved` or `rejected`. 400 on any other value. |
| DELETE | `/claims/{id}` | Deletes the claim and cascades to its report and documents. |

The existing `POST /documents/upload` takes an optional `claim_id` query param. When it is set, the endpoint creates a `claim_document_links` row and moves the claim from `creating` to `extracting`.

---

## 9. Configuration

Add these to `config.py` / `.env.example`:
```
CLAIM_INTEGRITY_AGENT_ID=
CLAIM_MEDICAL_AGENT_ID=
CLAIM_TREATMENT_AGENT_ID=
CLAIM_DISABILITY_AGENT_ID=
CLAIM_LITIGATION_AGENT_ID=
CLAIM_REPORT_AGENT_ID=
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=20480
EXECUTION_MODE=queue|inline
```

---

## 10. Non-Functional Requirements

- **Explainability**: every check explanation must cite the actual extracted values it relied on.
- **Fault isolation**: if one agent fails, the run still continues. The failed agent shows up as `ERROR`, and the final suggestion routes the claim to review.
- **Observability**: prefix every log line with `[Claim {claim_id}]`, and log each tool call and each agent's final status.
- **Idempotency**: execution IDs are unique per attempt. Re-running a claim clears the previous report first.
- **Tests (pytest)**: cover the tool dispatcher, the fallback suggestion matrix (FAIL/FLAG/ERROR/all PASS), the tool-call loop against a mocked Mistral client (including the JSON-repair path), the incremental upsert, and the API status-gating rules (409/400/404).

---

## Deliverables

1. Models plus an Alembic migration for the six claim tables.
2. `tools/claim_tools.py` (schemas, implementations, dispatcher).
3. `db/claim_operations.py` (CRUD, readiness evaluation, fetch tools, report upsert/save).
4. `utils/claim_requirements.py` (checklist config).
5. `activities/claim_{integrity,medical,treatment,disability,litigation}.py`.
6. `claim_workflow.py` (workflow, support activities, fallback).
7. Agent configs in `agents_config.py`, prompts in `platform_core/prompts/claim_*.md`, and the `create_or_update_agents.py` sync script.
8. Dispatch, queue, and worker wiring.
9. `api/routers/v1/claims.py` and `schemas/claims.py`.
10. The tests listed above.

# Master Prompt: Autonomous AI-Powered Insurance Claim Processing Workflow

> **Prompt Objective**: Provide an end-to-end blueprint to implement an autonomous, multi-agent Insurance Claim Processing system from scratch. This system integrates with an OCR/IDP document extraction pipeline, runs five specialized validator agents using function calling, generates an explainable adjuster report via a synthesis agent, and provides a real-time reactive reviewer dashboard.

---

## 1. System Overview & Architecture

Build an autonomous, asynchronous Insurance Claim Processing backend and frontend. The architecture is decoupled into two tiers:
1. **Document Ingestion & Extraction Tier**: Documents (claim forms, medical reports, invoices, disability certificates, legal notices, ID proofs) are uploaded and processed by an OCR/IDP pipeline that outputs structured key-value pairs (`ExtractedData`).
2. **Claim Validation & Adjudication Tier**: An orchestration engine that takes a `claim_id`, pulls extracted document fields, and runs a sequence of specialized AI agents equipped with data-fetching tools.

### Technology Stack Requirements
- **Backend**: Python 3.11+, FastAPI (asynchronous endpoints with Pydantic validation).
- **Workflow Orchestration**: Mistral Workflows SDK (`mistralai.workflows`) or Temporal-compatible workflow runtime with durable execution, retries, and decoupled activity workers.
- **AI Agent Framework**: Mistral AI Studio Agents (model `mistral-small-latest`, temperature `0.1`, max output tokens `20480`) with OpenAI-compatible tool/function calling.
- **Database Layer**: PostgreSQL (or SQLite for development) using SQLAlchemy 2.0 Async (`asyncpg` / `aiosqlite`).
- **Asynchronous Task Queue**: Redis with `arq` for distributed queueing (`EXECUTION_MODE=queue`) and an immediate direct execution mode (`EXECUTION_MODE=inline`).
- **Frontend**: React (Vite, vanilla CSS design tokens, Lucide icons) with live polling for incremental step updates, checklist validation, and human-in-the-loop decisioning.

---

## 2. Database Design & Entity Relationships

Design the persistence layer with six interconnected models:

### 1. `claims` (Primary Claim Entity)
- **Identifiers**: `id` (UUID primary key), `claim_id` (human-readable unique string, format `CLM-YYYY-XXXX`), `claimant_id` (unique claimant reference, format `CLT-NAME-XXXX`), `policy_id` (policy number reference, indexed).
- **Metadata**: `claimant_name` (string), `claim_type` (e.g., "Health Insurance", "Motor Insurance", "Life Insurance"), `amount` (float monetary total), `priority` (low, medium, high, urgent), `description` (text summary of the incident), `submitted_at` (timestamp).
- **Lifecycle Status**:
  - `creating`: Claim record created, awaiting document uploads.
  - `extracting`: Documents are uploaded; OCR pipeline is actively extracting fields.
  - `ready`: All mandatory documents have successfully extracted; claim is eligible for agent analysis.
  - `processing`: Claim workflow is executing (with dynamic sub-states: `checking_integrity`, `checking_medical`, `checking_treatment`, `checking_disability`, `checking_litigation`, `generating_report`).
  - `completed`: All agents have completed; report and suggestion are saved.
  - `approved` / `rejected`: Final human adjuster decision recorded.
  - `failed`: Workflow halted due to technical error.
- **Workflow Reference**: `workflow_run_id` (stores execution ID for correlation).
- **Timestamps**: `created_at`, `updated_at`.

### 2. `claim_documents` (Document Field Cache)
- **Fields**: `id` (UUID), `claim_id` (foreign key to `claims.claim_id`), `doc_type` (string category), `fields` (JSON dictionary of OCR key-value pairs), `created_at`.
- Stores cached, normalized fields per document type under a claim.

### 3. `claim_document_links` (Bridge to OCR Pipeline)
- **Fields**: `id` (UUID), `claim_id` (foreign key to `claims.claim_id`), `document_id` (foreign key to the OCR `documents` table), `doc_type` (document category), `synced` (`pending`, `synced`, or `failed`), `created_at`.
- **Packet Splitting Cascade**: If an uploaded PDF is a multi-document bundle, the splitter decomposes it into individual child documents. The system must automatically delete the link to the parent packet and create individual `claim_document_links` for every extracted child document.

### 4. `claimant_history` (Historical Claimant Activity)
- **Fields**: `id` (UUID), `claimant_id` (indexed string), `prior_claim_id` (string reference), `submitted_at` (timestamp), `status` (`approved`, `rejected`, `pending`), `created_at`.
- Serves as the historical database for frequency and fraud detection.

### 5. `policy_details` (Underwritten Insurance Policies)
- **Fields**: `id` (UUID), `policy_id` (unique indexed string), `holder_name` (string), `coverage_type` (e.g., "comprehensive", "basic"), `start_date` (timestamp), `end_date` (timestamp), `details` (JSON dictionary for deductible, limits, special clauses), `created_at`.

### 6. `claim_reports` (Audit & Output Report)
- **Fields**: `id` (UUID), `claim_id` (foreign key to `claims.claim_id`, unique), `claimant_name` (string), `agent_results` (JSON dictionary keyed by agent name), `suggestion` (text recommendation from Report Agent), `overall_status` (`APPROVE`, `REVIEW BEFORE APPROVAL`, or `REJECT`), `processed_at` (timestamp).
- Updated **incrementally** during workflow execution so the UI streams live agent findings.

---

## 3. Document Requirements Engine & Auto-Population

Implement a dynamic checklist and field-mapping system:

### 1. Document Requirements by Claim Type
Maintain a configurable JSON ruleset defining mandatory and optional documents per insurance vertical:
- **Health Insurance**:
  - *Mandatory*: Claim Form (`claim_form`), Medical Report / Discharge Summary (`medical_report`), Policy Document (`policy_document`), Prescription Records (`prescription_records`), Lab Reports (`lab_reports`), ID Proof / PAN Card (`pan_card`), Disability Certificate (`disability_certificate`), Police FIR / Legal Letter (`legal_letter`).
  - *Optional*: Hospital / Medical Bills (`bills_invoices`).
- **Motor Insurance**:
  - *Mandatory*: Claim Form, Policy Document, ID Proof / Driving License, Police FIR Copy.
  - *Optional*: Repair Estimate / Garage Bills.
- **Life Insurance**:
  - *Mandatory*: Death Claim Form, Medical / Death Certificate, Policy Document, Nominee ID Proof, Police FIR / Post-Mortem Report.

### 2. Document Alias Matching
Create a fuzzy alias matcher that resolves document classifications to required categories:
- `medical_report` aliases: `medical_record`, `discharge_summary`, `lab_reports`.
- `bills_invoices` aliases: `invoice`, `bill`, `medical_bills`.
- `pan_card` / `id_proof` aliases: `aadhaar_card`, `driving_licence`, `driving_license`, `kyc`, `passport`.
- Fall back to keyword inspection in original file names (e.g., checking for "id proof", "license", "pan", "bill").

### 3. Readiness Evaluation & Auto-Population
Provide an evaluation function (`get_claim_extraction_status`):
- Cross-references linked documents against the required checklist for the claim's vertical.
- Computes `total_docs`, `completed_docs`, `failed_docs`, `missing_required_count`, and `all_required_completed`.
- **Auto-Readiness Transition**: When all mandatory documents reach `completed` OCR status, transition the claim status from `extracting` to `ready`.
- **Auto-Population**: Read the extracted data from the `claim_form` and `policy_document`. Automatically parse and update the parent claim record with `claimant_name`, `claim_type`, `amount`, and `policy_id`.

---

## 4. Shared Fetch Tools (Zero-Reasoning Pattern)

All reasoning is performed by the LLM agents. Create three lightweight data-fetching tools with standardized JSON schemas:

### 1. `get_claim_documents_data`
- **Purpose**: Fetches OCR-extracted key-value pairs for specified document types belonging to a claim.
- **Parameters**: `claim_id` (string), `doc_types` (array of strings).
- **Behavior**: Executes a single optimized query joining `ClaimDocumentLink`, `Document`, and `ExtractedData`. For each requested type, checks alias matches against link type and OCR classified type, returning a JSON map: `{ "<doc_type>": { <extracted_fields> }, ... }`. Returns `null` for any document type not present.

### 2. `get_claimant_history`
- **Purpose**: Retrieves prior claims history for a claimant.
- **Parameters**: `claimant_id` (string).
- **Behavior**: Queries `claimant_history` for matching records. Computes `total_prior_claims`, calculates `claims_last_12_months` using a 365-day cutoff, and returns a list of prior claims with their submission dates and statuses (`approved`, `rejected`, `pending`).

### 3. `get_policy_details`
- **Purpose**: Fetches insurance policy coverage details.
- **Parameters**: `policy_id` (string).
- **Behavior**: Queries `policy_details`. Returns a dictionary containing `found` (boolean), `policy_id`, `holder_name`, `coverage_type`, `start_date`, `end_date`, and policy `details`.

### Central Dispatcher
Implement a centralized tool router that inspects function call names from LLM responses, routes the parsed arguments to the corresponding database helper, and serializes the response back to the agent conversation loop.

---

## 5. The 5 Validator Agents & System Instructions

Each validator agent is an autonomous Mistral AI Studio agent. Agents must return **only** a valid JSON object matching this contract:
```json
{
  "agent": "<Agent Name>",
  "status": "PASS" | "FAIL" | "FLAG",
  "checks": [
    {
      "name": "<Check Name>",
      "result": "PASS" | "FAIL" | "FLAG",
      "explanation": "<Plain English explanation citing exact document field values>"
    }
  ],
  "overall_reason": "<1-2 sentence executive summary>"
}
```

### Agent 1: Claim Integrity Agent
- **Identifier**: `CLAIM_INTEGRITY_AGENT_ID`
- **Tools**: `get_claim_documents_data(claim_id, ["claim_form", "policy_document", "id_proof"])`, `get_claimant_history(claimant_id)`, `get_policy_details(policy_id)`
- **Core Checks**:
  1. *Required Fields*: Verify that the claim form contains claimant name, date of birth, policy number, incident date, and submission date. Mark `FAIL` if any are missing or blank.
  2. *Date Logic*: Verify chronological consistency: `incident_date < treatment_date < submission_date`. Mark `FAIL` if dates are logically impossible.
  3. *Policy Active on Incident Date*: Compare `incident_date` against policy `start_date` and `end_date`. Mark `FAIL` if the incident falls outside the active coverage window or if the policy is not found.
  4. *Duplicate Check*: Inspect claimant history. Mark `FAIL` if any previous claim has the identical policy number and incident date.
- **Decision Rule**: Overall status is `FAIL` if any check fails; otherwise `PASS`.

### Agent 2: Medical Agent
- **Identifier**: `CLAIM_MEDICAL_AGENT_ID`
- **Tools**: `get_claim_documents_data(claim_id, ["medical_report", "lab_reports"])`
- **Core Checks**:
  1. *Diagnosis Present*: Verify that a clear medical diagnosis is articulated in the medical report. Mark `FAIL` if absent.
  2. *ICD Code Format*: Verify that the diagnostic code matches standard ICD-10 formatting (starts with a letter, followed by two digits, a dot, and 1 to 4 alphanumeric characters, e.g., `M51.16`). Mark `FAIL` if missing or invalid.
  3. *Provider Mentioned*: Verify that a treating physician name or hospital/clinic name is documented. Mark `FAIL` if no provider is cited.
  4. *Medical Documentation*: Verify that medical report, SOAP notes, or lab report contents are non-empty. Mark `FAIL` if documents are missing or blank.
- **Decision Rule**: Overall status is `FAIL` if any check fails; otherwise `PASS`.

### Agent 3: Treatment Agent
- **Identifier**: `CLAIM_TREATMENT_AGENT_ID`
- **Tools**: `get_claim_documents_data(claim_id, ["prescription_records", "bills_invoices", "medical_report"])`
- **Core Checks**:
  1. *Treatment Documented*: Verify that a specific medical procedure, treatment, therapy, or medication is clearly documented.
  2. *Treatment Matches Diagnosis*: Apply clinical reasoning to evaluate if the treatment logically corresponds to the stated diagnosis (e.g., physiotherapy is appropriate for lumbar disc herniation; antibiotics for bacterial pneumonia). Mark `FAIL` if contradictory or unrelated.
  3. *Billing Present*: Verify that a medical bill or invoice document is attached and readable.
  4. *Amount Documented*: Verify that a specific monetary charge or total billed amount is stated.
- **Decision Rule**: Overall status is `FAIL` if any check fails; otherwise `PASS`.

### Agent 4: Disability Agent
- **Identifier**: `CLAIM_DISABILITY_AGENT_ID`
- **Tools**: `get_claim_documents_data(claim_id, ["disability_certificate", "medical_report"])`
- **Core Checks**:
  1. *Disability Certificate Present*: Verify that a disability certificate is attached and contains an issuing physician name, hospital, or medical board. Mark `PASS` if found; mark `FAIL` only if completely missing.
  2. *Severity Mentioned*: Verify that disability severity is indicated (e.g., severity grade, permanent/temporary nature, percentage of disability). Mark `FAIL` only if all severity fields are absent.
  3. *Limitations Consistent with Diagnosis*: Cross-reference functional limitations against the medical report diagnosis. Mark `FAIL` only on clear, severe contradiction (e.g., claiming total limb paralysis for minor sprains).
- **Decision Rule**: Overall status is `FAIL` if any check fails; otherwise `PASS`.

### Agent 5: Litigation & Fraud Agent
- **Identifier**: `CLAIM_LITIGATION_AGENT_ID`
- **Tools**: `get_claim_documents_data(claim_id, ["legal_letter", "claim_form"])`, `get_claimant_history(claimant_id)`
- **Core Checks**:
  1. *Attorney Involvement*: Check for legal notices, attorney names, law firms, or court references. If detected, mark check as `FLAG` (soft warning, not automatic denial).
  2. *Multiple Recent Claims*: Check claims submitted in the last 12 months. If > 2 claims, mark as `FLAG`. If > 5 claims, mark as `FAIL` (high fraud probability).
  3. *Suspicious Language*: Scan documents for litigation escalation keywords ("lawsuit", "damages", "court action", "negligence", "compensation demand", "fraud", "fabricated"). If detected, mark as `FLAG` and list matching terms.
- **Decision Rule**: Overall status is `FAIL` if any check is FAIL; `FLAG` if any check is FLAG and none are FAIL; otherwise `PASS`.

---

## 6. The Synthesis Agent (Claim Report Agent)

- **Identifier**: `CLAIM_REPORT_AGENT_ID`
- **Role**: Does **not** make a binding final decision. Acts as an expert advisor synthesizing all five agent outputs for the insurance adjuster.
- **Input**: Executive summary and detailed JSON outputs from all 5 validator agents.
- **Output Schema**:
  ```json
  {
    "overall_status": "APPROVE" | "REVIEW BEFORE APPROVAL" | "REJECT",
    "suggestion": "<Comprehensive 3-8 sentence narrative addressed to a human claims adjuster>"
  }
  ```
- **Synthesis Rules**:
  - `APPROVE`: All 5 agents returned `PASS` with zero flags.
  - `REVIEW BEFORE APPROVAL`: One or more agents returned `FLAG` (e.g., attorney detected, frequent claims), or minor fixable `FAIL` issues (e.g., malformed ICD-10 punctuation).
  - `REJECT`: Critical `FAIL` issues (e.g., policy inactive during incident, clear duplicate claim, > 5 recent claims).
- **Deterministic Rule Fallback**: Implement a code-level fallback (`_fallback_suggestion`) that computes the exact same status and a formatted summary paragraph if the agent API encounters timeouts or errors.

---

## 7. Workflow Orchestration & Real-Time Streaming

Implement the orchestration workflow using Mistral Workflows (`@workflows.workflow.define(name="claim_processing_workflow")`):

### 1. Sequential Pipeline Steps
1. Transition claim status to `processing`.
2. **Step 1 (Integrity)**: Update status to `checking_integrity` -> Run `claim_integrity_activity` -> Persist incremental result.
3. **Step 2 (Medical)**: Update status to `checking_medical` -> Run `claim_medical_activity` -> Persist incremental result.
4. **Step 3 (Treatment)**: Update status to `checking_treatment` -> Run `claim_treatment_activity` -> Persist incremental result.
5. **Step 4 (Disability)**: Update status to `checking_disability` -> Run `claim_disability_activity` -> Persist incremental result.
6. **Step 5 (Litigation)**: Update status to `checking_litigation` -> Run `claim_litigation_activity` -> Persist incremental result.
7. **Step 6 (Report Synthesis)**: Update status to `generating_report` -> Run `generate_claim_suggestion_activity`.
8. **Step 7 (Final Report Persistence)**: Save the aggregated report, update claim status to `completed`, and return the complete report payload.

### 2. Multi-Turn Activity Execution Loop
Inside each activity:
- Submit prompt to agent with `CLAIM_TOOLS`.
- If `tool_calls` are requested, loop through calls, execute via `dispatch_claim_tool`, append responses with `role="tool"`, and re-invoke the agent until final completion.
- Parse the resulting JSON string into a structured dictionary. If raw text is returned, prompt the model once more with `response_format={"type": "json_object"}`.

### 3. Real-Time Incremental Output Persistence
Implement `upsert_agent_result_activity`:
- Called **immediately after each agent finishes**.
- Writes that agent's JSON output directly into `claim_reports.agent_results[agent_key]`.
- Enables the frontend UI to display live validation check passes and failures as they happen without waiting for the full workflow to terminate.

---

## 8. Dispatch & Worker Architecture

Implement a two-mode execution strategy:

1. **Dispatcher (`platform_core/dispatch.py`)**:
   - Generates unique execution IDs: `claim-{claim_id}-{uuid4().hex[:8]}`.
   - Triggers execution via `execute_workflow_async(workflow_identifier="claim_processing_workflow", input={...})`.
2. **Execution Modes (`api/queue.py`)**:
   - `EXECUTION_MODE=inline`: Workflow starts directly inside the request handler; writes `workflow_run_id` immediately. Suitable for development without Redis.
   - `EXECUTION_MODE=queue`: API handler enqueues `run_claim_pipeline` to Redis via `arq` and immediately returns HTTP 202. The standalone `worker.py` picks up the job with automatic exponential backoff retries.
3. **Workflow Worker (`workflow_worker.py`)**:
   - Registers `ClaimProcessingWorkflow` in `workflows.run_worker(WORKFLOWS)`.
   - Runs as an independent process, listening for tasks dispatched by the Mistral Studio / Temporal control plane.

---

## 9. REST API Specification

Expose the following endpoints under `/api/v1`:

1. `POST /claims`:
   - Creates a new claim with metadata (`claimant_name`, `claim_type`, `policy_number`, `priority`, `amount`, `description`).
   - Generates formatted `claim_id` and `claimant_id`. Sets initial status to `creating`.
2. `GET /claims`:
   - Returns all claims ordered by `created_at DESC` with statuses, amounts, priorities, and workflow IDs.
3. `GET /claims/{id}/status`:
   - Returns detailed status, document counts (`total_docs`, `completed_docs`, `failed_docs`), checklist items with upload/extraction status, and any partial `agent_results` saved so far.
4. `POST /claims/{id}/run`:
   - Initiates processing for a claim.
   - **Guards**: Allowed only if status is `ready` (or `failed`) and all mandatory checklist documents are completed.
5. `POST /claims/{id}/rerun`:
   - Deletes any existing `ClaimReport`, resets status to `ready`, and restarts the workflow.
6. `GET /claims/{id}/report`:
   - Fetches the final `ClaimReport` including all 5 agent check breakdowns and the final suggestion paragraph.
7. `POST /claims/{id}/decision`:
   - Accepts `{ "decision": "approve" | "reject", "notes": "..." }`.
   - Updates claim status to `approved` or `rejected` and logs notes.
8. `DELETE /claims/{id}`:
   - Permanently deletes a claim, its report, and linked document mappings (preserves raw document files).
9. `POST /documents/upload` (Query Param Extension):
   - Accepts `?claim_id=...&doc_type=...`. Automatically creates a `ClaimDocumentLink` and transitions claim status from `creating` to `extracting`.

---

## 10. Frontend UI & User Experience Flow

Implement two cohesive dashboard views in React:

### 1. Claims Management & Ingestion Dashboard (`ClaimProcess.jsx`)
- **Metrics Bar**: Cards displaying Total Claims, In Processing, Ready to Process, and Approved/Rejected totals.
- **New Claim Modal**: Form capturing Claimant Details, Insurance Vertical, Policy ID, Priority, Description, and a Multi-file Upload zone.
- **Expandable Claim Cards**:
  - Displays claimant name, claim ID, policy number, amount, priority badge, and current status.
  - Expanding the card reveals the **Document Checklist**:
    - Categorized slots for each required document type.
    - Badges for `Extracted` (green), `Extracting` (pulsing blue), or `Missing` (amber).
    - Per-slot upload buttons allowing users to drop missing documents directly into specific requirements.
  - "Run Processing" button enabled **only** when all mandatory checklist items are satisfied.

### 2. Live Workflow Execution & Adjudication View (`ClaimWorkflow.jsx`)
- **Left Column (Interactive Step Tracker)**:
  - Vertical pipeline view representing: Setup -> Integrity -> Medical -> Treatment -> Disability -> Litigation -> Final Report.
  - Step icons reflecting dynamic state: Pending (circle), Running (animated spinner), Completed (green checkmark), Warning (amber triangle), Failed (red cross).
  - Clicking any step navigates to that agent's detailed output in the central view.
- **Center Stage (Live Agent Thought & Check Details)**:
  - Displays agent status badge (`PASS`, `FAIL`, `FLAG`).
  - Executive summary callout explaining findings.
  - Granular breakdown table listing every individual check, pass/fail result, and exact document evidence cited.
  - Tab toggles between `Structured Checks View`, `Raw JSON Output`, and `Execution Log`.
- **Top Summary Banner (Adjuster Recommendation)**:
  - Prominent badge displaying `APPROVE`, `REVIEW BEFORE APPROVAL`, or `REJECT`.
  - Highlighted callout containing the synthesis paragraph generated by the Report Agent.
- **Human Adjuster Action Bar**:
  - `Approve Claim` (green button) / `Reject Claim` (red button) opening a confirmation modal for adjuster notes.
  - `Re-run Analysis` button to reset and re-evaluate.
  - `Export Report` button to download findings as a clean JSON/PDF summary.

---

## 11. Verification & Testing Checklist

When implementing, verify against these criteria:
1. **Zero-Hallucination Tools**: Confirm validator agents only receive document field values retrieved from `get_claim_documents_data` and do not invent dates, amounts, or diagnosis codes.
2. **Deterministic Fallbacks**: Test that if the Report Agent encounters an API disruption, `_fallback_suggestion` still outputs an explainable status and summary based on the other 5 agents' outputs.
3. **Live Streaming UI**: Verify that while Agent 3 is running, the outputs of Agents 1 and 2 are already visible in the UI through polling `/claims/{id}/status`.
4. **Packet Split Cascade**: Verify that uploading a multi-document bundle correctly cascades down into individual `ClaimDocumentLink` rows for each extracted document.
5. **Human Override**: Confirm that adjuster decisions (`approve`/`reject`) update the DB status and prevent further automated overrides.

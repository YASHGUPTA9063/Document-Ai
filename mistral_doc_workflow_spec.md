# Mistral Document Processing Workflow — Backend Spec

> **Stack:** Python 3.11+ · FastAPI · Mistral Workflow SDK · Mistral AI SDK · SQLAlchemy (async) · SQLite · Local Filesystem Storage
> **Purpose:** Production-grade POC backend for multi-agent document ingestion, classification, extraction, validation, and human-in-the-loop review.
>
> ⚠️ **Agent Strategy:** All AI agents (Classifier, Extractor, Validator, Reviewer) are **pre-created in Mistral AI Studio**. The codebase does NOT create, configure, name, or describe any agent. It only calls agents using their Agent IDs loaded from `.env`. No agent creation code anywhere.

---

## Project Structure

```
mistral-doc-workflow/
├── main.py
├── workflow.py
├── agents/
│   ├── __init__.py
│   ├── intake.py
│   ├── classifier.py
│   ├── extractor.py
│   ├── validator.py
│   ├── reviewer.py
│   └── output.py
├── db/
│   ├── __init__.py
│   ├── database.py
│   └── models.py
├── schemas/
│   ├── __init__.py
│   └── documents.py
├── utils/
│   ├── __init__.py
│   ├── file_handler.py
│   └── ocr.py
├── storage/               ← uploaded files land here
├── config.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Workflow Overview

```
Upload
  │
  ▼
[INTAKE] ── duplicate? ──► input() pause ──► user: override / reject
  │ not duplicate
  ▼
[CLASSIFIER] → doc_type
  │
  ▼
[EXTRACTOR] → raw fields (Invoice only in v1)
  │
  ▼
[VALIDATOR] → confidence_score, validation_errors
  │
  ▼
[REVIEWER] ── score < 80%? ──► input() pause ──► user: approve / correct
  │ auto-approved or approved
  ▼
[OUTPUT] → save to DB → return final response
```

**Two `input()` pause points:**
1. **Intake** — if a duplicate filename is detected, pause and ask user whether to override.
2. **Reviewer** — if `confidence_score < 0.80`, pause and send extracted data to user for correction/approval.

Human decisions are submitted via FastAPI resume endpoints, which feed into the Mistral Workflow `input()` call.

---

## `.env.example`

```env
MISTRAL_API_KEY=your_mistral_api_key_here
STORAGE_DIR=./storage
DATABASE_URL=sqlite+aiosqlite:///./doc_workflow.db
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true

# Agent IDs — copy from Mistral AI Studio after creating each agent
CLASSIFIER_AGENT_ID=ag:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EXTRACTOR_AGENT_ID=ag:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VALIDATOR_AGENT_ID=ag:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
REVIEWER_AGENT_ID=ag:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## `config.py`

- Use `pydantic-settings` `BaseSettings` to load all values from `.env`
- Export a singleton `settings` object
- Fields: `MISTRAL_API_KEY`, `STORAGE_DIR`, `DATABASE_URL`, `APP_HOST`, `APP_PORT`, `DEBUG`
- Agent ID fields: `CLASSIFIER_AGENT_ID`, `EXTRACTOR_AGENT_ID`, `VALIDATOR_AGENT_ID`, `REVIEWER_AGENT_ID`
- All agent ID fields are required strings — raise a clear error at startup if any are missing

---

## `db/database.py`

- Async SQLAlchemy engine using `aiosqlite`
- `AsyncSession` factory
- `Base` declarative base
- `init_db()` async function — creates all tables on startup

---

## `db/models.py`

### `Document` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | UUID4 string |
| `filename` | String (unique) | original filename |
| `file_path` | String | absolute local path |
| `doc_type` | String (nullable) | set after classification |
| `status` | String | `pending` · `processing` · `awaiting_review` · `completed` · `failed` · `rejected` |
| `workflow_run_id` | String (nullable) | Mistral workflow run ID |
| `error_details` | JSON (nullable) | error info if status = failed |
| `created_at` | DateTime | auto now |
| `updated_at` | DateTime | auto update |

### `ExtractedData` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | UUID4 string |
| `document_id` | ForeignKey → Document.id | |
| `raw_extracted` | JSON | raw OCR output |
| `validated_data` | JSON | post-validation cleaned fields |
| `confidence_score` | Float | blended OCR + validation score |
| `reviewer_corrections` | JSON (nullable) | human corrections if any |
| `created_at` | DateTime | auto now |

---

## `schemas/documents.py`

Pydantic v2 schemas:

### `LineItem`
```
description: str | None
quantity: float | None
unit_price: float | None
total: float | None
```

### `ExtractedInvoiceFields`
```
invoice_number: str | None
invoice_date: str | None
vendor_name: str | None
vendor_address: str | None
bill_to: str | None
line_items: list[LineItem]
subtotal: float | None
tax: float | None
total_amount: float | None
currency: str | None
due_date: str | None
payment_terms: str | None
```

### `DocumentUploadResponse`
```
document_id: str
filename: str
status: str
message: str
workflow_run_id: str
```

### `WorkflowStatusResponse`
```
document_id: str
workflow_run_id: str | None
status: str
doc_type: str | None
confidence_score: float | None
extracted_data: dict | None
message: str
```

### `DuplicateDecisionRequest`
```
override: bool
```

### `ReviewerDecisionRequest`
```
approved: bool
corrections: dict | None
```

---

## `utils/file_handler.py`

- `save_file(file: UploadFile, storage_dir: str) -> str`
  - Saves uploaded file to `storage/` directory
  - Returns absolute path
- `get_file_as_base64(file_path: str) -> str`
  - Reads file, returns base64 string (for Mistral OCR API)
- `delete_file(file_path: str)`
  - Removes file from disk
- `list_stored_filenames() -> list[str]`
  - Returns all filenames currently in storage directory

---

## `utils/ocr.py`

- Initialize `MistralAsyncClient` using `settings.MISTRAL_API_KEY`
- `extract_with_ocr(file_path: str, doc_type: str) -> dict`
  - Converts file to base64
  - Calls Mistral OCR API (`mistral-ocr-latest`)
  - Supports: PDF, JPEG, PNG, WEBP
  - For DOCX: extract text using `python-docx` first, skip OCR API
  - Returns `{"raw_text": str, "confidence": float, "pages": list}`

---

## `agents/intake.py`

**Activity:** `intake_activity(document_id: str, filename: str) -> dict`

- Check `storage/` directory AND `Document` DB table for same filename
- Return `{"is_duplicate": bool, "existing_document_id": str | None}`
- No Mistral API calls — pure logic

---

## `agents/classifier.py`

**Activity:** `classifier_activity(document_id: str, file_path: str) -> dict`

- The Classifier agent is **pre-created in Mistral AI Studio** with its own system prompt, name, and instructions already configured there.
- Call the agent using `settings.CLASSIFIER_AGENT_ID` via the Mistral Agents API (`client.agents.complete()` or equivalent SDK method)
- Pass the OCR-extracted text of the document as the user message content
- The agent will respond with a JSON object — parse it to extract: `doc_type`, `confidence`, `reasoning`
- `doc_type` must be one of: `Invoice` · `Contract` · `Medical Record` · `KYC` · `Bank Record` · `Others`
- Return `{"doc_type": str, "confidence": float, "reasoning": str}`
- **Do NOT define any system prompt, agent name, or agent description in this file**

---

## `agents/extractor.py`

**Activity:** `extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict`

- The Extractor agent is **pre-created in Mistral AI Studio** with its own system prompt and extraction instructions already configured there.
- Call the agent using `settings.EXTRACTOR_AGENT_ID` via the Mistral Agents API
- **Invoice (implemented in v1):**
  - First call `extract_with_ocr()` from `utils/ocr.py` to get raw text
  - Pass the OCR text as the user message to the Extractor agent
  - The agent will respond with a JSON object — parse it to extract all `ExtractedInvoiceFields`
  - Return `{"fields": dict, "raw_ocr": str, "confidence": float}`
- **All other doc types:**
  - Skip the agent call entirely
  - Return `{"message": "Extractor not yet implemented for this document type", "doc_type": doc_type, "fields": {}, "confidence": 0.0}`
- **Do NOT define any system prompt, agent name, or extraction instructions in this file**

---

## `agents/validator.py`

**Activity:** `validator_activity(document_id: str, extracted_data: dict, doc_type: str) -> dict`

- The Validator agent is **pre-created in Mistral AI Studio** with its own validation rules and instructions already configured there.
- Call the agent using `settings.VALIDATOR_AGENT_ID` via the Mistral Agents API
- Pass the extracted data as a JSON string in the user message (e.g. `f"Validate this extracted invoice data: {json.dumps(extracted_data)}"`)
- The agent will respond with a JSON object — parse it to extract: `is_valid`, `confidence_score`, `validation_errors`, `validated_data`
- After receiving the agent response, apply this **local confidence score formula** in Python code (not by the agent):
  - `confidence_score` = OCR confidence × (validation rules passed / total rules)
  - This is computed locally to have a deterministic, auditable score regardless of agent response
- Return `{"is_valid": bool, "confidence_score": float, "validation_errors": list[str], "validated_data": dict}`
- **Do NOT define any system prompt, validation rules, or agent description in this file**

---

## `agents/reviewer.py`

**Activity:** Human-in-the-loop using Mistral Workflow `input()`

- The Reviewer agent is **pre-created in Mistral AI Studio** with its own review instructions already configured there.
- If `confidence_score >= 0.80`: auto-approve without calling the agent or pausing the workflow.
- If `confidence_score < 0.80`:
  - Optionally call `settings.REVIEWER_AGENT_ID` via the Mistral Agents API to generate a human-readable review summary of the extracted data (what looks correct, what looks suspicious). Pass the validated data as the user message.
  - Then pause the workflow using `workflow_context.input()` — this is the actual human-in-the-loop pause point. The agent summary can be stored in the `Document` DB record for the frontend to display alongside the pause.
  - The frontend reads the summary via `GET /status/{document_id}` and submits the human decision to the resume endpoint.
- **Do NOT define any system prompt or agent description in this file**

```python
async def reviewer_activity(workflow_context, document_id, validated_data, confidence_score):
    if confidence_score >= 0.80:
        return {"approved": True, "corrections": None, "auto_approved": True}

    # Optional: call Reviewer agent to generate a review summary for the human
    # summary = await call_agent(settings.REVIEWER_AGENT_ID, json.dumps(validated_data))
    # await db.store_review_summary(document_id, summary)

    # Pause workflow — waits for frontend to POST to /workflow/{run_id}/resume/review
    human_decision = await workflow_context.input(
        name="reviewer_decision",
        description=f"Document {document_id} confidence score: {confidence_score:.0%}. Review and approve or correct.",
        schema=ReviewerDecisionRequest.model_json_schema()
    )

    return {
        "approved": human_decision["approved"],
        "corrections": human_decision.get("corrections"),
        "auto_approved": False
    }
```

---

## `agents/output.py`

**Activity:** `output_activity(document_id, doc_type, validated_data, reviewer_result, confidence_score) -> dict`

- Merge reviewer corrections into `validated_data` if any
- Save `ExtractedData` record to DB (idempotent — upsert by `document_id`)
- Update `Document`: `status = completed`, `doc_type = doc_type`
- Return `{"success": True, "document_id": str, "final_data": dict}`

---

## `workflow.py`

Register workflow with Mistral Workflow SDK. Workflow name: `"document_processing_workflow"`.

**Step-by-step sequence:**

```python
async def document_processing_workflow(ctx, document_id, filename, file_path):

    # Step 1 — Intake
    await db.update_status(document_id, "processing")
    intake_result = await intake_activity(document_id, filename)

    if intake_result["is_duplicate"]:
        # Pause — wait for user duplicate override decision
        duplicate_decision = await ctx.input(
            name="duplicate_decision",
            description=f"File '{filename}' already exists. Override?",
            schema=DuplicateDecisionRequest.model_json_schema()
        )
        if not duplicate_decision["override"]:
            await db.update_status(document_id, "rejected")
            return {"status": "rejected", "reason": "duplicate_not_overridden"}

    # Step 2 — Classify
    classifier_result = await classifier_activity(document_id, file_path)
    doc_type = classifier_result["doc_type"]
    await db.update_doc_type(document_id, doc_type)

    # Step 3 — Extract
    extractor_result = await extractor_activity(document_id, file_path, doc_type)

    # Step 4 — Validate
    validator_result = await validator_activity(document_id, extractor_result["fields"], doc_type)

    # Step 5 — Review (may pause via input() if score < 80%)
    await db.update_status(document_id, "awaiting_review")
    reviewer_result = await reviewer_activity(ctx, document_id, validator_result["validated_data"], validator_result["confidence_score"])

    if not reviewer_result["approved"]:
        await db.update_status(document_id, "rejected")
        return {"status": "rejected", "reason": "reviewer_rejected"}

    # Step 6 — Output
    output_result = await output_activity(document_id, doc_type, validator_result["validated_data"], reviewer_result, validator_result["confidence_score"])
    return output_result
```

**Important:** All activities must be idempotent. Wrap every activity in try/except; on failure, set `Document.status = failed` and store error in `error_details`.

---

## `main.py` — FastAPI Endpoints

### `POST /upload`
- Accept `multipart/form-data` with file field
- Validate file type: `application/pdf`, `image/jpeg`, `image/png`, `image/webp`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Save file to `storage/` using `file_handler`
- Create `Document` DB record with `status = pending`
- Trigger Mistral Workflow asynchronously (non-blocking)
- Return `DocumentUploadResponse`

### `GET /status/{document_id}`
- Return current `Document` status, `doc_type`, `confidence_score`, extracted data if available
- Return `WorkflowStatusResponse`

### `POST /workflow/{workflow_run_id}/resume/duplicate`
- Body: `DuplicateDecisionRequest`
- Resume paused workflow at the duplicate `input()` point
- Use Mistral Workflow SDK resume mechanism

### `POST /workflow/{workflow_run_id}/resume/review`
- Body: `ReviewerDecisionRequest`
- Resume paused workflow at the reviewer `input()` point
- Use Mistral Workflow SDK resume mechanism

### `GET /documents`
- List all documents with status
- Query params: `page: int = 1`, `limit: int = 20`
- Return paginated list

### `GET /documents/{document_id}/extracted`
- Return full `ExtractedData` record including reviewer corrections

### `DELETE /documents/{document_id}`
- Set `Document.status = deleted`
- Remove file from `storage/` using `file_handler.delete_file()`
- Return `{"success": True}`

### App lifespan:
- **Startup:** `init_db()` · create `storage/` if not exists · initialize Mistral Workflow worker
- **Shutdown:** gracefully stop workflow worker

### CORS:
- Allow all origins (POC, local dev)

---

## `requirements.txt`

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
mistralai>=1.0.0
mistral-workflow
sqlalchemy>=2.0.0
aiosqlite>=0.20.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-multipart>=0.0.9
python-docx>=1.1.0
aiofiles>=23.0.0
```

---

## `README.md` Content

Include:
- Project overview and workflow diagram (ASCII)
- Setup: `cp .env.example .env` → fill `MISTRAL_API_KEY` and all four `*_AGENT_ID` values from Mistral AI Studio → `pip install -r requirements.txt` → `uvicorn main:app --reload`
- Section titled **"Setting Up Agents in Mistral AI Studio"** — explains that users must create 4 agents in [console.mistral.ai](https://console.mistral.ai), copy each Agent ID, and paste into `.env`
- All API endpoints with example `curl` commands
- Explanation of the two `input()` pause points and how to resume them via the resume endpoints
- Notes on extending the extractor to other document types

---

## Implementation Rules (Non-Negotiable)

1. **All DB operations must be async** — use `AsyncSession` throughout
2. **All IDs must be UUID4 strings** — never integers
3. **No hardcoded values** — everything from `config.py` / `.env`
4. **Activities must be idempotent** — safe to replay without double-inserting
5. **Every activity wrapped in try/except** — failures must set `status = failed` and populate `error_details`
6. **Structured logging** — use Python `logging` module, every log line must include `document_id` for traceability
7. **`input()` is the ONLY pause mechanism** — no polling, no websockets, no background tasks for human-in-the-loop
8. **DOCX handling** — use `python-docx` to extract text before passing to Mistral; do not send DOCX binary to OCR API directly
9. **File type whitelist** — reject anything not in: PDF, JPEG, PNG, WEBP, DOCX
10. **Confidence score formula** — `OCR confidence × (validation rules passed / total rules)` — computed locally in Python, not delegated to any agent
11. **Never create agents in code** — all agents are pre-created in Mistral AI Studio. The codebase only calls agents by ID. No agent name, description, model selection, or system prompt should appear anywhere in the Python code. Agent IDs come exclusively from `settings.*_AGENT_ID`.
12. **Agent calls use Mistral Agents API** — use `client.agents.complete(agent_id=settings.CLASSIFIER_AGENT_ID, messages=[...])` or the equivalent async SDK method. Never use `client.chat.complete()` for activities that have a designated agent.

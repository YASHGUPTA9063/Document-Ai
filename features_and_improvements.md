# Document-AI — Feature & Improvement Opportunities

> A thorough audit of the project across **Backend**, **Frontend**, **Workflow & AI**, **Security**, **DevOps**, and **UX** dimensions.

---

## 🔴 Critical Bugs / Broken Logic

### 1. Duplicate Detection Uses Filename Only (Not Content Hash)
**Files:** [`intake.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/intake.py), [`file_handler.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/utils/file_handler.py)

**Reason:** The spec explicitly calls for **SHA-256 hash-based** duplicate detection, but `intake_activity` only compares filenames via `check_duplicate_filename()`. Two documents with different names but identical content will pass through as unique. The spec also mentions `list_stored_filenames()` being used, but the code itself acknowledges this logic is incomplete (comment on line 21–24 of `intake.py`).

**Fix:** Compute a SHA-256 hash of the uploaded file bytes in `save_file()`, store it in a new `file_hash` column on `Document`, and compare hashes in `intake_activity`.

---

### 2. Confidence Score Formula Is Not Implemented
**File:** [`validator.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/validator.py)

**Reason:** The spec mandates a **local deterministic** confidence formula: `OCR confidence × (validation rules passed / total rules)`. Currently, the validator just passes through `ocr_confidence` directly without applying the formula. The validator agent response fields `is_valid` and `validation_errors` are parsed but never used to compute the actual score.

**Fix:** Count `validation_errors` returned by the agent and apply the formula in Python before returning the result.

---

### 3. `Document.filename` Column Has No `unique=True` Constraint
**File:** [`models.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/db/models.py)

**Reason:** The spec says `filename` should be `unique`. The model only has `index=True`. This means the DB won't enforce uniqueness, so concurrent uploads of the same filename can race past the duplicate check and both succeed.

**Fix:** Add `unique=True` to the `filename` column and handle `IntegrityError` in the upload endpoint.

---

### ~~4. `DELETE /documents/{document_id}` Sets Status to "deleted" But Never Removes from DB~~ ✅ IMPLEMENTED
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L539-L553)

**Reason:** The delete endpoint marks `doc.status = "deleted"` but keeps the row in the database. These phantom documents will show up in `GET /documents` and pollute analytics. Since `filename` isn't truly unique-constrained, deleted documents also prevent re-uploading the same filename.

**Fix (applied):** Soft-delete approach — `GET /documents` now filters out `status = "deleted"` rows via a `.where(Document.status != "deleted")` clause. `GET /status/{document_id}` also returns HTTP 404 for soft-deleted documents. The row remains in the DB for audit purposes but is invisible to all read APIs.

---

### ~~5. Test/Fake Files Committed to Repo~~ ✅ IMPLEMENTED
**Files:** `backend/test.png`, `backend/test.txt`, `backend/fake2.png`, `backend/test_duplicate.png`

**Reason:** These appear to be scratch files from development (8–13 bytes each, clearly placeholders). They shouldn't be in the repository. These also live outside the `storage/` directory, bypassing the normal file lifecycle.

**Fix (applied):** All four files deleted from disk and removed from git index (`git rm --cached`). Added the following rules to [`.gitignore`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/.gitignore): `test.*`, `test_*.*`, `fake*.*`, `scratch.*`, and `storage/`.

---

## 🟠 Missing Backend Features

### 6. No Export Endpoint for Extracted Data (CSV / JSON download)
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py)

**Reason:** The UI describes the pipeline as outputting "Structured JSON persisted & ready to export", but there is no `GET /documents/{id}/export` endpoint. Users have no way to download results programmatically or in bulk without hitting raw API JSON. This is a core use-case for document processing.

**Fix:** Add `GET /documents/{id}/export?format=json|csv` that serializes `ExtractedData.validated_data` into the requested format and returns a file download.

---

### 7. No Bulk Export / Archive Endpoint
**Reason:** There's no way to export all completed documents at once (e.g., a ZIP of all JSONs, or a master CSV). In real document pipelines, this is a primary delivery mechanism.

**Fix:** Add `GET /documents/export/bulk?status=completed&format=csv|json` with optional date range filtering.

---

### 8. No Pagination `total` Count in `GET /documents`
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L487-L494)

**Reason:** The `/documents` endpoint returns a list with `page`/`limit` params but never returns the total document count. The frontend has no way to know how many pages exist, making proper pagination impossible.

**Fix:** Add a `count(*)` query and return `{"items": [...], "total": n, "page": p, "limit": l}`.

---

### 9. No Search / Filter on `GET /documents`
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L487-L494)

**Reason:** The documents list has no filtering by `status`, `doc_type`, date range, or filename search. With more than a handful of documents, users are completely blind.

**Fix:** Add optional query params: `?status=completed&doc_type=invoice&filename=foo&from=2025-01-01&to=2025-06-01`.

---

### 10. No Webhook / Notification System for Workflow Completion
**File:** [`activities/output.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/output.py)

**Reason:** The `Output Agent` description in the code even lists "Webhook Notifier" as one of its tools, but no webhook implementation exists. Integrating systems have to poll `/status/{id}` to know when processing finishes — highly inefficient.

**Fix:** Add an optional `callback_url` field to the upload request; on workflow completion, POST the result JSON to that URL.

---

### 11. No Re-processing / Retry Endpoint for Failed Documents
**Reason:** When a document fails at any pipeline stage, there's no way to resubmit it without re-uploading the file. Users must delete and re-upload.

**Fix:** Add `POST /documents/{document_id}/reprocess` that re-triggers the Mistral workflow with the stored `file_path`.

---

### 12. SQLite Used in Production Context with No Migration Tool
**File:** [`config.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/config.py), [`database.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/db/database.py)

**Reason:** SQLite is fine for POC, but `init_db()` uses `create_all()` which can't handle schema migrations. Any model change will silently fail on existing databases. There's no Alembic setup.

**Fix:** Add Alembic for migrations, or at minimum switch to PostgreSQL with asyncpg when moving beyond POC.

---

### 13. No Rate Limiting on Upload Endpoints
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py)

**Reason:** The `/upload` and `/upload/batch` endpoints have no rate limiting. A single client can flood the system with 20-file batches in rapid succession, exhausting Mistral API quota and disk space.

**Fix:** Integrate `slowapi` (FastAPI-compatible rate limiter) with per-IP limits on upload routes.

---

### 14. CORS Is Wildcard (`allow_origins=["*"]`)
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L60-L66)

**Reason:** Acceptable for local dev, but wildcard CORS is a security risk in any shared/staging environment. CORS origins should come from config.

**Fix:** Add `CORS_ORIGINS` to `config.py`/`.env` and replace the wildcard.

---

### 15. No File Size Limit on Uploads
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L76-L117)

**Reason:** There is no maximum file size check. A user can upload a 500MB PDF and it will be accepted, read entirely into memory, and forwarded to the Mistral OCR API.

**Fix:** Add a `MAX_FILE_SIZE_MB` config setting and reject files exceeding it before saving to disk.

---

### 16. Workflow Timeout Is 24 Hours With No Configurable Override
**File:** [`workflow.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/workflow.py#L49)

**Reason:** Both `wait_for_input` calls use a hardcoded `timedelta(hours=24)`. This should be configurable per deployment context (e.g., `REVIEW_TIMEOUT_HOURS` in `.env`).

**Fix:** Move timeouts to `config.py` as `DUPLICATE_REVIEW_TIMEOUT_HOURS` and `HUMAN_REVIEW_TIMEOUT_HOURS`.

---

## 🟡 Missing Frontend Features

### 17. No Real-time WebSocket / SSE Updates — Polling Only
**File:** [`frontend-v2/src/hooks/useDocumentPoller.js`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/hooks)

**Reason:** The frontend polls document status via intervals (`setInterval` in Dashboard and a custom hook). This creates unnecessary API load and adds up to 10 seconds of status lag. A WebSocket or Server-Sent Events channel would provide instant, push-based status updates.

**Fix:** Add a `GET /documents/{id}/stream` SSE endpoint on the backend and replace polling with an `EventSource` in the frontend hook.

---

### 18. No Document Search / Filter UI
**File:** [`frontend-v2/src/pages/Documents.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Documents.jsx)

**Reason:** The Documents page renders a flat list with no filtering, search input, or date range picker. As the document count grows, this becomes unusable.

**Fix:** Add a search bar, status filter dropdown, doc type filter, and date range picker that feed into the backend's (to-be-built) filter params.

---

### ~~19. No Side-by-Side Document Viewer + Extracted Data Panel~~ ✅ IMPLEMENTED
**File:** [`frontend-v2/src/pages/Extraction.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Extraction.jsx)

**Reason:** The Extraction page shows extracted fields but not the original document alongside them. Reviewers have to mentally cross-reference between the AI output and the source document, making corrections error-prone.

**Fix (applied):** The left panel is now a sticky document viewer (PDF via `<object>` + iframe fallback, images via `<img>`) that stays fixed as the user scrolls the extracted fields on the right. A "⛶ Expand" button opens a full-screen overlay viewer and a "↗ New tab" link is always available. A confidence banner is pinned to the bottom of the viewer. The viewer height matches the viewport so both panels are always in sync visually.

---

### 20. Analytics Page Has No Time-Series / Trend Data
**File:** [`frontend-v2/src/pages/Analytics.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Analytics.jsx)

**Reason:** The Analytics page shows only aggregate counts (total, success rate, etc.) and static distributions. There's no view of how processing volume, success rate, or confidence scores change over time.

**Fix:** Add backend endpoints for time-bucketed metrics (`/analytics/daily`) and render a line/area chart on the frontend (using a library like `recharts`).

---

### ~~21. No Inline Edit for Reviewer Corrections~~ ✅ IMPLEMENTED
**File:** [`frontend-v2/src/pages/Validation.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Validation.jsx)

**Reason:** The Validation page allows reviewers to approve/reject, but the schema supports `corrections: dict`. There is no UI to actually input field-level corrections. Reviewers can only approve or reject wholesale — they can't fix individual extracted fields.

**Fix (applied):** The "Edit & Approve" modal now renders each field from `validated_data` as a styled labelled input pre-filled with the current value. Only fields whose values differ from the original are collected into the `corrections` dict. Each modified field shows a "modified" pill badge, the original value below the input as a hint, and an individual "↩ reset" button. The submit button dynamically labels itself with the correction count (e.g. "Save 2 Corrections & Approve"). Complex/nested fields are noted but excluded from inline editing.

---

### 22. No Dark/Light Theme Toggle
**Reason:** The app appears to use a single dark theme defined in CSS variables. There's no user preference toggle, and the theme isn't persisted across sessions.

**Fix:** Add CSS variables for a light theme, a toggle button in the nav, and `localStorage` persistence.

---

### 23. No Toast / Notification for Review Timeouts
**Reason:** If a document's `wait_for_input` call times out (after 24h), the workflow silently fails. The frontend has no alert for this edge case.

**Fix:** Track `awaiting_review` documents and show a warning toast if they haven't been actioned within a configurable window.

---

### 24. Upload Page Has No File Preview Before Submitting
**File:** [`frontend-v2/src/pages/Upload.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Upload.jsx)

**Reason:** Users can't see a thumbnail/preview of the files they've queued before submitting to the AI pipeline. This reduces confidence in what they're uploading, especially for image files.

**Fix:** Generate image thumbnails using `FileReader` + `<canvas>` for images, and a PDF page preview using `pdfjs-dist` for PDFs — shown in the `QueueItem` row.

---

### 25. Batch Upload Progress Is Estimated, Not Real
**File:** [`frontend-v2/src/pages/Upload.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Upload.jsx#L202)

**Reason:** The `batchProgress` state is driven by an `onProgress` callback from the API client, but batch upload is a single multipart HTTP request — `XMLHttpRequest.upload.onprogress` only reflects the upload transfer, not server-side AI processing. The displayed % can be misleading.

**Fix:** Clearly label the progress bar as "Upload Transfer Progress" and add a separate "AI Processing" indicator that reflects the polling state of each document.

---

### 26. `frontend` and `frontend-v2` Both Exist — Unclear Which Is Active
**Directories:** [`frontend/`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend), [`frontend-v2/`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2)

**Reason:** Two frontend directories exist. `frontend/` lacks a `.env` file and `node_modules`, suggesting it's abandoned. Having two frontends causes confusion for contributors and CI/CD setup.

**Fix:** Delete or archive `frontend/` and rename `frontend-v2/` to `frontend/`. Update all documentation references.

---

## 🟢 AI / Workflow Improvements

### 27. Classifier Result Confidence Is Not Stored
**File:** [`workflow.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/workflow.py#L59-L61), [`activities/classifier.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/classifier.py)

**Reason:** `classifier_activity` returns `{"doc_type", "confidence", "reasoning"}`, but only `doc_type` is saved to the DB. The classifier confidence and reasoning are silently discarded. These are valuable audit signals.

**Fix:** Add `classifier_confidence` and `classifier_reasoning` columns to the `Document` model, or store them in `error_details` / a new `pipeline_metadata` JSON column.

---

### 28. No Retry Logic for Transient Mistral API Failures
**File:** All activity files

**Reason:** All `client.agents.complete()` calls are wrapped in `try/except` that immediately marks the document as `failed`. A single transient 503 or rate-limit response will permanently fail the document.

**Fix:** Implement exponential backoff with `tenacity` for all Mistral API calls. Configure `MISTRAL_MAX_RETRIES` and `MISTRAL_RETRY_WAIT` in `config.py`.

---

### 29. OCR Is Run Twice in Extractor Fallback Path
**File:** [`activities/extractor.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/extractor.py#L133-L147)

**Reason:** In the "agent skipped tool call" fallback path, OCR is run first, then the result is passed to the agent. But in the normal path, the agent requests OCR via a tool call. If the agent forgets to call the tool, OCR still runs — but the agent is then called again with the raw text in a separate request. The result is two separate Mistral API calls in the failure path vs. one round-trip in the normal path. This inconsistency can lead to subtle quality differences.

**Fix:** Standardize on always running OCR first locally, then pass the result to the agent — eliminating the function-calling round-trip entirely. Or, commit fully to the tool-call pattern and only fallback if OCR itself fails.

---

### 30. No Multi-Page Support / Page-Level Confidence
**File:** [`utils/ocr.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/utils)

**Reason:** The OCR utility returns a single `confidence` float and a `pages` list, but the `pages` data is never used downstream. Multi-page PDFs likely have page-level confidence variation that the current pipeline ignores — averaging everything into one number.

**Fix:** Store per-page OCR confidence, compute a weighted average confidence (by character/word count), and flag low-confidence pages in the extraction output.

---

### 31. No Support for Scanned / Low-Quality Document Pre-processing
**Reason:** Documents with poor scan quality (skew, low DPI, noise) will have low OCR confidence. There's no image pre-processing step (deskew, denoise, contrast enhancement) before OCR.

**Fix:** Add an optional pre-processing step using `Pillow` (or `opencv-python`) to auto-rotate, normalize contrast, and denoise images before passing to OCR.

---

### 32. `reviewer_activity` Summary Is Not Surfaced to the UI
**File:** [`activities/reviewer.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/reviewer.py#L21-L29)

**Reason:** The reviewer agent generates a human-readable summary of extracted data, but it's only logged — never stored in the DB and never sent to the frontend. The human reviewer has to understand raw JSON without any AI-generated context.

**Fix:** Store the summary in a new `review_summary` field on `Document` or `ExtractedData`, and display it prominently in the Validation page above the correction form.

---

## 🔵 Developer Experience / DevOps

### 33. No Docker / Docker Compose Setup
**Reason:** The backend requires Python 3.11+, specific pip packages, and environment variables. There's no `Dockerfile` or `docker-compose.yml`, making onboarding from scratch painful.

**Fix:** Add a `Dockerfile` for the backend and a `docker-compose.yml` that wires the backend, and optionally a frontend build service.

---

### 34. No Unit or Integration Tests
**Reason:** The project has zero test files. With complex async workflows, multi-agent coordination, and human-in-the-loop logic, untested code is extremely fragile.

**Fix:** Add `pytest` + `pytest-asyncio` with:
- Unit tests for all activities with mocked Mistral client
- Integration tests for the workflow using a test DB
- API endpoint tests using `httpx.AsyncClient`

---

### 35. No API Documentation Beyond FastAPI Auto-Docs
**Reason:** While FastAPI generates Swagger docs automatically, there are no rich descriptions, examples, or error response schemas on most endpoints. The `DELETE` endpoint has no documented error responses.

**Fix:** Add `summary`, `description`, `responses`, and `examples` to all endpoint decorators. Add a custom OpenAPI description to the `FastAPI()` constructor.

---

### 36. No Structured Logging / Log Aggregation
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L29-L30)

**Reason:** Python's basic `logging.basicConfig` is used. In production, logs need to be structured (JSON), include request IDs, and be shipped to a log aggregator (Datadog, CloudWatch, etc.).

**Fix:** Replace with `structlog` or configure `python-json-logger` for JSON-structured output. Add a middleware that injects a request ID into every log line.

---

### 37. Workflow Run ID Is Stored as "unknown_run_id" on Failure
**File:** [`main.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/main.py#L106)

**Reason:** The `run_id` fallback is the string `"unknown_run_id"`, which is then stored in the DB. This makes it impossible to distinguish between documents that genuinely have no run ID vs. those that failed silently.

**Fix:** Use `None` as the fallback and handle `nullable` properly downstream.

---

### 38. `.env` File Is Tracked by `.gitignore` But `doc_workflow.db` Is Not
**File:** [`.gitignore`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/.gitignore)

**Reason:** The SQLite database file (`doc_workflow.db`) likely contains real document data and should never be committed. Confirm it's excluded.

**Fix:** Ensure `*.db` and `storage/` are in `.gitignore`. (The previous conversation addressed `__pycache__`, but these data files deserve explicit entries.)

---

### 39. `agents/` Directory in Spec But `activities/` in Code
**File:** [`mistral_doc_workflow_spec.md`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/mistral_doc_workflow_spec.md)

**Reason:** The spec defines the directory as `agents/`, but the implementation uses `activities/`. This naming drift means the spec and code are misaligned, which will confuse new contributors.

**Fix:** Pick one name and update both the spec and the code to match. (Or rename the directory and update all imports — `activities/` better reflects that these are Mistral Workflow activities, not standalone agents.)

---

## ⚪ UX / Polish

### 40. Dashboard Auto-Refresh Is Every 10 Seconds — Too Slow
**File:** [`frontend-v2/src/pages/Dashboard.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Dashboard.jsx#L42-L45)

**Reason:** With a 10-second polling interval, a user watching a document process will see stale status for up to 10 seconds per state transition. The pipeline can pass through multiple states (classifying → extracting → validating) within that window.

**Fix:** Reduce to 3–5 seconds, or — better — switch to SSE (see #17).

---

### 41. No Empty State Handling on the Processing / Validation Pages
**File:** [`frontend-v2/src/pages/Processing.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Processing.jsx), [`Validation.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Validation.jsx)

**Reason:** When no documents are in-pipeline or awaiting review, these pages likely render empty containers. There's no friendly empty state with guidance (e.g., "Nothing to review — upload a document to get started").

**Fix:** Add illustrated empty state components consistent with Dashboard's pattern.

---

### 42. No Keyboard Shortcuts for Reviewer Actions
**File:** [`frontend-v2/src/pages/Validation.jsx`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/frontend-v2/src/pages/Validation.jsx)

**Reason:** Power reviewers processing many documents per day would benefit from keyboard shortcuts (`A` = approve, `R` = reject, `N` = next document).

**Fix:** Add a `useKeyboardShortcuts` hook on the Validation page that binds common review actions.

---

### 43. Confidence Score Threshold Is Hardcoded at 80%
**File:** [`activities/reviewer.py`](file:///c:/Users/Dhruvkumar/Desktop/Document-Ai/backend/activities/reviewer.py#L17)

**Reason:** The `>= 0.80` auto-approve threshold is hardcoded. Different organizations may need different thresholds (e.g., financial documents at 95%, internal memos at 60%).

**Fix:** Add `AUTO_APPROVE_CONFIDENCE_THRESHOLD` to `config.py` / `.env`.

---

### 44. No Audit Trail / History Log Per Document
**Reason:** There's no record of who reviewed a document, when they reviewed it, what corrections they made, or how many times the document was reprocessed. This is essential for compliance use-cases (KYC, medical, legal).

**Fix:** Add a `DocumentEvent` table that logs every status transition, reviewer action, and correction with a timestamp and optional `reviewer_id`.

---

### 45. No Multi-Tenant / User Authentication
**Reason:** The entire system is single-tenant with no authentication. Any user with network access can see, delete, or submit review decisions for any document.

**Fix:** Add JWT-based authentication (FastAPI + `python-jose`). Scope document access and review permissions per user/team.

---

*Last updated: 2026-06-02 | Audited by: Antigravity*

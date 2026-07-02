# Multi-Agent Workflow Refactoring Tracker

This document tracks the progress of refactoring the Document-Ai processing workflow from a hybrid Python/Agent system to a fully Agent-driven workflow with Tool Calls.

---

## Architectural Goal
Remove all direct domain-specific function calls, database reads/writes, and external API requests from the main workflow and activities, and delegate them to Mistral Agents as Tool Calls. The only exceptions are workflow status updates and pause/resume mechanisms.

---

## Overall Refactoring Plan

| Stage | Activity / Function | Current Direct Calls (Python / DB) | Target Agent & Tools | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Intake** | `db.get_document()`, `db.check_duplicate_hash()`, `db.check_duplicate_filename()` | **Intake Agent** calling `check_document_duplicates` | **COMPLETED** |
| **2** | **Pre-Validation** | Vision API request directly in Python, DOCX auto-pass executed in Python | **Pre-Validator Agent** calling `get_file_metadata` | **COMPLETED** |
| **3** | **Preprocessing** | `preprocess_image()` (OpenCV/CLAHE/Gaussian/Skew) called directly | **Preprocessing Agent** calling `enhance_document_image` | **COMPLETED** |
| **4** | **Classifier** | OCR call, template reads, and page-count checks called directly in Python | **Classifier Agent** calling `get_document_text` and `get_supported_document_types` | **COMPLETED** |
| **5** | **Fraud Check** | Google Document AI client / output.json mock read called directly | **Fraud Examiner Agent** calling `run_identity_proofing` | **COMPLETED** |
| **6** | **Extractor** | Template reads, confidence calculations, and KYC signature/photo cropping | **Extractor Agent** calling `extract_text` and `crop_signature_and_photo` | **COMPLETED** |
| **7** | **Validator** | Template schema formatting and JSON parsing done directly in Python | **Validator Agent** calling `get_validation_schema` | **COMPLETED** |
| **8** | **Auto-Verify** | DB lookups, ML pipelines (DINOv2 + face morphology) called directly | **Auto-Verifier Agent** calling `find_customer_reference`, `verify_signature`, `verify_face` | **COMPLETED** |
| **9** | **Reviewer** | Summary generation called directly via Reviewer Agent (no tools) | **Reviewer Agent** calling `get_review_context` | **COMPLETED** |
| **10**| **Output** | SQLAlchemy commits saving to `ExtractedData` and `Document` done directly | **Output Agent** calling `persist_final_extraction` | **COMPLETED** |

---

## Detailed Stage Progress

### 📥 Stage 1: Intake Phase
*   **Target Agent:** `Intake Agent` (New agent to be created)
*   **Direct Functions Removed:**
    *   `db.get_document(document_id)`
    *   `db.check_duplicate_hash(hash)`
    *   `db.check_duplicate_filename(filename)`
*   **Refactored Logic:**
    *   Exposed a tool `check_document_duplicates` to check database for file hash or name duplicates.
    *   Refactored `activities/intake.py` to call the Intake Agent. The agent calls the duplicate tool, processes the tool's JSON output, and returns the final duplicate verdict.
*   **Status:** **COMPLETED**

### 🛡️ Stage 2: Pre-Validation Phase
*   **Target Agent:** `Pre-Validator Agent` (Existing vision agent)
*   **Direct Functions Removed:**
    *   `get_file_as_base64(file_path)` (moved into tool-triggered vision block builder)
    *   DOCX auto-pass checks (delegated to agent decision tree)
*   **Refactored Logic:**
    *   Exposed a tool `get_file_metadata` to check file extension, MIME type, and see if visual analysis is needed.
    *   Refactored `activities/pre_validator.py` to call the Pre-Validator Agent. The agent calls the metadata tool. If visual representation is required, Python base64-encodes the file and appends it to the conversation in the next turn before completing validation.
*   **Status:** **COMPLETED**

### ⚙️ Stage 3: Preprocessing Phase
*   **Target Agent:** `Preprocessing Agent` (New agent to be created)
*   **Direct Functions Removed:**
    *   `preprocess_image(...)` (from `utils.preprocessor`) called directly inside the activity.
*   **Refactored Logic:**
    *   Exposed a tool `enhance_document_image` to trigger resolution normalization, CLAHE brightness adjustment, Gaussian noise filter, and skew angle rotation on an image.
    *   Refactored `activities/preprocessor.py` to call the Preprocessing Agent. The agent calls the enhancement tool with the input and output paths, parses the resulting logs, and returns the preprocessed file path.
*   **Status:** **COMPLETED**

### 🏷️ Stage 4: Classifier Phase
*   **Target Agent:** `Classifier Agent` (Existing text classifier agent)
*   **Direct Functions Removed:**
    *   `extract_with_ocr(...)` (called before classifier run to get text)
    *   `pypdf.PdfReader` checks for page constraints (moved into tool logic)
    *   `get_supported_doc_types()` (moved into tool logic loading `templates.json`)
*   **Refactored Logic:**
    *   Exposed two tools:
        1. `get_supported_document_types`: returns a list of supported document categories in the system.
        2. `get_document_text`: runs OCR on the document file path (pages 1 and 2 for PDFs) and returns raw text.
    *   Refactored `activities/classifier.py` to call the Classifier Agent with these tools. The agent calls the tools sequentially to discover the templates, read the document content, classify it, and return the structured JSON decision.
*   **Status:** **COMPLETED**

### 🛡️ Stage 5: Fraud Check Phase
*   **Target Agent:** `Fraud Examiner Agent` (New agent to be created)
*   **Direct Functions Removed:**
    *   Google Document AI client code (moved into tool logic)
    *   `output.json` mock fallback logic (moved into tool logic)
*   **Refactored Logic:**
    *   Exposed a tool `run_identity_proofing` that runs Google Document AI Identity Proofing or loads the mock `output.json` locally on failure.
    *   Refactored `activities/fraud_checker.py` to call the Fraud Examiner Agent. The agent calls `run_identity_proofing` to fetch the forensic check statuses, evaluates the results, and returns the final JSON fraud check verdict.
*   **Status:** **COMPLETED**

### 📑 Stage 6: Extractor Phase
*   **Target Agent:** `Extractor Agent` (Existing field extraction agents)
*   **Direct Functions Removed:**
    *   `get_template_fields` and `get_template_metadata` called directly in the activity.
    *   `extract_signature_and_photo` (KYC crops) called directly in Python.
    *   `_compute_confidences_recursive` and `_calculate_field_confidence` (moved inside tool logic or executed post-extraction using saved OCR results).
*   **Refactored Logic:**
    *   Exposed two tools:
        1. `extract_text_from_document`: runs OCR with target schema annotations and returns raw and structured fields.
        2. `crop_kyc_images`: extracts bounding box crops (signature/photo) for identity documents.
    *   Refactored `activities/extractor.py` to call the Extractor Agent. The agent calls the tools in sequence. To optimize token usage, the `crop_kyc_images` tool returns status flags to the agent, while the Python layer temporarily saves the massive base64 crops and re-injects them post-extraction.
*   **Status:** **COMPLETED**

### ✅ Stage 7: Validator Phase
*   **Target Agent:** `Validator Agent` (Existing validator agent)
*   **Direct Functions Removed:**
    *   `get_template_fields(...)` called directly in python validation prompt construction.
*   **Refactored Logic:**
    *   Exposed a tool `get_validation_schema` to load the validation target schema fields for a given document type.
    *   Refactored `activities/validator.py` to call the Validator Agent. The agent calls the schema tool, receives the fields configurations, validates the input JSON payload against those fields, and outputs the final JSON validation verdict.
*   **Status:** **COMPLETED**

### 🔍 Stage 8: Auto-Verifier Phase
*   **Target Agent:** `Auto-Verifier Agent` (New agent to be created)
*   **Direct Functions Removed:**
    *   `CustomerReference` DB lookup and matching logic (moved to tool).
    *   `Document.customer_id` persistence (moved to tool).
    *   `run_verification_pipeline` (DINOv2 signature check) execution (moved to tool).
    *   `run_face_verification_pipeline` (face morphology verification) execution (moved to tool).
*   **Refactored Logic:**
    *   Exposed three tools:
        1. `find_customer_reference`: searches DB for a matching customer ID or details, automatically links it, and reports available validation elements.
        2. `verify_signature`: executes DINOv2 signature comparison pipeline locally on temp files.
        3. `verify_face`: executes face morphology verification pipeline locally on temp files.
    *   Refactored `activities/auto_verifier.py` to call the Auto-Verifier Agent. The agent calls the tools sequentially based on what reference/extracted assets are available, evaluates the result structures, and outputs the final JSON verification verdict.
*   **Status:** **COMPLETED**

### 👤 Stage 9: Reviewer Phase
*   **Target Agent:** `Reviewer Agent` (Existing reviewer agent)
*   **Direct Functions Removed:**
    *   Auto-approval score comparison logic (moved to Agent prompts/decisions).
    *   Reviewer data serialization/formatting done directly in Python.
*   **Refactored Logic:**
    *   Exposed a tool `get_review_context` to fetch the confidence score and stripped validated data payload.
    *   Refactored `activities/reviewer.py` to call the Reviewer Agent. The agent calls `get_review_context` to fetch score and data, checks if the document meets auto-approval rules, constructs the summary if human review is required, and returns the final JSON review status.
*   **Status:** **COMPLETED**

### 📤 Stage 10: Output Phase
*   **Target Agent:** `Output Agent` (New agent to be created)
*   **Direct Functions Removed:**
    *   Database transaction, `ExtractedData` record creation/modification, and `Document` status updates (moved to tool).
*   **Refactored Logic:**
    *   Exposed a tool `persist_final_extraction` which updates database models and commits transactions.
    *   Refactored `activities/output.py` to call the Output Agent. The agent calls `persist_final_extraction` to write all workflow outputs to the database, completing the document processing loop, and returns the final success JSON.
*   **Status:** **COMPLETED**

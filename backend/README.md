# Mistral Document Processing Workflow

Production-grade POC backend for multi-agent document ingestion, classification, extraction, validation, and human-in-the-loop review.

## Architecture

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
[VALIDATOR] → validation_errors
  │
  ▼
[REVIEWER] ── score < 80%? ──► input() pause ──► user: approve / correct
  │ auto-approved or approved
  ▼
[OUTPUT] → save to DB → return final response
```

## Setting Up Agents in Mistral AI Studio
You must pre-create four agents in [console.mistral.ai](https://console.mistral.ai/):
1. **Classifier**
2. **Extractor**
3. **Validator**
4. **Reviewer**

After creating these agents, copy their Agent IDs (format: `ag:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) and paste them into your `.env` file. The backend logic *only* uses these Agent IDs; no system prompts or configuration are defined in code.

## Setup Instructions

1. **Environment Setup:**
   ```bash
   cp .env.example .env
   ```
   Fill in `MISTRAL_API_KEY` and all four `*_AGENT_ID` values.

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application:**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

## API Endpoints

### `POST /upload`
Upload a document. Supported formats: PDF, JPEG, PNG, WEBP, DOCX.
```bash
curl -X POST -F "file=@invoice.pdf" http://localhost:8000/upload
```

### `GET /status/{document_id}`
Get the status of a document workflow.
```bash
curl http://localhost:8000/status/uuid-1234
```

### Human-in-the-Loop Resumes

If the workflow pauses because it detects a duplicate filename:
```bash
curl -X POST http://localhost:8000/workflow/{run_id}/resume/duplicate \
     -H "Content-Type: application/json" \
     -d '{"override": true}'
```

If the workflow pauses because confidence is < 80%:
```bash
curl -X POST http://localhost:8000/workflow/{run_id}/resume/review \
     -H "Content-Type: application/json" \
     -d '{"approved": true, "corrections": {"vendor_name": "Corrected Vendor"}}'
```

### `GET /documents`
List all documents paginated.
```bash
curl "http://localhost:8000/documents?page=1&limit=20"
```

### `GET /documents/{document_id}/extracted`
Get final extracted data.
```bash
curl http://localhost:8000/documents/uuid-1234/extracted
```

### `DELETE /documents/{document_id}`
Delete a document and its stored file.
```bash
curl -X DELETE http://localhost:8000/documents/uuid-1234
```

## Extending to other Document Types
To extend to other document types, configure the Extractor Agent in the Mistral Studio to handle additional documents. Modify `backend/activities/extractor.py` to route logic depending on the `doc_type` returned by the Classifier.

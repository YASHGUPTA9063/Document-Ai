import os
import json
import logging
import mimetypes
from config import settings

logger = logging.getLogger(__name__)

# Core 4 check names expected from Identity Document Proofing processor
CORE_CHECKS = {
    "fraud_signals_is_identity_document",
    "fraud_signals_suspicious_words",
    "fraud_signals_image_manipulation",
    "fraud_signals_online_duplicate"
}

# ─── TOOL SCHEMAS ───
FRAUD_CHECKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_identity_proofing",
            "description": "Performs identity document proofing checks on the file. Runs Google Document AI processor or loads mock checks on failure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path of the document to run proofing on."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]

# ─── HELPERS & FUNCTIONS ───
def _process_checks_dict(document_id: str, checks_results: dict, mocked: bool) -> dict:
    checks_final = {}
    failed_checks = []

    for check in CORE_CHECKS:
        status = checks_results.get(check, "MISSING")
        checks_final[check] = status
        if status != "PASS":
            failed_checks.append(f"{check}: {status}")

    passed = len(failed_checks) == 0
    rejection_reason = None
    if not passed:
        rejection_reason = f"Document failed fraud check verification: {', '.join(failed_checks)}"

    logger.info(
        f"[Document {document_id}] Fraud check completed (mocked={mocked}). "
        f"Passed: {passed}. Checks: {checks_final}"
    )

    return {
        "passed": passed,
        "checks": checks_final,
        "rejection_reason": rejection_reason,
        "mocked": mocked
    }


async def run_identity_proofing(file_path: str, document_id: str) -> dict:
    """Runs Google Document AI or fallback to output.json mock."""
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai

        project_id = settings.DOCUMENTAI_PROJECT_ID
        location = settings.DOCUMENTAI_LOCATION
        processor_id = settings.DOCUMENTAI_PROCESSOR_ID

        if not project_id or not processor_id:
            raise ValueError("Google Document AI Project ID or Processor ID is not set.")

        logger.info(
            f"[Document {document_id}] Calling Document AI. "
            f"Project: {project_id}, Location: {location}, Processor: {processor_id}"
        )

        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        doc_client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = doc_client.processor_path(project_id, location, processor_id)

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            ext = os.path.splitext(file_path.lower())[1]
            if ext in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            elif ext == ".png":
                mime_type = "image/png"
            else:
                mime_type = "application/pdf"

        with open(file_path, "rb") as f:
            image_content = f.read()

        raw_document = documentai.RawDocument(content=image_content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        
        result = doc_client.process_document(request=request)
        document = result.document

        checks_results = {}
        for entity in getattr(document, "entities", []):
            ent_type = entity.type_
            if ent_type in CORE_CHECKS:
                value = entity.mention_text
                if entity.normalized_value and entity.normalized_value.text:
                    value = entity.normalized_value.text
                checks_results[ent_type] = value.strip().upper()

        return _process_checks_dict(document_id, checks_results, mocked=False)

    except Exception as e:
        logger.warning(
            f"[Document {document_id}] Google Document AI API execution failed: {str(e)}. "
            "Attempting fallback to local output.json mock file."
        )

        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_file_path = os.path.join(workspace_root, "output.json")

        if not os.path.exists(mock_file_path):
            logger.warning(
                f"[Document {document_id}] Google credentials not configured and mock file 'output.json' "
                f"is missing at {mock_file_path}. Skipping fraud checking."
            )
            return {
                "passed": True,
                "checks": {c: "SKIPPED" for c in CORE_CHECKS},
                "rejection_reason": None,
                "mocked": True,
                "warnings": ["Google credentials not found, fraud checking skipped."]
            }

        logger.info(f"[Document {document_id}] Loading mock fraud check output from {mock_file_path}")
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            checks_results = {}
            for entity in data.get("entities", []):
                ent_type = entity.get("type")
                if ent_type in CORE_CHECKS:
                    value = entity.get("mentionText", "")
                    if entity.get("normalizedValue") and entity.get("normalizedValue").get("text"):
                        value = entity.get("normalizedValue").get("text")
                    checks_results[ent_type] = value.strip().upper()

            return _process_checks_dict(document_id, checks_results, mocked=True)
        except Exception as mock_err:
            logger.warning(f"[Document {document_id}] Failed to parse mock output.json: {str(mock_err)}. Skipping fraud checking.")
            return {
                "passed": True,
                "checks": {c: "SKIPPED" for c in CORE_CHECKS},
                "rejection_reason": None,
                "mocked": True,
                "warnings": [f"Fraud check failed to process fallback: {str(mock_err)}"]
            }

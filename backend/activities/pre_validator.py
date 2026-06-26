import os
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.file_handler import get_file_as_base64
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

# MIME type map by extension
MIME_MAP = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
}

# DOCX files have no visual representation — auto-pass with a note
DOCX_AUTO_PASS = {
    "passed": True,
    "rejection_reason": None,
    "warnings": ["DOCX file — visual quality checks skipped (not applicable to text documents)"],
    "checks": {},
}


def _parse_json_response(raw_text: str) -> dict:
    """Parse JSON from agent response, stripping markdown fences if present."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove opening fence (e.g. ```json or ```)
        cleaned = "\n".join(lines[1:])
    if cleaned.endswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[:-1])
    return json.loads(cleaned.strip())


def _extract_response_text(response) -> str:
    """Extract the assistant text from a conversations response."""
    raw_text = ""
    for entry in (response.outputs or []):
        if hasattr(entry, "content") and entry.content:
            raw_text = entry.content
            break
        if hasattr(entry, "text") and entry.text:
            raw_text = entry.text
            break
    return raw_text


@workflows.activity()
async def pre_validator_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2 — Pre-Validation.

    Sends the file directly to a Mistral Vision agent (no tools, no conversion).
    Checks: blur, brightness, skew, readability, watermark (warning only), orientation.

    DOCX files are auto-passed without an API call.
    Images are sent via image_url content blocks.
    PDFs are sent via document_url content blocks (full file, all pages).

    Returns:
        {
            "passed": bool,
            "rejection_reason": str | None,
            "warnings": [str],
            "checks": {
                "blur":        {"passed": bool, "severity": str, "message": str},
                "brightness":  {"passed": bool, "severity": str, "message": str},
                "skew":        {"passed": bool, "severity": str, "message": str},
                "readability": {"passed": bool, "severity": str, "message": str},
                "watermark":   {"passed": bool, "severity": str, "message": str},
                "orientation": {"passed": bool, "severity": str, "message": str},
            }
        }
    """
    try:
        logger.info(f"[Document {document_id}] Starting pre-validation activity")

        ext = os.path.splitext(file_path.lower())[1]

        # DOCX: no visual representation — skip checks and auto-pass
        if ext == ".docx":
            logger.info(f"[Document {document_id}] DOCX detected — auto-passing pre-validation")
            return DOCX_AUTO_PASS

        mime_type = MIME_MAP.get(ext)
        if not mime_type:
            logger.warning(f"[Document {document_id}] Unknown extension '{ext}' — auto-passing pre-validation")
            return {
                "passed": True,
                "rejection_reason": None,
                "warnings": [f"Unknown file type '{ext}' — visual checks skipped"],
                "checks": {},
            }

        # Encode file as base64 data URL
        logger.info(f"[Document {document_id}] Encoding file as base64 (mime: {mime_type})")
        b64 = get_file_as_base64(file_path)
        data_url = f"data:{mime_type};base64,{b64}"

        # Build the correct content block for this file type
        if mime_type == "application/pdf":
            # PDFs: document_url block — full file sent, agent sees all pages
            file_content_block = {
                "type": "document_url",
                "document_url": {"url": data_url},
            }
        else:
            # Images: image_url block
            file_content_block = {
                "type": "image_url",
                "image_url": {"url": data_url},
            }

        inputs = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this document and return your quality assessment as JSON. "
                            "Check for blur, brightness, skew, readability, watermark, and orientation."
                        ),
                    },
                    file_content_block,
                ],
            }
        ]

        logger.info(f"[Document {document_id}] Calling Pre-Validator Agent ({settings.PRE_VALIDATOR_AGENT_ID})")
        response = await client.beta.conversations.start_async(
            agent_id=settings.PRE_VALIDATOR_AGENT_ID,
            inputs=inputs,
        )

        raw_text = _extract_response_text(response)
        if not raw_text:
            raise ValueError("Pre-Validator Agent returned an empty response")

        result = _parse_json_response(raw_text)
        logger.info(
            f"[Document {document_id}] Pre-validation result: "
            f"passed={result.get('passed')}, warnings={result.get('warnings', [])}"
        )
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Pre-validation failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "pre_validator"})
        raise

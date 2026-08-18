import os
import io
import json
import base64
import logging
import mistralai.workflows as workflows
from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
from tools.classifier import get_supported_doc_types, get_document_text
import db.operations as db

logger = logging.getLogger(__name__)
client = get_mistral_client()


# ─── MIME TYPE MAPPING ───
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

# Extensions treated as non-visual (cannot be sent as image to the vision model)
NON_VISUAL_EXTENSIONS = {".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls"}


def _extract_text(content) -> str:
    """Safely extract text from various Mistral response content formats."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif hasattr(chunk, "text") and chunk.text:
                parts.append(chunk.text)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _prepare_pdf_base64(file_path: str, document_id: str, max_pages: int = 2) -> str:
    """
    Read a PDF, trim it to `max_pages` if it has more, and return
    the resulting PDF as a base64-encoded string.
    """
    import pypdf

    reader = pypdf.PdfReader(file_path)
    total_pages = len(reader.pages)

    if total_pages <= max_pages:
        # Small PDF — send the whole file as-is
        logger.info(f"[Document {document_id}] PDF has {total_pages} page(s), sending full document")
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # Multi-page PDF — extract only the first `max_pages`
    logger.info(f"[Document {document_id}] PDF has {total_pages} pages, trimming to first {max_pages}")
    writer = pypdf.PdfWriter()
    for i in range(max_pages):
        writer.add_page(reader.pages[i])

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _build_vision_content_block(file_path: str, document_id: str) -> dict | None:
    """
    Build the multimodal content block for the Mistral API message.
    Returns an image_url or document_url block, or None for non-visual files.
    """
    _, ext = os.path.splitext(file_path.lower())

    if ext in NON_VISUAL_EXTENSIONS:
        return None

    mime_type = MIME_TYPES.get(ext)
    if not mime_type:
        logger.warning(f"[Document {document_id}] Unknown extension '{ext}', attempting as image")
        mime_type = "image/jpeg"

    if ext == ".pdf":
        b64_data = _prepare_pdf_base64(file_path, document_id)
        data_url = f"data:{mime_type};base64,{b64_data}"
        return {
            "type": "document_url",
            "document_url": data_url,
        }
    else:
        with open(file_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_data}"
        return {
            "type": "image_url",
            "image_url": {"url": data_url},
        }


@workflows.activity()
async def classifier_activity(document_id: str, file_path: str) -> dict:
    """
    Step 3 — Classification (Vision-First).

    Sends the document visually (image or first 2 PDF pages) to the
    Classifier Agent with a list of supported types. The agent classifies
    the document in a single call — no OCR, no tool calls.

    For non-visual files (DOCX, etc.), falls back to OCR-based text classification.
    """
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity (vision mode)")

        if not settings.CLASSIFIER_AGENT_ID:
            raise ValueError("CLASSIFIER_AGENT_ID is not configured in settings/environment.")

        # Load supported document types
        types_map = get_supported_doc_types()
        allowed_types = list(types_map.values()) + ["Others"]
        types_list_str = ", ".join(allowed_types)

        # Try to build a vision content block
        vision_block = _build_vision_content_block(file_path, document_id)

        if vision_block:
            # ── VISION PATH: Send document visually ──
            logger.info(f"[Document {document_id}] Using vision-based classification")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Classify the following document into one of these supported types: "
                                f"[{types_list_str}]. "
                                f"Analyze the visual layout, text, logos, structure, and formatting. "
                                f"Return your classification as a JSON object with doc_type, confidence, and reasoning."
                            ),
                        },
                        vision_block,
                    ],
                }
            ]
        else:
            # ── TEXT FALLBACK: Non-visual file (DOCX, etc.) — use OCR ──
            logger.info(f"[Document {document_id}] Non-visual file detected, falling back to OCR text classification")
            raw_text = get_document_text(file_path, document_id)

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Classify the following document into one of these supported types: "
                        f"[{types_list_str}]. "
                        f"Analyze the text content and determine the document category. "
                        f"Return your classification as a JSON object with doc_type, confidence, and reasoning.\n\n"
                        f"--- DOCUMENT TEXT ---\n{raw_text}"
                    ),
                }
            ]

        # Single API call to the Classifier Agent — no tools
        logger.info(f"[Document {document_id}] Calling Classifier Agent ({settings.CLASSIFIER_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.CLASSIFIER_AGENT_ID,
            messages=messages,
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message
        content = _extract_text(message.content).strip()

        # Parse JSON response
        parsed = json.loads(content)

        doc_type_returned = parsed.get("doc_type", "Others").strip()

        # Match returned type back to the formal snake_case key
        matched_doc_type = "others"
        for key, display_name in types_map.items():
            if doc_type_returned.lower() in [key.lower(), display_name.lower(), key.replace("_", " ").lower()]:
                matched_doc_type = key
                break

        result = {
            "doc_type": matched_doc_type,
            "confidence": parsed.get("confidence", 0.0),
            "reasoning": parsed.get("reasoning", ""),
        }

        logger.info(f"[Document {document_id}] Classification result: {result}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Classifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "classifier"})
        raise

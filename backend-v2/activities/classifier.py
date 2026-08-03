"""
Classifier Activity
====================
Classifies a document into one of the supported document types.

Vision-first: the document itself (image, or the first 2 pages of a PDF) is sent
to the LLM alongside the list of supported types, and classified in a single
call — no OCR round-trip, no tool calls. Non-visual files (DOCX, spreadsheets)
fall back to OCR text classification.

Runs through the provider-agnostic ProviderRegistry + PromptManager; the system
prompt lives in platform_core/prompts/classifier.md.
"""

import os
import io
import base64
import logging
import db.operations as db
from tools.classifier import get_supported_doc_types, get_document_text
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import _parse_json_response

logger = logging.getLogger(__name__)
prompts = PromptManager()


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

# Extensions treated as non-visual (cannot be sent as an image to the vision model)
NON_VISUAL_EXTENSIONS = {".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls"}


def _prepare_pdf_base64(file_path: str, document_id: str, max_pages: int = 2) -> str:
    """
    Read a PDF, trim it to `max_pages` if it has more, and return
    the resulting PDF as a base64-encoded string.
    """
    import pypdf

    reader = pypdf.PdfReader(file_path)
    total_pages = len(reader.pages)

    if total_pages <= max_pages:
        logger.info(f"[Document {document_id}] PDF has {total_pages} page(s), sending full document")
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

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
    Build the multimodal content block for the LLM message.
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
        return {
            "type": "document_url",
            "document_url": f"data:{mime_type};base64,{b64_data}",
        }

    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
    }


async def classifier_activity(document_id: str, file_path: str) -> dict:
    """
    Step 3 — Classification (vision-first).

    Sends the document visually to the LLM with the list of supported types and
    classifies it in a single call. Falls back to OCR text for non-visual files.
    """
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity (vision mode)")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("classifier")

        types_map = get_supported_doc_types()
        allowed_types = list(types_map.values()) + ["Others"]
        types_list_str = ", ".join(allowed_types)

        vision_block = _build_vision_content_block(file_path, document_id)

        if vision_block:
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
            logger.info(f"[Document {document_id}] Non-visual file detected, falling back to OCR text classification")
            raw_text = await get_document_text(file_path, document_id)
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

        # Single call — no tools
        response = await llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        parsed = _parse_json_response(response.content)

        doc_type_returned = parsed.get("doc_type", "Others").strip()

        # Match returned type back to the formal snake_case key, or default to Others
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

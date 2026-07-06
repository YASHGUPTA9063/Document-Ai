import os
import json
import logging
from config import settings
from utils.ocr import extract_with_ocr

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
CLASSIFIER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_supported_document_types",
            "description": "Gets the list of currently supported document templates and types in the system.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_text",
            "description": "Extracts the raw text content of the document using OCR. For PDFs, it restricts OCR to the first two pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path of the document to run OCR on."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def get_supported_doc_types() -> dict:
    types_map = {}
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if os.path.exists(templates_path):
        try:
            with open(templates_path, "r") as f:
                templates = json.load(f)
                for key in templates.keys():
                    normalized_key = key.lower().replace(" ", "_")
                    display_name = " ".join(word.capitalize() for word in normalized_key.split("_"))
                    types_map[normalized_key] = display_name
        except Exception as e:
            logger.error(f"Failed to read templates in classifier: {e}")
    return types_map


def get_document_text(file_path: str, document_id: str) -> str:
    _, ext = os.path.splitext(file_path.lower())
    pages = None
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            total_pages = len(reader.pages)
            if total_pages >= 2:
                pages = [0, 1]
                logger.info(f"[Document {document_id}] Restricting classification OCR to pages 1 and 2.")
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to count PDF pages: {e}")
            pages = [0, 1]

    ocr_result = extract_with_ocr(file_path, "unknown", pages=pages)
    return ocr_result.get("raw_text", "")

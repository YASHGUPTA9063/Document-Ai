import os
import json
import logging
from config import settings
from utils.ocr import extract_with_ocr
from utils.classification_config import load_classification_config

logger = logging.getLogger(__name__)

# ─── TOOL FUNCTIONS ───
def get_supported_doc_types() -> dict:
    types_map = {}
    try:
        doc_types = load_classification_config()
        for key in doc_types:
            normalized_key = key.lower().replace(" ", "_")
            display_name = " ".join(word.capitalize() for word in normalized_key.split("_"))
            types_map[normalized_key] = display_name
    except Exception as e:
        logger.error(f"Failed to load classification config in classifier tool: {e}")
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

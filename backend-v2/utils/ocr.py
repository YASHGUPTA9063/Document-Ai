import os
import json
import logging
from config import settings
from utils.file_handler import get_file_as_base64
import docx
from platform_core.registry import ProviderRegistry

logger = logging.getLogger(__name__)

async def extract_with_ocr(
    file_path: str, 
    doc_type: str, 
    pages: list = None,
    document_annotation_format: dict = None,
    document_annotation_prompt: str = None
) -> dict:
    """
    Extract text using ProviderRegistry OCR or python-docx for DOCX files.
    Supports structured document annotation via document_annotation_format/prompt.
    Returns: {"raw_text": str, "confidence": float, "pages": list, "document_annotation": dict, "blocks": list, ...}
    blocks: list of {page, content, type, top_left_x, top_left_y, bottom_right_x, bottom_right_y, page_width, page_height}
    """
    _, ext = os.path.splitext(file_path.lower())

    if ext == ".docx":
        # Handle DOCX locally, no OCR needed
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return {
            "raw_text": "\n".join(full_text),
            "confidence": 1.0, # 100% confidence for direct text extraction
            "pages": [{"markdown": "\n".join(full_text)}],
            "document_annotation": None,
            "blocks": [],
            "word_confidence_scores": []
        }

    # Call ProviderRegistry OCR
    registry = ProviderRegistry.get()
    ocr = registry.get_ocr()

    kwargs = {}
    if document_annotation_format is not None:
        kwargs["document_annotation_format"] = document_annotation_format
    if document_annotation_prompt is not None:
        kwargs["document_annotation_prompt"] = document_annotation_prompt

    logger.info(f"Calling OCR provider '{ocr.name}' with pages={pages}, annotated={document_annotation_format is not None}")
    
    ocr_response = await ocr.extract(
        file_path=file_path,
        pages=pages,
        include_blocks=True,
        **kwargs
    )

    return {
        "raw_text": ocr_response.raw_text,
        "confidence": ocr_response.confidence,
        "pages": ocr_response.pages,
        "word_confidence_scores": ocr_response.word_confidences,
        "document_annotation": ocr_response.document_annotation,
        "blocks": ocr_response.blocks,
    }

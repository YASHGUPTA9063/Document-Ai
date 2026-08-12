import os
import json
import logging
from mistralai.client import Mistral
from config import settings
from utils.file_handler import get_file_as_base64
import docx
import pypdf

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

# Tables in page.markdown are rendered as markdown pipe tables (the API also
# supports "html"). Markdown keeps the OCR text one consistent format for the
# downstream chat extraction prompts.
TABLE_FORMAT = "markdown"

# Document annotation is always requested as JSON, never plain text.
JSON_OBJECT_FORMAT = {"type": "json_object"}

# json_object mode requires the model to be told to emit JSON, so a prompt is
# always sent alongside the format.
DEFAULT_DOCUMENT_ANNOTATION_PROMPT = (
    "Extract the useful information from this document and return it as a single JSON object."
)


def _as_json_annotation_format(document_annotation_format: dict = None) -> dict:
    """
    Coerce a caller-supplied annotation format into a JSON ResponseFormat.

    Accepts None (-> json_object), a bare JSON Schema (-> wrapped as json_schema),
    or an already-built ResponseFormat dict. A "text" type is upgraded to
    json_object so the annotation is never returned as free text.
    """
    if not document_annotation_format:
        return dict(JSON_OBJECT_FORMAT)

    fmt_type = document_annotation_format.get("type")

    # A bare JSON Schema (no ResponseFormat wrapper) — wrap it.
    if "json_schema" not in document_annotation_format and fmt_type not in ("json_object", "json_schema", "text"):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "document_annotation",
                "schema": document_annotation_format,
                "strict": True,
            },
        }

    if fmt_type == "json_schema" and document_annotation_format.get("json_schema"):
        return document_annotation_format

    return dict(JSON_OBJECT_FORMAT)


def extract_with_ocr(
    file_path: str,
    doc_type: str,
    pages: list = None,
    document_annotation_format: dict = None,
    document_annotation_prompt: str = None,
) -> dict:
    """
    Extract text using Mistral OCR or python-docx for DOCX files.
    Tables are returned as markdown (table_format="markdown").
    Structured document annotation is requested only when a caller passes
    document_annotation_format and/or document_annotation_prompt, and is always
    requested in a JSON format (json_object, or json_schema when a schema is given).
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
            "blocks": []  # DOCX has no spatial layout, citation not supported
        }

    # Determine mime type for base64 data URL
    mime_type = "application/pdf"
    if ext in [".jpeg", ".jpg"]:
        mime_type = "image/jpeg"
    elif ext == ".png":
        mime_type = "image/png"
    elif ext == ".webp":
        mime_type = "image/webp"
    
    base64_data = get_file_as_base64(file_path)
    document_url = f"data:{mime_type};base64,{base64_data}"
    
    # Calculate page range if PDF
    actual_pages = None
    if ext == ".pdf" and pages is not None:
        try:
            reader = pypdf.PdfReader(file_path)
            total_pages = len(reader.pages)
            # Limit page indexes to the actual pages in the PDF (0-indexed)
            actual_pages = [p for p in pages if 0 <= p < total_pages]
            if not actual_pages:
                actual_pages = [0]  # Fallback to the first page if range is empty
            logger.info(f"PDF page range restricted from {pages} to valid range: {actual_pages} (total pages: {total_pages})")
        except Exception as e:
            logger.error(f"Failed to extract page count from PDF: {e}")
            actual_pages = pages

    # Call Mistral OCR
    ocr_args = {
        "model": "mistral-ocr-latest",
        "document": {
            "type": "document_url",
            "document_url": document_url
        },
        "confidence_scores_granularity": "word",
        # Render tables in page.markdown as markdown instead of HTML.
        "table_format": TABLE_FORMAT,
        # include_blocks returns paragraph-level bounding boxes for citation highlighting.
        # Only effective for image/PDF files — DOCX is handled above before this point.
        "include_blocks": True
    }

    if actual_pages is not None:
        ocr_args["pages"] = actual_pages

    # Annotation is opt-in per call, but whenever it is requested the format is JSON.
    annotate = document_annotation_format is not None or document_annotation_prompt is not None
    if annotate:
        ocr_args["document_annotation_format"] = _as_json_annotation_format(document_annotation_format)
        ocr_args["document_annotation_prompt"] = document_annotation_prompt or DEFAULT_DOCUMENT_ANNOTATION_PROMPT

    logger.info(
        f"Calling Mistral OCR: model={ocr_args['model']}, pages={ocr_args.get('pages')}, "
        f"table_format={TABLE_FORMAT}, annotated={annotate}"
    )
    ocr_response = client.ocr.process(**ocr_args)

    # Parse response
    raw_text = ""
    pages_list = []
    total_confidence = 0.0
    valid_pages_count = 0
    all_word_confidences = []
    all_blocks = []  # bounding box blocks for citation highlighting

    for page in ocr_response.pages:
        page_index = getattr(page, "index", 0)
        raw_text += page.markdown + "\n\n"
        pages_list.append({
            "markdown": page.markdown,
            "index": page_index
        })
        # Extract confidence score if available
        if hasattr(page, "confidence_scores") and page.confidence_scores:
            if hasattr(page.confidence_scores, "average_page_confidence_score"):
                total_confidence += page.confidence_scores.average_page_confidence_score
                valid_pages_count += 1
            if getattr(page.confidence_scores, "word_confidence_scores", None):
                for w in page.confidence_scores.word_confidence_scores:
                    all_word_confidences.append({
                        "text": w.text,
                        "confidence": w.confidence,
                        "start_index": w.start_index
                    })
        # Extract bounding box blocks for citation highlighting
        # Confirmed field names from live API: top_left_x/y, bottom_right_x/y, content, type
        dims = getattr(page, "dimensions", None)
        page_w = getattr(dims, "width", None)
        page_h = getattr(dims, "height", None)
        for block in getattr(page, "blocks", []) or []:
            b_type = getattr(block, "type", "text")
            if b_type == "image":
                continue  # skip image placeholder blocks — they have no readable text
            top_left_x     = getattr(block, "top_left_x", None)
            top_left_y     = getattr(block, "top_left_y", None)
            bottom_right_x = getattr(block, "bottom_right_x", None)
            bottom_right_y = getattr(block, "bottom_right_y", None)
            content        = getattr(block, "content", "") or ""
            if top_left_x is None or bottom_right_x is None:
                continue  # block has no spatial data, skip
            all_blocks.append({
                "page":           page_index,
                "content":        content,
                "type":           b_type,
                "top_left_x":     top_left_x,
                "top_left_y":     top_left_y,
                "bottom_right_x": bottom_right_x,
                "bottom_right_y": bottom_right_y,
                "page_width":     page_w,
                "page_height":    page_h,
            })
    
    avg_confidence = (total_confidence / valid_pages_count) if valid_pages_count > 0 else 0.0

    # document_annotation comes back as a JSON string — parse it to a dict.
    document_annotation = None
    raw_annotation = getattr(ocr_response, "document_annotation", None)
    if raw_annotation:
        if isinstance(raw_annotation, str):
            try:
                document_annotation = json.loads(raw_annotation)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse document_annotation as JSON: {e}")
                document_annotation = raw_annotation
        elif hasattr(raw_annotation, "model_dump"):
            document_annotation = raw_annotation.model_dump()
        else:
            document_annotation = raw_annotation

    return {
        "raw_text": raw_text.strip(),
        "confidence": avg_confidence,
        "pages": pages_list,
        "word_confidence_scores": all_word_confidences,
        "blocks": all_blocks,  # bounding box blocks for field citation highlighting
        "document_annotation": document_annotation,
    }

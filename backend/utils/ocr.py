import os
import logging
from mistralai.client import Mistral
from config import settings
from utils.file_handler import get_file_as_base64
import docx
import pypdf

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

def extract_with_ocr(
    file_path: str, 
    doc_type: str, 
    pages: list = None,
    document_annotation_format: dict = None,
    document_annotation_prompt: str = None
) -> dict:
    """
    Extract text using Mistral OCR or python-docx for DOCX files.
    Supports structured document annotation via document_annotation_format/prompt.
    Returns: {"raw_text": str, "confidence": float, "pages": list, "document_annotation": dict, ...}
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
            "document_annotation": None
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
        "confidence_scores_granularity": "word"
    }
    
    if actual_pages is not None:
        ocr_args["pages"] = actual_pages
    if document_annotation_format is not None:
        ocr_args["document_annotation_format"] = document_annotation_format
    if document_annotation_prompt is not None:
        ocr_args["document_annotation_prompt"] = document_annotation_prompt

    logger.info(f"Calling Mistral OCR with args: model={ocr_args['model']}, pages={ocr_args.get('pages')}, annotated={document_annotation_format is not None}")
    ocr_response = client.ocr.process(**ocr_args)

    # Parse response
    raw_text = ""
    pages_list = []
    total_confidence = 0.0
    valid_pages_count = 0
    all_word_confidences = []

    for page in ocr_response.pages:
        raw_text += page.markdown + "\n\n"
        pages_list.append({
            "markdown": page.markdown,
            "index": getattr(page, "index", 0)
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
    
    avg_confidence = (total_confidence / valid_pages_count) if valid_pages_count > 0 else 0.0
    
    # Extract document annotation if present
    document_annotation = None
    if hasattr(ocr_response, "document_annotation") and ocr_response.document_annotation:
        annotation = ocr_response.document_annotation
        if isinstance(annotation, str):
            try:
                document_annotation = json.loads(annotation)
            except Exception:
                document_annotation = annotation
        elif hasattr(annotation, "to_dict"):
            document_annotation = annotation.to_dict()
        elif hasattr(annotation, "model_dump"):
            document_annotation = annotation.model_dump()
        else:
            document_annotation = annotation
            
    return {
        "raw_text": raw_text.strip(),
        "confidence": avg_confidence,
        "pages": pages_list,
        "word_confidence_scores": all_word_confidences,
        "document_annotation": document_annotation
    }

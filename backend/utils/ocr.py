import os
from mistralai.client import Mistral
from config import settings
from utils.file_handler import get_file_as_base64
import docx

client = Mistral(api_key=settings.MISTRAL_API_KEY)

def extract_with_ocr(file_path: str, doc_type: str) -> dict:
    """
    Extract text using Mistral OCR or python-docx for DOCX files.
    Returns: {"raw_text": str, "confidence": float, "pages": list}
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
            "pages": [{"markdown": "\n".join(full_text)}]
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
    
    # Call Mistral OCR (synchronously, since Mistral SDK sync client is easier to use here,
    # though it will be called from an async activity. The Mistral SDK uses httpx under the hood)
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": document_url
        },
        confidence_scores_granularity="word"
    )

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
    
    return {
        "raw_text": raw_text.strip(),
        "confidence": avg_confidence,
        "pages": pages_list,
        "word_confidence_scores": all_word_confidences
    }

import os
import json
import logging
import base64
import re
import fitz  # PyMuPDF
from mistralai.client import Mistral
from config import settings
from tools.extractor import get_template_fields, get_template_metadata
from utils.file_handler import get_file_as_base64

logger = logging.getLogger(__name__)


def _pdf_pages_to_images(file_path: str) -> list[str]:
    """Convert each page of a PDF into high-resolution base64 JPEG data using PyMuPDF (fitz)."""
    doc = fitz.open(file_path)
    pages_b64 = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("jpeg")
        pages_b64.append(base64.b64encode(img_bytes).decode("utf-8"))
    doc.close()
    return pages_b64


def _get_required_fields_needing_fallback(
    doc_type: str,
    normalized_extracted: dict,
    field_confidences: dict,
    threshold: float,
    trigger_on_missing: bool = True,
    trigger_on_low_confidence: bool = True
) -> list[dict]:
    """
    Identify template fields marked as 'required' that are either:
    1. Missing / null / empty in the extracted data
    2. Have a confidence score below the threshold

    Returns a list of field definitions that need vLLM re-extraction.
    """
    template_fields = get_template_fields(doc_type)
    if not template_fields or not isinstance(template_fields, list):
        return []

    fallback_fields = []
    threshold_decimal = threshold / 100.0  # Convert percentage to decimal

    for field in template_fields:
        if not isinstance(field, dict):
            continue
        if not field.get("required", False):
            continue

        key = field.get("key", "")
        if not key:
            continue

        # Skip image/binary fields — these can't be re-extracted via text VLM
        field_type = field.get("type", "Text").lower()
        if field_type in ("image",):
            continue

        value = normalized_extracted.get(key)
        confidence = field_confidences.get(key)

        # Check if field is missing or empty
        is_missing = False
        if value is None:
            is_missing = True
        elif isinstance(value, str):
            trimmed = value.strip().lower()
            if trimmed in ("", "null", "none", "n/a", "—", "-"):
                is_missing = True
        elif isinstance(value, (list, dict)) and len(value) == 0:
            is_missing = True

        # Check if confidence is below threshold
        is_low_confidence = False
        if confidence is not None:
            if isinstance(confidence, (int, float)):
                is_low_confidence = confidence < threshold_decimal
            elif isinstance(confidence, dict):
                # For nested confidence (e.g., objects), use average
                flat_values = []
                _flatten_confidence(confidence, flat_values)
                if flat_values:
                    avg = sum(flat_values) / len(flat_values)
                    is_low_confidence = avg < threshold_decimal

        should_fallback = (
            (trigger_on_missing and is_missing) or
            (trigger_on_low_confidence and is_low_confidence)
        )
        if should_fallback:
            fallback_fields.append(field)

    return fallback_fields


def _flatten_confidence(obj, result: list):
    """Recursively flatten a nested confidence structure into a list of floats."""
    if isinstance(obj, (int, float)):
        result.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_confidence(v, result)
    elif isinstance(obj, list):
        for item in obj:
            _flatten_confidence(item, result)


def vllm_reextract_required_fields(
    file_path: str,
    doc_type: str,
    document_id: str,
    normalized_extracted: dict,
    field_confidences: dict,
    threshold: float,
    trigger_on_missing: bool = True,
    trigger_on_low_confidence: bool = True
) -> dict:
    """
    Re-extract required fields that are missing or have low confidence using Mistral VLM.

    Args:
        file_path: Path to the document file
        doc_type: Classified document type
        document_id: Document ID for logging
        normalized_extracted: Current extracted field values
        field_confidences: Current field confidence scores
        threshold: Confidence threshold percentage (0-100)

    Returns:
        Dict mapping field_key -> {"value": ..., "confidence": ..., "source": "vllm", "reason": ...}
    """
    fallback_fields = _get_required_fields_needing_fallback(
        doc_type, normalized_extracted, field_confidences, threshold,
        trigger_on_missing=trigger_on_missing,
        trigger_on_low_confidence=trigger_on_low_confidence
    )

    if not fallback_fields:
        logger.info(f"[Document {document_id}] No required fields need vLLM fallback re-extraction")
        return {}

    field_keys = [f["key"] for f in fallback_fields]
    logger.info(
        f"[Document {document_id}] vLLM fallback triggered for {len(fallback_fields)} required fields: {field_keys}"
    )

    # Prepare document images
    _, ext = os.path.splitext(file_path.lower())
    page_images_b64 = []

    if ext == ".pdf":
        try:
            page_images_b64 = _pdf_pages_to_images(file_path)
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to rasterize PDF for vLLM fallback: {e}")
            return {}
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        try:
            page_images_b64 = [get_file_as_base64(file_path)]
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to load image for vLLM fallback: {e}")
            return {}
    else:
        logger.warning(f"[Document {document_id}] Unsupported file format for vLLM fallback: {ext}")
        return {}

    # Build field instructions
    field_instructions = []
    for f in fallback_fields:
        current_val = normalized_extracted.get(f["key"])
        current_conf = field_confidences.get(f["key"])

        reason = "missing/empty"
        if current_val is not None and str(current_val).strip().lower() not in ("", "null", "none", "n/a", "—", "-"):
            conf_pct = ""
            if isinstance(current_conf, (int, float)):
                conf_pct = f" (current confidence: {round(current_conf * 100)}%)"
            reason = f"low confidence{conf_pct}"

        field_instructions.append(
            f"- key: '{f['key']}' ({f.get('type', 'Text')}): {f.get('description', '')} "
            f"[Reason for re-extraction: {reason}]"
        )

    fields_text = "\n".join(field_instructions)

    prompt = (
        f"You are a document extraction expert performing a careful re-extraction pass.\n\n"
        f"CONTEXT:\n"
        f"The following fields from a '{doc_type}' document were either not detected or had low confidence "
        f"during the initial OCR extraction. These are all REQUIRED fields that must have values.\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Carefully examine the provided document image(s).\n"
        f"2. For each field listed below, locate the relevant information in the document.\n"
        f"3. Extract the value as accurately as possible.\n"
        f"4. Assign a confidence score (0.0 to 1.0) based on how certain you are about the extraction.\n"
        f"5. If a field truly cannot be found in the document, set its value to null with confidence 0.0.\n\n"
        f"Fields to re-extract:\n{fields_text}\n\n"
        f"Return ONLY a valid JSON object mapping each field key to an object with 'value' and 'confidence'.\n"
        f"Example:\n"
        f"{{\n"
        f'  "field_name": {{"value": "Extracted Text", "confidence": 0.92}}\n'
        f"}}\n"
    )

    # Build multimodal content
    content = []
    for b64 in page_images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
    content.append({"type": "text", "text": prompt})

    try:
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        logger.info(
            f"[Document {document_id}] Calling Mistral VLM (mistral-large-latest) "
            f"for vLLM fallback on {len(fallback_fields)} fields"
        )
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content

        # Parse the response
        try:
            result_json = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                result_json = json.loads(match.group(0))
            else:
                logger.error(f"[Document {document_id}] vLLM fallback returned non-JSON: {response_text[:200]}")
                return {}

        # Normalize and annotate results
        fallback_results = {}
        threshold_decimal = threshold / 100.0

        for field in fallback_fields:
            key = field["key"]
            if key in result_json and isinstance(result_json[key], dict):
                res = result_json[key]
                value = res.get("value")
                confidence = res.get("confidence", 0.0)

                # Determine reason
                current_val = normalized_extracted.get(key)
                current_conf = field_confidences.get(key)
                if current_val is None or (isinstance(current_val, str) and current_val.strip().lower() in ("", "null", "none", "n/a", "—", "-")):
                    reason = "missing"
                else:
                    reason = "low_confidence"

                fallback_results[key] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "vllm",
                    "reason": reason,
                    "original_value": current_val,
                    "original_confidence": current_conf if isinstance(current_conf, (int, float)) else None,
                }
                logger.info(
                    f"[Document {document_id}] vLLM fallback for '{key}': "
                    f"value='{value}', confidence={confidence}, reason={reason}"
                )

        return fallback_results

    except Exception as e:
        logger.error(f"[Document {document_id}] vLLM fallback extraction failed: {e}")
        return {}

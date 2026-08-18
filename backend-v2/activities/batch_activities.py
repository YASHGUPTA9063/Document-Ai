"""
activities/batch_activities.py
──────────────────────────────
Batch activities for multi-document processing using the Mistral Batch API.
Includes:
- batch_intake_activity
- batch_classify_activity (Vision-First direct multimodal, no OCR)
- batch_ocr_activity (Mistral /v1/ocr batch processing)
- batch_extract_activity (Structured extraction on /v1/chat/completions)
- batch_validate_and_save_activity (Confidence calculation, schema check, DB persistence)
"""
import os
import io
import json
import base64
import re
import logging
from typing import List, Dict, Any, Optional

import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.batch_client import MistralBatchHelper
from tools.classifier import get_supported_doc_types
from tools.extractor import get_template_fields, get_template_metadata, crop_kyc_images, _save_ocr_blocks
from utils.norm_config import build_normalization_rules_prompt
from tools.output import persist_final_extraction
import db.operations as db
from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData, ClaimDocumentLink
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

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


def _prepare_pdf_base64(file_path: str, max_pages: int = 2) -> str:
    """Read a PDF, trim to max_pages for classification vision analysis, and return base64."""
    import pypdf

    reader = pypdf.PdfReader(file_path)
    total_pages = len(reader.pages)

    if total_pages <= max_pages:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    writer = pypdf.PdfWriter()
    for i in range(max_pages):
        writer.add_page(reader.pages[i])

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _build_vision_block(file_path: str, max_pages: int = 2) -> Optional[dict]:
    """Builds a vision block (document_url or image_url) for multimodal chat completions."""
    _, ext = os.path.splitext(file_path.lower())
    mime_type = MIME_TYPES.get(ext, "image/jpeg")

    if not os.path.exists(file_path):
        return None

    if ext == ".pdf":
        b64_data = _prepare_pdf_base64(file_path, max_pages=max_pages)
        return {
            "type": "document_url",
            "document_url": f"data:{mime_type};base64,{b64_data}",
        }
    else:
        with open(file_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
        }


def _calculate_field_confidence(field_value: Any, word_confidence_scores: List[dict]) -> float:
    """Matches words in field_value with word-level OCR confidence scores."""
    if not isinstance(field_value, str):
        field_str = str(field_value).strip() if field_value is not None else ""
    else:
        field_str = field_value.strip()

    if not field_str:
        return 0.0

    field_words = re.findall(r"\b\w+\b", field_str.lower())
    if not field_words:
        return 1.0

    confidences = []
    for f_word in field_words:
        matches = [
            w["confidence"]
            for w in word_confidence_scores
            if w["text"].strip().lower() == f_word or f_word in w["text"].strip().lower()
        ]
        if matches:
            confidences.append(sum(matches) / len(matches))

    if confidences:
        return sum(confidences) / len(confidences)
    return 1.0


def _compute_confidences_recursive(data: Any, word_confidence_scores: List[dict]) -> Any:
    if isinstance(data, dict):
        return {k: _compute_confidences_recursive(v, word_confidence_scores) for k, v in data.items()}
    elif isinstance(data, list):
        return [_compute_confidences_recursive(item, word_confidence_scores) for item in data]
    else:
        return _calculate_field_confidence(data, word_confidence_scores)


def _normalize_rate_fields(normalized: dict, raw: dict) -> dict:
    if not isinstance(normalized, dict):
        return normalized
    res = dict(normalized)
    for k, v in res.items():
        if v is None:
            continue
        key_lower = k.lower()
        raw_val = raw.get(k) if isinstance(raw, dict) else None
        raw_has_pct = isinstance(raw_val, str) and "%" in raw_val
        is_rate_key = any(t in key_lower for t in ["rate", "percent", "pct", "withholding"])

        if (is_rate_key or raw_has_pct) and isinstance(v, (str, int, float)):
            val_str = str(v).strip()
            if val_str and not val_str.endswith("%") and val_str.lower() not in ("null", "none", "—"):
                res[k] = f"{val_str}%"
    return res


# ─── BATCH ACTIVITIES ─────────────────────────────────────────────────────────

@workflows.activity()
async def batch_intake_activity(documents: List[dict]) -> dict:
    """
    Step 1: Batch Intake.
    Validates documents, checks file existence, and marks DB status as batch_processing.
    """
    logger.info(f"Starting batch intake activity for {len(documents)} documents")
    valid_docs = []
    invalid_docs = []

    async with AsyncSessionLocal() as session:
        for doc_item in documents:
            doc_id = doc_item["document_id"]
            file_path = doc_item["file_path"]

            if not os.path.exists(file_path):
                logger.error(f"[Document {doc_id}] File not found at {file_path}")
                invalid_docs.append({"document_id": doc_id, "error": f"File not found: {file_path}"})
                continue

            result = await session.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "batch_processing"
            valid_docs.append(doc_item)

        await session.commit()

    logger.info(f"Batch intake completed: {len(valid_docs)} valid, {len(invalid_docs)} invalid")
    return {
        "valid_documents": valid_docs,
        "invalid_documents": invalid_docs
    }


@workflows.activity()
async def batch_classify_activity(documents: List[dict]) -> dict:
    """
    Step 2: Batch Classification (Vision-First, No OCR).
    Sends documents visually to mistral-large-latest via the Mistral Batch API.
    """
    logger.info(f"Starting batch classification for {len(documents)} documents")
    helper = MistralBatchHelper()

    types_map = get_supported_doc_types()
    allowed_types = list(types_map.values()) + ["Others"]
    types_list_str = ", ".join(allowed_types)

    requests_data = []
    doc_id_map = {}

    for doc in documents:
        doc_id = doc["document_id"]
        file_path = doc["file_path"]
        custom_id = f"cls_{doc_id}"
        doc_id_map[custom_id] = doc_id

        vision_block = _build_vision_block(file_path, max_pages=2)
        if not vision_block:
            logger.warning(f"[Document {doc_id}] Could not build vision block for {file_path}")
            continue

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
                            f"Return your classification as a JSON object matching this schema:\n"
                            f'{{"doc_type": "string", "confidence": float, "reasoning": "string"}}'
                        ),
                    },
                    vision_block,
                ],
            }
        ]

        requests_data.append({
            "custom_id": custom_id,
            "body": {
                "model": "mistral-large-latest",
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        })

    if not requests_data:
        return {}

    # Run Batch API Job for Classification
    batch_results = await helper.run_batch_pipeline(
        requests_data=requests_data,
        endpoint="/v1/chat/completions",
        model="mistral-large-latest",
        filename="batch_classification.jsonl"
    )

    classification_results = {}
    async with AsyncSessionLocal() as session:
        for custom_id, res in batch_results.items():
            doc_id = doc_id_map.get(custom_id)
            if not doc_id:
                continue

            body = res.get("body", {})
            choices = body.get("choices", [])
            matched_doc_type = "others"
            confidence = 0.0
            reasoning = ""

            if choices:
                content_str = choices[0].get("message", {}).get("content", "{}")
                try:
                    parsed = json.loads(content_str)
                    doc_type_raw = parsed.get("doc_type", "Others").strip()
                    confidence = float(parsed.get("confidence", 0.0))
                    reasoning = parsed.get("reasoning", "")

                    for key, display_name in types_map.items():
                        if doc_type_raw.lower() in [key.lower(), display_name.lower(), key.replace("_", " ").lower()]:
                            matched_doc_type = key
                            break
                except Exception as parse_err:
                    logger.error(f"[Document {doc_id}] Failed to parse classification JSON: {parse_err}")

            classification_results[doc_id] = {
                "doc_type": matched_doc_type,
                "confidence": confidence,
                "reasoning": reasoning
            }

            # Update Document doc_type in DB
            result = await session.execute(select(Document).where(Document.id == doc_id))
            db_doc = result.scalar_one_or_none()
            if db_doc:
                db_doc.doc_type = matched_doc_type

        await session.commit()

    logger.info(f"Batch classification completed for {len(classification_results)} documents")
    return classification_results


@workflows.activity()
async def batch_ocr_activity(documents: List[dict]) -> dict:
    """
    Step 3: Batch OCR (Only for Extraction).
    Executes Mistral OCR on /v1/ocr across all documents in batch.
    """
    logger.info(f"Starting batch OCR for {len(documents)} documents")
    helper = MistralBatchHelper()

    requests_data = []
    doc_id_map = {}

    for doc in documents:
        doc_id = doc["document_id"]
        file_path = doc["file_path"]
        custom_id = f"ocr_{doc_id}"
        doc_id_map[custom_id] = doc_id

        _, ext = os.path.splitext(file_path.lower())
        mime_type = MIME_TYPES.get(ext, "application/pdf")

        with open(file_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        document_url = f"data:{mime_type};base64,{b64_data}"

        requests_data.append({
            "custom_id": custom_id,
            "body": {
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "document_url",
                    "document_url": document_url
                },
                "include_blocks": True,
                "table_format": "markdown",
                "confidence_scores_granularity": "word"
            }
        })

    if not requests_data:
        return {}

    # Run Batch API Job for OCR
    batch_results = await helper.run_batch_pipeline(
        requests_data=requests_data,
        endpoint="/v1/ocr",
        model="mistral-ocr-latest",
        filename="batch_ocr.jsonl"
    )

    ocr_results = {}
    for custom_id, res in batch_results.items():
        doc_id = doc_id_map.get(custom_id)
        if not doc_id:
            continue

        body = res.get("body", {})
        pages = body.get("pages", [])

        raw_text = ""
        pages_list = []
        total_confidence = 0.0
        valid_pages_count = 0
        all_word_confidences = []
        all_blocks = []

        for page in pages:
            page_index = page.get("index", 0)
            page_md = page.get("markdown", "")
            raw_text += page_md + "\n\n"
            pages_list.append({"markdown": page_md, "index": page_index})

            conf_scores = page.get("confidence_scores", {})
            if conf_scores:
                avg_score = conf_scores.get("average_page_confidence_score")
                if avg_score is not None:
                    total_confidence += avg_score
                    valid_pages_count += 1
                for w in conf_scores.get("word_confidence_scores", []):
                    all_word_confidences.append({
                        "text": w.get("text", ""),
                        "confidence": w.get("confidence", 1.0),
                        "start_index": w.get("start_index", 0)
                    })

            dims = page.get("dimensions", {})
            page_w = dims.get("width")
            page_h = dims.get("height")

            for block in page.get("blocks", []):
                b_type = block.get("type", "text")
                if b_type == "image":
                    continue
                top_left_x = block.get("top_left_x")
                top_left_y = block.get("top_left_y")
                bottom_right_x = block.get("bottom_right_x")
                bottom_right_y = block.get("bottom_right_y")
                content = block.get("content", "")

                if top_left_x is not None and bottom_right_x is not None:
                    all_blocks.append({
                        "page": page_index,
                        "content": content,
                        "type": b_type,
                        "top_left_x": top_left_x,
                        "top_left_y": top_left_y,
                        "bottom_right_x": bottom_right_x,
                        "bottom_right_y": bottom_right_y,
                        "page_width": page_w,
                        "page_height": page_h,
                    })

        avg_conf = (total_confidence / valid_pages_count) if valid_pages_count > 0 else 0.95

        ocr_results[doc_id] = {
            "raw_text": raw_text,
            "pages": pages_list,
            "blocks": all_blocks,
            "word_confidences": all_word_confidences,
            "confidence": avg_conf
        }

    logger.info(f"Batch OCR completed for {len(ocr_results)} documents")
    return ocr_results


@workflows.activity()
async def batch_extract_activity(
    documents: List[dict],
    classification_results: dict,
    ocr_results: dict
) -> dict:
    """
    Step 4: Batch Structured Field Extraction.
    Uses OCR markdown + doc_type template rules in mistral-large-latest via Batch API.
    """
    logger.info(f"Starting batch extraction for {len(documents)} documents")
    helper = MistralBatchHelper()

    normalization_rules = build_normalization_rules_prompt()
    requests_data = []
    doc_id_map = {}

    for doc in documents:
        doc_id = doc["document_id"]
        custom_id = f"ext_{doc_id}"
        doc_id_map[custom_id] = doc_id

        doc_type = classification_results.get(doc_id, {}).get("doc_type", "others")
        ocr_data = ocr_results.get(doc_id, {})
        raw_ocr_text = ocr_data.get("raw_text", "")

        fields_schema = get_template_fields(doc_type)
        template_meta = get_template_metadata(doc_type)

        prompt = (
            f"You are the Extractor Agent. Extract structured data from the OCR text of a document classified as '{doc_type}'.\n\n"
            f"--- OCR TEXT ---\n{raw_ocr_text}\n\n"
            f"Apply these standard normalization rules to the extracted fields:\n"
            f"{normalization_rules}\n\n"
        )
        if fields_schema:
            prompt += f"Target Schema Fields:\n{json.dumps(fields_schema, indent=2)}\n\n"
        else:
            prompt += (
                f"No predefined template exists for '{doc_type}'. Read the full OCR text and identify all relevant "
                f"keys, values, and tables, and extract them into the raw_extracted and normalized_extracted dictionaries.\n\n"
            )

        prompt += (
            f"Output a JSON response matching exactly this schema:\n"
            f'{{\n  "raw_extracted": dict,\n  "normalized_extracted": dict\n}}'
        )

        messages = [
            {"role": "system", "content": "You are an expert data extraction assistant. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        requests_data.append({
            "custom_id": custom_id,
            "body": {
                "model": "mistral-large-latest",
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        })

    if not requests_data:
        return {}

    # Run Batch API Job for Extraction
    batch_results = await helper.run_batch_pipeline(
        requests_data=requests_data,
        endpoint="/v1/chat/completions",
        model="mistral-large-latest",
        filename="batch_extraction.jsonl"
    )

    extraction_results = {}
    for custom_id, res in batch_results.items():
        doc_id = doc_id_map.get(custom_id)
        if not doc_id:
            continue

        body = res.get("body", {})
        choices = body.get("choices", [])
        raw_extracted = {}
        normalized_extracted = {}

        if choices:
            content_str = choices[0].get("message", {}).get("content", "{}")
            try:
                parsed = json.loads(content_str)
                raw_extracted = parsed.get("raw_extracted", {})
                normalized_extracted = parsed.get("normalized_extracted", {})
            except Exception as e:
                logger.error(f"[Document {doc_id}] Failed to parse extraction JSON: {e}")

        # Post-process rate/pct fields
        normalized_extracted = _normalize_rate_fields(normalized_extracted, raw_extracted)

        extraction_results[doc_id] = {
            "raw_extracted": raw_extracted,
            "normalized_extracted": normalized_extracted
        }

    logger.info(f"Batch extraction completed for {len(extraction_results)} documents")
    return extraction_results


@workflows.activity()
async def batch_validate_and_save_activity(
    documents: List[dict],
    classification_results: dict,
    ocr_results: dict,
    extraction_results: dict
) -> dict:
    """
    Step 5: Batch Validation & Persistence.
    Computes field confidences, validates completeness, marks status, and saves to DB.
    """
    logger.info(f"Starting batch validate and save for {len(documents)} documents")
    final_results = []
    completed_count = 0
    awaiting_review_count = 0

    for doc in documents:
        doc_id = doc["document_id"]
        doc_type = classification_results.get(doc_id, {}).get("doc_type", "others")
        ocr_data = ocr_results.get(doc_id, {})
        word_confidences = ocr_data.get("word_confidences", [])
        ocr_conf = ocr_data.get("confidence", 0.95)
        blocks = ocr_data.get("blocks", [])

        ext_data = extraction_results.get(doc_id, {})
        raw_ext = ext_data.get("raw_extracted", {})
        norm_ext = ext_data.get("normalized_extracted", {})

        # Compute field confidences
        field_confs = _compute_confidences_recursive(norm_ext, word_confidences)

        # Average field confidence
        def _gather_confs(obj):
            scores = []
            if isinstance(obj, dict):
                for v in obj.values():
                    scores.extend(_gather_confs(v))
            elif isinstance(obj, list):
                for item in obj:
                    scores.extend(_gather_confs(item))
            elif isinstance(obj, (int, float)):
                scores.append(float(obj))
            return scores

        all_scores = _gather_confs(field_confs)
        overall_confidence = (sum(all_scores) / len(all_scores)) if all_scores else ocr_conf

        # Determine approval: Score >= 80% is auto-approved, else awaiting_review
        is_auto_approved = overall_confidence >= 0.80

        # Persist OCR blocks for field citation highlighting
        if blocks:
            _save_ocr_blocks(doc_id, blocks)

        # KYC Photo and Signature Extraction
        template_meta = get_template_metadata(doc_type)
        is_kyc = template_meta.get("is_kyc", False)
        signature_ver = None
        photo_ver = None

        if is_kyc:
            file_path = doc.get("file_path", "")
            if file_path and os.path.exists(file_path):
                try:
                    kyc_res = crop_kyc_images(file_path, doc_type, doc_id)
                    kyc_image_result = kyc_res.get("kyc_image_result") or {}
                    if kyc_image_result:
                        signature_ver = {
                            "has_signature": kyc_image_result.get("has_signature", False),
                            "signer_name": kyc_image_result.get("signer_name", ""),
                            "signature_crop_path": kyc_image_result.get("signature_crop_path"),
                        }
                        photo_ver = {
                            "has_photo": kyc_image_result.get("has_photo", False),
                            "photo_crop_path": kyc_image_result.get("photo_crop_path"),
                        }
                        # Inject base64 image data into validated_data & raw_extracted for frontend preview
                        for f_dict in [norm_ext, raw_ext]:
                            if isinstance(f_dict, dict):
                                if kyc_image_result.get("signature_base64"):
                                    f_dict["signature_image"] = kyc_image_result["signature_base64"]
                                f_dict["signature_detected"] = kyc_image_result.get("has_signature", False)
                                if kyc_image_result.get("photo_base64"):
                                    f_dict["photo_image"] = kyc_image_result["photo_base64"]
                                f_dict["photo_detected"] = kyc_image_result.get("has_photo", False)
                                if kyc_image_result.get("signer_name"):
                                    f_dict["signer_name"] = kyc_image_result["signer_name"]

                        logger.info(f"[Document {doc_id}] KYC crops extracted & injected into validated_data: photo={photo_ver['has_photo']}, sig={signature_ver['has_signature']}")
                except Exception as e:
                    logger.warning(f"[Document {doc_id}] KYC image cropping failed: {e}")

        # Persist to DB
        await persist_final_extraction(
            document_id=doc_id,
            doc_type=doc_type,
            raw_extracted=raw_ext,
            validated_data=norm_ext,
            confidence_score=overall_confidence,
            field_confidences=field_confs,
            fraud_check=None,
            vllm_fallback=None,
            signature_verification=signature_ver,
            photo_verification=photo_ver,
            corrections=None
        )

        # If confidence is low, update status to awaiting_review instead of completed
        if not is_auto_approved:
            await db.update_status_and_message(
                doc_id,
                "awaiting_review",
                f"Confidence ({overall_confidence:.1%}) below threshold (80%) — human review recommended."
            )
            awaiting_review_count += 1
            final_status = "awaiting_review"
        else:
            completed_count += 1
            final_status = "completed"

        final_results.append({
            "document_id": doc_id,
            "filename": doc.get("filename"),
            "doc_type": doc_type,
            "status": final_status,
            "confidence_score": overall_confidence,
            "extracted_fields_count": len(norm_ext) if isinstance(norm_ext, dict) else 0,
            "blocks_count": len(blocks)
        })

    summary = {
        "total_documents": len(documents),
        "completed": completed_count,
        "awaiting_review": awaiting_review_count,
        "documents": final_results
    }
    logger.info(f"Batch validate & save completed: {summary}")
    return summary

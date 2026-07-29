import os
import json
import logging
import re
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.norm_config import build_normalization_rules_prompt
import db.operations as db

from tools.extractor import (
    EXTRACTOR_TOOLS,
    extract_text_from_document,
    crop_kyc_images
)

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)


def _extract_text(content) -> str:
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


def _calculate_field_confidence(field_value, word_confidence_scores: list) -> float:
    if not isinstance(field_value, str):
        field_str = str(field_value).strip() if field_value is not None else ""
    else:
        field_str = field_value.strip()
        
    if not field_str:
        return 1.0

    # Normalize and split field value into word tokens
    field_words = re.findall(r'\b\w+\b', field_str.lower())
    if not field_words:
        return 1.0
    
    confidences = []
    for f_word in field_words:
        # Search for this word in word_confidence_scores
        word_matches = [
            w["confidence"] for w in word_confidence_scores
            if w["text"].strip().lower() == f_word or f_word in w["text"].strip().lower()
        ]
        if word_matches:
            # Take average of matching word confidences
            confidences.append(sum(word_matches) / len(word_matches))
            
    if confidences:
        return sum(confidences) / len(confidences)
    
    return 1.0


def _compute_confidences_recursive(data, word_confidence_scores):
    if isinstance(data, dict):
        conf_dict = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                conf_dict[k] = _compute_confidences_recursive(v, word_confidence_scores)
            else:
                conf_dict[k] = _calculate_field_confidence(v, word_confidence_scores)
        return conf_dict
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


@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    """
    Step 4 — Extractor.
    Extracts fields from the document using the Extractor Agent via tools.
    """
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")

        # Determine agent routing
        agent_id = settings.GENERAL_EXTRACTOR_AGENT_ID
        if not agent_id:
            raise ValueError("GENERAL_EXTRACTOR_AGENT_ID is not configured in settings/environment.")
        logger.info(f"[Document {document_id}] Routing to general extractor agent: {agent_id}")

        # Check template metadata for KYC flag
        from tools.extractor import get_template_metadata
        template_meta = get_template_metadata(doc_type)
        is_kyc = template_meta.get("is_kyc", False)

        # Use imported tools schema
        tools = EXTRACTOR_TOOLS

        normalization_rules = build_normalization_rules_prompt()

        prompt = (
            f"You are the Extractor Agent. We need to extract structured data from the document "
            f"at path '{file_path}' which has been classified as '{doc_type}'.\n"
            f"First, call the `extract_text_from_document` tool to get the text content and structured OCR extraction.\n"
            f"{('You MUST also call the `crop_kyc_images` tool to extract the signature and photo crops — this template is marked as KYC.' if is_kyc else '')}\n"
            f"CRITICAL: If the `structured_ocr_extraction` returned by the tool contains generic placeholder fields "
            f"(such as `document_title`, `summary`, `full_ocr_text`), it indicates that no predefined template "
            f"exists for '{doc_type}'. In this case, do NOT output those generic fields. Instead, read the full "
            f"`raw_ocr_text` returned by the tool and use your own intelligence to identify all relevant keys, "
            f"values, and tables for this type of document, and extract them into the `raw_extracted` and "
            f"`normalized_extracted` dictionaries.\n\n"
            f"Apply these standard normalization rules to the extracted fields:\n"
            f"{normalization_rules}\n\n"
            f"Based on the results, output a JSON response matching exactly this schema:\n"
            f"{{\n"
            f"  \"raw_extracted\": dict,\n"
            f"  \"normalized_extracted\": dict\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Extractor Agent ({agent_id})")
        response = await client.agents.complete_async(
            agent_id=agent_id,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        # Saved state from tool execution to merge later
        ocr_confidence = 0.0
        word_confidence_scores = []
        raw_text = ""
        kyc_image_result = None

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Extractor Agent requested tool calls: {message.tool_calls}")

            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            }
            messages.append(assistant_msg)

            for tool_call in message.tool_calls:
                if tool_call.function.name == "extract_text_from_document":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)
                    t_doc_type = args.get("doc_type", doc_type)

                    logger.info(f"[Document {document_id}] Executing extract_text_from_document tool for file: {t_file_path}")

                    res = extract_text_from_document(t_file_path, t_doc_type, document_id=document_id)
                    raw_text = res["raw_text"]
                    ocr_confidence = res["confidence"]
                    word_confidence_scores = res["word_confidence_scores"]

                    messages.append({
                        "role": "tool",
                        "name": "extract_text_from_document",
                        "content": json.dumps(res["tool_output"]),
                        "tool_call_id": tool_call.id
                    })

                elif tool_call.function.name == "crop_kyc_images":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)
                    t_doc_type = args.get("doc_type", doc_type)

                    logger.info(f"[Document {document_id}] Executing crop_kyc_images tool for file: {t_file_path}")

                    res = crop_kyc_images(t_file_path, t_doc_type, document_id)
                    kyc_image_result = res["kyc_image_result"]

                    messages.append({
                        "role": "tool",
                        "name": "crop_kyc_images",
                        "content": json.dumps(res["tool_output"]),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Extractor Agent with tool result")
            response = await client.agents.complete_async(
                agent_id=agent_id,
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message

        # Parse final response
        content = _extract_text(message.content).strip()
        try:
            parsed_response = json.loads(content)
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to parse agent JSON output: {content}")
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed_response = json.loads(match.group(0))
            else:
                raise

        raw_extracted = parsed_response.get("raw_extracted", {})
        normalized_extracted = parsed_response.get("normalized_extracted", {})

        # Fallback if the agent returned a flat structure instead of nesting
        if not raw_extracted and not normalized_extracted:
            raw_extracted = parsed_response
            normalized_extracted = parsed_response

        # Post-process rate fields to ensure '%' sign is preserved
        normalized_extracted = _normalize_rate_fields(normalized_extracted, raw_extracted)

        # Calculate field confidences
        field_confidences = _compute_confidences_recursive(normalized_extracted, word_confidence_scores)

        # Check if template_fields are specified for this document type
        from tools.extractor import get_template_fields
        template_fields = get_template_fields(doc_type)
        template_field_keys = None
        if template_fields and isinstance(template_fields, list):
            template_field_keys = set(
                (f.get("key") or f.get("name") or str(f)) if isinstance(f, dict) else str(f)
                for f in template_fields
            )

        # Merge KYC image data into the extracted fields if cropped
        if kyc_image_result:
            for f_dict in [normalized_extracted, raw_extracted]:
                if kyc_image_result.get("signature_base64"):
                    f_dict["signature_image"] = kyc_image_result["signature_base64"]
                f_dict["signature_detected"] = kyc_image_result.get("has_signature", False)
                if kyc_image_result.get("photo_base64"):
                    f_dict["photo_image"] = kyc_image_result["photo_base64"]
                f_dict["photo_detected"] = kyc_image_result.get("has_photo", False)
                if kyc_image_result.get("signer_name") and (template_field_keys is None or "signer_name" in template_field_keys):
                    f_dict["signer_name"] = kyc_image_result["signer_name"]

        # System KYC image fields allowed automatically
        SYSTEM_KYC_KEYS = {"signature_image", "photo_image", "signature_detected", "photo_detected"}

        # If a template is configured for this document type, strictly enforce template fields
        if template_field_keys is not None:
            allowed_keys = template_field_keys | SYSTEM_KYC_KEYS
            for f_dict in [normalized_extracted, raw_extracted]:
                extra_keys = [k for k in list(f_dict.keys()) if k not in allowed_keys]
                for k in extra_keys:
                    f_dict.pop(k, None)

        logger.info(f"[Document {document_id}] Normalized fields from extractor: {normalized_extracted}")
        return {
            "fields": normalized_extracted,
            "raw_extracted": raw_extracted,
            "raw_ocr": raw_text,
            "confidence": ocr_confidence,
            "field_confidences": field_confidences
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

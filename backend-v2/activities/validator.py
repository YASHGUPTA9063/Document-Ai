import os
import json
import datetime
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
import db.operations as db

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


from tools.validator import VALIDATOR_TOOLS, get_template_fields



@workflows.activity()
async def validator_activity(
    document_id: str, 
    extracted_data: dict, 
    doc_type: str, 
    ocr_confidence: float,
    field_confidences: dict = None
) -> dict:
    """
    Step 5 — Validator.
    Validates extracted fields schema using the Validator Agent.
    """
    try:
        logger.info(f"[Document {document_id}] Starting validator activity")
        
        # Remove massive base64 images from the prompt to avoid overwhelming the LLM
        prompt_data = extracted_data.copy()
        sig_img = prompt_data.pop("signature_image", None)
        photo_img = prompt_data.pop("photo_image", None)
        
        json_data = json.dumps(prompt_data)

        # Use imported tools schema
        tools = VALIDATOR_TOOLS

        today = datetime.date.today().isoformat()
        prompt = (
            f"You are the Validator Agent. Today's date is {today}.\n"
            f"We have extracted data from a document of type '{doc_type}'.\n"
            f"First, call the `get_validation_schema` tool with doc_type: '{doc_type}' to load the target schema.\n"
            f"Then validate this extracted JSON data against that schema:\n"
            f"{json_data}\n\n"
            f"CRITICAL: If the `get_validation_schema` tool returns an empty list or indicates no template schema is configured, "
            f"use your own intelligence to validate that the extracted data is logical, consistent, and free of obvious OCR/parsing errors "
            f"for a document of type '{doc_type}'. Ensure date logic sequence (e.g. expiration/validation date is not prior to issue or creation date).\n\n"
            f"Output a JSON object matching exactly this schema:\n"
            f"{{\n"
            f"  \"is_valid\": bool,\n"
            f"  \"validation_errors\": list of strings,\n"
            f"  \"validated_data\": dict\n"
            f"}}\n\n"
            f"IMPORTANT: Do not modify the casing, date formatting, number styles, or custom format rules present in the extracted data. "
            f"Keep the values in 'validated_data' formatted exactly as they are in the extracted data.\n\n"
            f"IMPORTANT: Only flag a field as missing or empty if it is explicitly marked as 'required' in the schema. "
            f"Do NOT flag optional fields that are empty or null — they are expected to be blank sometimes.\n\n"
            f"IMPORTANT: When cross-checking amount_in_words against amount_in_numbers, compare only the actual numerical value. "
            f"Ignore trivial formatting differences such as a missing 'Only' suffix, 'Rupees' prefix, decimal '.00', or minor phrasing variations. "
            f"Only flag a mismatch if the numerical values genuinely differ."
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Validator Agent ({settings.VALIDATOR_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.VALIDATOR_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Validator Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "get_validation_schema":
                    args = json.loads(tool_call.function.arguments)
                    t_doc_type = args.get("doc_type", doc_type)

                    logger.info(f"[Document {document_id}] Executing get_validation_schema tool for: {t_doc_type}")

                    fields_list = get_template_fields(t_doc_type) or []

                    messages.append({
                        "role": "tool",
                        "name": "get_validation_schema",
                        "content": json.dumps({"fields": fields_list}),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Validator Agent with tool result")
            response = await client.agents.complete_async(
                agent_id=settings.VALIDATOR_AGENT_ID,
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message

        # Parse final response
        content = _extract_text(message.content).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            logger.info(f"[Document {document_id}] Final message not JSON. Requesting JSON formatting.")
            messages.append({
                "role": "user",
                "content": (
                    "Based on your validation checks, please output the final validation results "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"is_valid\": bool,\n"
                    "  \"validation_errors\": [],\n"
                    "  \"validated_data\": {}\n"
                    "}"
                )
            })
            response = await client.agents.complete_async(
                agent_id=settings.VALIDATOR_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        validated_data = parsed.get("validated_data", prompt_data)
        logger.info(f"[Document {document_id}] Validated fields from validator: {validated_data}")
        
        # Re-inject the massive base64 strings so they are saved to the database
        if sig_img is not None:
            validated_data["signature_image"] = sig_img
        if photo_img is not None:
            validated_data["photo_image"] = photo_img

        # Strictly enforce template fields on validated_data
        template_fields = get_template_fields(doc_type)
        if template_fields and isinstance(template_fields, list):
            allowed_keys = set(
                (f.get("key") or f.get("name") or str(f)) if isinstance(f, dict) else str(f)
                for f in template_fields
            ) | {"signature_image", "photo_image", "signature_detected", "photo_detected"}
            
            unwanted = [k for k in list(validated_data.keys()) if k not in allowed_keys]
            for k in unwanted:
                validated_data.pop(k, None)

        # Deterministic mandatory-field check (runs after LLM, after allow-list strip)
        if template_fields and isinstance(template_fields, list):
            missing = []
            for f in template_fields:
                if not (isinstance(f, dict) and f.get("required")):
                    continue
                key = f.get("key") or f.get("name")
                if key and validated_data.get(key) in (None, "", []):
                    missing.append(key)
            if missing:
                errs = parsed.setdefault("validation_errors", [])
                for k in missing:
                    if not any(k in e for e in errs):
                        errs.append(f"The field '{k}' is required but is empty.")
                parsed["is_valid"] = False

        # ─── Weighted Document Score ───
        # Compute doc_score as: Σ(field_confidence × weight) / Σ(weight)
        # Each template field carries a "weight" (default 80).
        # field_confidences values are 0.0–1.0.
        doc_score = None
        fc = field_confidences or {}
        if template_fields and isinstance(template_fields, list) and fc:
            total_weighted = 0.0
            total_weight = 0.0
            low_confidence_fields = []
            for f in template_fields:
                if not isinstance(f, dict):
                    continue
                key = f.get("key") or f.get("name")
                if not key:
                    continue
                weight = f.get("weight", 80)
                conf = fc.get(key)
                if conf is None:
                    # Field not extracted — treat as 0 confidence
                    conf = 0.0
                elif isinstance(conf, dict):
                    # Nested confidence (e.g. line items) — skip for now
                    continue
                elif isinstance(conf, list):
                    # Array of sub-confidences — average them
                    flat = [c for c in conf if isinstance(c, (int, float))]
                    conf = (sum(flat) / len(flat)) if flat else 0.0
                total_weighted += conf * weight
                total_weight += weight
                if conf < 0.8:
                    low_confidence_fields.append((key, conf))

            if total_weight > 0:
                doc_score = total_weighted / total_weight
                logger.info(
                    f"[Document {document_id}] Weighted doc score: "
                    f"{doc_score:.2%} (threshold: 80%)"
                )
                if doc_score < 0.80:
                    errs = parsed.setdefault("validation_errors", [])
                    score_pct = round(doc_score * 100, 1)
                    warning_msg = (
                        f"Document confidence score is {score_pct}% "
                        f"(below 80% threshold)."
                    )
                    if not any("Document confidence score" in e for e in errs):
                        errs.append(warning_msg)

        # Use weighted doc_score when available, otherwise fall back to OCR confidence
        final_confidence = doc_score if doc_score is not None else ocr_confidence

        return {
            "is_valid": parsed.get("is_valid", False),
            "confidence_score": final_confidence,
            "doc_score": doc_score,  # Weighted doc score (None if no template)
            "validation_errors": parsed.get("validation_errors", []),
            "validated_data": validated_data,
            "field_confidences": field_confidences or {}
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

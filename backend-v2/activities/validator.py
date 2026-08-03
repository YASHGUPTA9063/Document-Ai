"""
Validator Activity
===================
Validates extracted data against business rules and corrects OCR errors.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.validator import VALIDATOR_TOOLS, get_template_fields
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def validator_activity(document_id: str, extracted_data: dict, doc_type: str, ocr_confidence: float = 0.0, field_confidences: dict = None) -> dict:
    """
    Step 5 — Validator.
    Validates extracted data against business rules.
    """
    try:
        logger.info(f"[Document {document_id}] Starting validator activity for type: {doc_type}")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("validator")

        async def execute_tool(name: str, args: dict):
            if name == "get_template_fields":
                t_doc_type = args.get("doc_type", doc_type)
                logger.info(f"[Document {document_id}] Executing get_template_fields for: {t_doc_type}")
                return get_template_fields(t_doc_type)
            else:
                return {"error": f"Unknown tool: {name}"}

        # Strip the base64 image blobs out of the prompt — they are enormous and
        # would swamp the LLM context. They are re-injected after validation.
        prompt_data = (extracted_data or {}).copy()
        sig_img = prompt_data.pop("signature_image", None)
        photo_img = prompt_data.pop("photo_image", None)

        user_message = (
            f"Please validate the following extracted data for a '{doc_type}' document.\n\n"
            f"Extracted data:\n{json.dumps(prompt_data, indent=2)}\n\n"
            f"OCR Confidence: {ocr_confidence}\n"
            f"Field Confidences: {json.dumps(field_confidences or {}, indent=2)}\n\n"
            f"You can call the `get_template_fields` tool with doc_type='{doc_type}' to get "
            f"the expected field schema for this document type.\n\n"
            f"Validate the data against business rules, correct any obvious OCR errors, "
            f"and return the validation result as JSON."
        )

        parsed = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=VALIDATOR_TOOLS,
            tool_executor=execute_tool,
            temperature=0.2,
        )

        validated_data = parsed.get("validated_data", prompt_data)

        # Re-inject the base64 strings so they are persisted to the database
        if sig_img is not None:
            validated_data["signature_image"] = sig_img
        if photo_img is not None:
            validated_data["photo_image"] = photo_img

        # Strictly enforce template fields on validated_data — the model
        # otherwise carries through keys the template does not define.
        template_fields = get_template_fields(doc_type)
        if template_fields and isinstance(template_fields, list):
            allowed_keys = set(
                (f.get("key") or f.get("name") or str(f)) if isinstance(f, dict) else str(f)
                for f in template_fields
            ) | {"signature_image", "photo_image", "signature_detected", "photo_detected"}

            unwanted = [k for k in list(validated_data.keys()) if k not in allowed_keys]
            for k in unwanted:
                validated_data.pop(k, None)

        logger.info(f"[Document {document_id}] Validation result: is_valid={parsed.get('is_valid')}")
        return {
            "is_valid": parsed.get("is_valid", False),
            "confidence_score": ocr_confidence,
            "validation_errors": parsed.get("validation_errors", []),
            "validated_data": validated_data,
            "field_confidences": field_confidences or {},
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

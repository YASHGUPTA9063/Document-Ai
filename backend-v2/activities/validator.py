import os
import json
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

        prompt = (
            f"You are the Validator Agent. We have extracted data from a document of type '{doc_type}'.\n"
            f"First, call the `get_validation_schema` tool with doc_type: '{doc_type}' to load the target schema.\n"
            f"Then validate this extracted JSON data against that schema:\n"
            f"{json_data}\n\n"
            f"Output a JSON object matching exactly this schema:\n"
            f"{{\n"
            f"  \"is_valid\": bool,\n"
            f"  \"validation_errors\": list of strings,\n"
            f"  \"validated_data\": dict\n"
            f"}}\n\n"
            f"IMPORTANT: Do not modify the casing, date formatting, number styles, or custom format rules present in the extracted data. "
            f"Keep the values in 'validated_data' formatted exactly as they are in the extracted data."
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Validator Agent ({settings.VALIDATOR_AGENT_ID})")
        response = client.agents.complete(
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
            response = client.agents.complete(
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
            response = client.agents.complete(
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
        
        return {
            "is_valid": parsed.get("is_valid", False),
            "confidence_score": ocr_confidence, # Pass through the OCR native confidence score
            "validation_errors": parsed.get("validation_errors", []),
            "validated_data": validated_data,
            "field_confidences": field_confidences or {}
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

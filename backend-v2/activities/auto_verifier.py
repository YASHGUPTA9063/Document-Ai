import os
import base64 as b64mod
import tempfile
import logging
import json
import mistralai.workflows as workflows
from mistralai.client import Mistral
from tools.auto_verifier import (
    AUTO_VERIFIER_TOOLS,
    find_customer_reference,
    verify_signature,
    verify_face
)
from config import settings



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


@workflows.activity()
async def auto_verify_activity(document_id: str, validated_data: dict) -> dict:
    """
    Step 3.6 — Auto Verifier.
    Checks customer reference availability and runs verification using the Auto-Verifier Agent.
    """
    logger.info(f"[AutoVerifier] Starting auto verification for document {document_id}")
    
    if not validated_data:
        logger.warning(f"[AutoVerifier] No validated data provided for document {document_id}.")
        return {"status": "skipped", "reason": "empty_validated_data"}

    # Saved state from customer lookup to resolve reference images in subsequent tool calls
    cached_ref_signature = None
    cached_ref_photo = None

    async def execute_direct_fallback() -> dict:
        logger.info(f"[AutoVerifier] Running direct fallback verification.")
        res = await find_customer_reference(document_id, validated_data)
        ref_status = res["tool_output"]
        if not ref_status.get("matched"):
            return {"status": "skipped", "reason": ref_status.get("reason", "no_reference")}

        c_id = ref_status["customer_id"]
        sig_res = None
        face_res = None

        if ref_status["has_doc_signature"] and ref_status["has_ref_signature"]:
            try:
                sig_res = await verify_signature(c_id, validated_data.get("signature_image"), res["reference_signature"])
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct signature verifier failed: {e}")

        if ref_status["has_doc_photo"] and ref_status["has_ref_photo"]:
            try:
                face_res = await verify_face(c_id, validated_data.get("photo_image"), res["reference_photo"])
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct face verifier failed: {e}")

        return {
            "status": "success",
            "signature": sig_res,
            "photo": face_res
        }

    try:
        if not settings.AUTO_VERIFIER_AGENT_ID:
            logger.warning("[AutoVerifier] AUTO_VERIFIER_AGENT_ID not set. Falling back to direct execution.")
            return await execute_direct_fallback()

        # Use imported tools schema
        tools = AUTO_VERIFIER_TOOLS

        prompt = (
            f"You are the Auto-Verifier Agent. We need to verify the signatures and photos for document '{document_id}'.\n"
            f"1. Call `find_customer_reference` first to check if customer reference images are available in the database.\n"
            f"2. Based on the returned check results:\n"
            f"   - If signature crops are available on both the document and reference, call `verify_signature`.\n"
            f"   - If photo crops are available on both the document and reference, call `verify_face`.\n"
            f"3. Combine the results and return the final verification output matching exactly this JSON schema:\n"
            f"{{\n"
            f"  \"status\": \"success\" or \"skipped\",\n"
            f"  \"signature\": dict or null,\n"
            f"  \"photo\": dict or null\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[AutoVerifier] Calling Auto-Verifier Agent ({settings.AUTO_VERIFIER_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.AUTO_VERIFIER_AGENT_ID,
            messages=messages,
            tools=tools
        )
        message = response.choices[0].message

        # Saved state of verification results to construct the final output
        signature_result = None
        photo_result = None
        status = "skipped"

        while message.tool_calls:
            logger.info(f"[AutoVerifier] Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "find_customer_reference":
                    logger.info(f"[AutoVerifier] Executing find_customer_reference tool")
                    res = await find_customer_reference(document_id, validated_data)
                    cached_ref_signature = res["reference_signature"]
                    cached_ref_photo = res["reference_photo"]
                    result = res["tool_output"]
                    if result.get("matched"):
                        status = "success"

                    messages.append({
                        "role": "tool",
                        "name": "find_customer_reference",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })

                elif tool_call.function.name == "verify_signature":
                    args = json.loads(tool_call.function.arguments)
                    c_id = args.get("customer_id")
                    
                    logger.info(f"[AutoVerifier] Executing verify_signature tool for customer_id: {c_id}")
                    signature_result = await verify_signature(
                        c_id,
                        validated_data.get("signature_image"),
                        cached_ref_signature
                    )

                    messages.append({
                        "role": "tool",
                        "name": "verify_signature",
                        "content": json.dumps(signature_result or {"status": "error"}),
                        "tool_call_id": tool_call.id
                    })

                elif tool_call.function.name == "verify_face":
                    args = json.loads(tool_call.function.arguments)
                    c_id = args.get("customer_id")

                    logger.info(f"[AutoVerifier] Executing verify_face tool for customer_id: {c_id}")
                    photo_result = await verify_face(
                        c_id,
                        validated_data.get("photo_image"),
                        cached_ref_photo
                    )

                    messages.append({
                        "role": "tool",
                        "name": "verify_face",
                        "content": json.dumps(photo_result or {"status": "error"}),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[AutoVerifier] Resuming Auto-Verifier Agent with tool result")
            response = client.agents.complete(
                agent_id=settings.AUTO_VERIFIER_AGENT_ID,
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message

        # Parse final response
        content = _extract_text(message.content).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            logger.info(f"[AutoVerifier] Final message not JSON. Requesting JSON formatting.")
            messages.append({
                "role": "user",
                "content": (
                    "Based on the tool output, please output the final verification status and results "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"status\": \"success\",\n"
                    "  \"signature\": {} or null,\n"
                    "  \"photo\": {} or null\n"
                    "}"
                )
            })
            response = client.agents.complete(
                agent_id=settings.AUTO_VERIFIER_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        return parsed

    except Exception as e:
        logger.error(f"[AutoVerifier] Auto-Verifier Agent failed: {str(e)}")
        # Record error and return direct execution
        import db.operations as db
        await db.update_error(document_id, {"error": str(e), "stage": "auto_verify"})
        return await execute_direct_fallback()

import os
import asyncio
import base64 as b64mod
import tempfile
import logging
import json
import mistralai.workflows as workflows
from platform_core.adapters.resilient_mistral import get_mistral_client
from tools.auto_verifier import (
    AUTO_VERIFIER_TOOLS,
    find_customer_reference,
    verify_signature,
    verify_face
)
from config import settings



logger = logging.getLogger(__name__)
client = get_mistral_client()


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

        async def safe_verify_sig():
            try:
                return await verify_signature(c_id, validated_data.get("signature_image"), res["reference_signature"])
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct signature verifier failed: {e}")
                return None

        async def safe_verify_face():
            try:
                return await verify_face(c_id, validated_data.get("photo_image"), res["reference_photo"])
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct face verifier failed: {e}")
                return None

        sig_coro = safe_verify_sig() if (ref_status["has_doc_signature"] and ref_status["has_ref_signature"]) else asyncio.sleep(0)
        face_coro = safe_verify_face() if (ref_status["has_doc_photo"] and ref_status["has_ref_photo"]) else asyncio.sleep(0)

        sig_res, face_res = await asyncio.gather(sig_coro, face_coro)

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
            f"1. Call `find_customer_reference` ONCE to check if customer reference images are available in the database.\n"
            f"2. Based on the returned check results:\n"
            f"   - If `matched` is false, STOP IMMEDIATELY and return: {{\"status\": \"skipped\", \"reason\": \"no_customer_reference_found\", \"signature\": null, \"photo\": null}}\n"
            f"   - If `matched` is true and signature crops are available on both the document and reference, call `verify_signature`.\n"
            f"   - If `matched` is true and photo crops are available on both the document and reference, call `verify_face`.\n"
            f"3. Combine the results and return the final verification output matching exactly this JSON schema:\n"
            f"{{\n"
            f"  \"status\": \"success\" or \"skipped\",\n"
            f"  \"signature\": dict or null,\n"
            f"  \"photo\": dict or null\n"
            f"}}\n"
            f"IMPORTANT: Do NOT call `find_customer_reference` more than once. Do NOT retry tools. "
            f"If no match is found on the first call, immediately return the skipped JSON."
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[AutoVerifier] Calling Auto-Verifier Agent ({settings.AUTO_VERIFIER_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.AUTO_VERIFIER_AGENT_ID,
            messages=messages,
            tools=tools,
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message

        # Saved state of verification results to construct the final output
        signature_result = None
        photo_result = None
        status = "skipped"
        customer_ref_checked = False  # Track whether find_customer_reference has been called

        MAX_TOOL_LOOP_ITERATIONS = 10
        loop_iter = 0
        while message.tool_calls:
            loop_iter += 1
            if loop_iter > MAX_TOOL_LOOP_ITERATIONS:
                logger.warning(f"[AutoVerifier] Tool call loop exceeded {MAX_TOOL_LOOP_ITERATIONS} iterations, breaking out.")
                break
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

            async def execute_tool(tool_call):
                nonlocal cached_ref_signature, cached_ref_photo, signature_result, photo_result, status, customer_ref_checked
                name = tool_call.function.name
                if name == "find_customer_reference":
                    if customer_ref_checked:
                        # Agent is retrying find_customer_reference — return cached result and tell it to stop
                        logger.warning(f"[AutoVerifier] Agent retried find_customer_reference — returning cached no-match result.")
                        return {
                            "role": "tool",
                            "name": "find_customer_reference",
                            "content": json.dumps({"matched": False, "reason": "already_checked_no_reference_found"}),
                            "tool_call_id": tool_call.id
                        }
                    customer_ref_checked = True
                    logger.info(f"[AutoVerifier] Executing find_customer_reference tool")
                    res = await find_customer_reference(document_id, validated_data)
                    cached_ref_signature = res["reference_signature"]
                    cached_ref_photo = res["reference_photo"]
                    result = res["tool_output"]
                    if result.get("matched"):
                        status = "success"
                    return {
                        "role": "tool",
                        "name": "find_customer_reference",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    }
                elif name == "verify_signature":
                    args = json.loads(tool_call.function.arguments)
                    c_id = args.get("customer_id")
                    logger.info(f"[AutoVerifier] Executing verify_signature tool for customer_id: {c_id}")
                    signature_result = await verify_signature(
                        c_id,
                        validated_data.get("signature_image"),
                        cached_ref_signature
                    )
                    return {
                        "role": "tool",
                        "name": "verify_signature",
                        "content": json.dumps(signature_result or {"status": "error"}),
                        "tool_call_id": tool_call.id
                    }
                elif name == "verify_face":
                    args = json.loads(tool_call.function.arguments)
                    c_id = args.get("customer_id")
                    logger.info(f"[AutoVerifier] Executing verify_face tool for customer_id: {c_id}")
                    photo_result = await verify_face(
                        c_id,
                        validated_data.get("photo_image"),
                        cached_ref_photo
                    )
                    return {
                        "role": "tool",
                        "name": "verify_face",
                        "content": json.dumps(photo_result or {"status": "error"}),
                        "tool_call_id": tool_call.id
                    }
                else:
                    logger.warning(f"[AutoVerifier] Unknown tool call name: {name}")
                    return {
                        "role": "tool",
                        "name": name,
                        "content": json.dumps({"error": "unknown_tool"}),
                        "tool_call_id": tool_call.id
                    }

            tool_tasks = [execute_tool(tc) for tc in message.tool_calls]
            tool_responses = await asyncio.gather(*tool_tasks)
            messages.extend(tool_responses)

            # If find_customer_reference returned no match, inject a stop instruction
            # so the agent produces a final JSON instead of looping
            if customer_ref_checked and status == "skipped":
                messages.append({
                    "role": "user",
                    "content": (
                        "No customer reference was found. Do NOT call any more tools. "
                        "Return immediately with this exact JSON: "
                        '{"status": "skipped", "reason": "no_customer_reference_found", "signature": null, "photo": null}'
                    )
                })
                logger.info(f"[AutoVerifier] No customer match — injecting stop instruction to agent.")
                response = await client.agents.complete_async(
                    agent_id=settings.AUTO_VERIFIER_AGENT_ID,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                message = response.choices[0].message
                break

            logger.info(f"[AutoVerifier] Resuming Auto-Verifier Agent with tool result")
            response = await client.agents.complete_async(
                agent_id=settings.AUTO_VERIFIER_AGENT_ID,
                messages=messages,
                tools=tools,
                response_format={"type": "json_object"}
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
            response = await client.agents.complete_async(
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
        # No db.update_error(): the run continues on the direct path, so the
        # document is not failed.
        return await execute_direct_fallback()

"""
Auto-Verifier Activity
=======================
Coordinates signature and face photo verification against reference records.

Runs through the provider-agnostic ProviderRegistry + PromptManager; the system
prompt lives in platform_core/prompts/auto_verifier.md.

Uses a custom conversation loop rather than run_agent_loop() because tool
execution captures side-effect state (the reference signature/photo blobs, and
the individual verification results) that is needed to build the final result —
and because the loop needs a guard against the model re-calling
find_customer_reference forever when no reference exists.
"""

import asyncio
import json
import logging

import db.operations as db
from tools.auto_verifier import (
    AUTO_VERIFIER_TOOLS,
    find_customer_reference,
    verify_signature,
    verify_face,
)
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import _parse_json_response

logger = logging.getLogger(__name__)
prompts = PromptManager()

MAX_TOOL_LOOP_ITERATIONS = 10


async def auto_verify_activity(document_id: str, validated_data: dict) -> dict:
    """
    Step 5.5 — Auto Verification.

    Checks customer reference availability and runs signature/face verification.

    Returns:
        {"status": "success" | "skipped", "signature": dict | None, "photo": dict | None}
    """
    logger.info(f"[AutoVerifier] Starting auto verification for document {document_id}")

    if not validated_data:
        logger.warning(f"[AutoVerifier] No validated data provided for document {document_id}.")
        return {"status": "skipped", "reason": "empty_validated_data"}

    # Reference blobs resolved by find_customer_reference, needed by the verify_* tools
    cached_ref_signature = None
    cached_ref_photo = None

    async def execute_direct_fallback() -> dict:
        """Run the verification sequence deterministically, without the LLM."""
        logger.info("[AutoVerifier] Running direct fallback verification.")
        res = await find_customer_reference(document_id, validated_data)
        ref_status = res["tool_output"]
        if not ref_status.get("matched"):
            return {"status": "skipped", "reason": ref_status.get("reason", "no_reference")}

        c_id = ref_status["customer_id"]

        async def safe_verify_sig():
            try:
                return await verify_signature(
                    c_id, validated_data.get("signature_image"), res["reference_signature"]
                )
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct signature verifier failed: {e}")
                return None

        async def safe_verify_face():
            try:
                return await verify_face(
                    c_id, validated_data.get("photo_image"), res["reference_photo"]
                )
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct face verifier failed: {e}")
                return None

        sig_coro = (
            safe_verify_sig()
            if (ref_status["has_doc_signature"] and ref_status["has_ref_signature"])
            else asyncio.sleep(0)
        )
        face_coro = (
            safe_verify_face()
            if (ref_status["has_doc_photo"] and ref_status["has_ref_photo"])
            else asyncio.sleep(0)
        )

        sig_res, face_res = await asyncio.gather(sig_coro, face_coro)

        return {"status": "success", "signature": sig_res, "photo": face_res}

    try:
        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("auto_verifier")

        user_message = (
            f"We need to verify the signatures and photos for document '{document_id}'.\n"
            f"1. Call `find_customer_reference` ONCE to check if customer reference images are available in the database.\n"
            f"2. Based on the returned check results:\n"
            f'   - If `matched` is false, STOP IMMEDIATELY and return: {{"status": "skipped", "reason": "no_customer_reference_found", "signature": null, "photo": null}}\n'
            f"   - If `matched` is true and signature crops are available on both the document and reference, call `verify_signature`.\n"
            f"   - If `matched` is true and photo crops are available on both the document and reference, call `verify_face`.\n"
            f"3. Combine the results and return the final verification output matching exactly this JSON schema:\n"
            f'{{\n  "status": "success" or "skipped",\n  "signature": dict or null,\n  "photo": dict or null\n}}\n'
            f"IMPORTANT: Do NOT call `find_customer_reference` more than once. Do NOT retry tools. "
            f"If no match is found on the first call, immediately return the skipped JSON."
        )

        messages = [{"role": "user", "content": user_message}]

        logger.info("[AutoVerifier] Calling Auto-Verifier via registry LLM")
        response = await llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            tools=AUTO_VERIFIER_TOOLS,
            temperature=0.7,
        )

        # State captured from tool execution, used to build the final result
        signature_result = None
        photo_result = None
        status = "skipped"
        customer_ref_checked = False

        loop_iter = 0
        while response.tool_calls:
            loop_iter += 1
            if loop_iter > MAX_TOOL_LOOP_ITERATIONS:
                logger.warning(
                    f"[AutoVerifier] Tool call loop exceeded {MAX_TOOL_LOOP_ITERATIONS} iterations, breaking out."
                )
                break

            logger.info(f"[AutoVerifier] Agent requested tool calls: {response.tool_calls}")

            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in response.tool_calls
                ],
            })

            async def execute_tool(tool_call):
                nonlocal cached_ref_signature, cached_ref_photo
                nonlocal signature_result, photo_result, status, customer_ref_checked

                name = tool_call["function"]["name"]
                try:
                    args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                if name == "find_customer_reference":
                    if customer_ref_checked:
                        # The model is retrying — hand back the cached no-match verdict
                        # rather than re-querying, and make the dead end explicit.
                        logger.warning(
                            "[AutoVerifier] Agent retried find_customer_reference — returning cached no-match result."
                        )
                        return {
                            "role": "tool",
                            "name": "find_customer_reference",
                            "content": json.dumps(
                                {"matched": False, "reason": "already_checked_no_reference_found"}
                            ),
                            "tool_call_id": tool_call["id"],
                        }
                    customer_ref_checked = True
                    logger.info("[AutoVerifier] Executing find_customer_reference tool")
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
                        "tool_call_id": tool_call["id"],
                    }

                elif name == "verify_signature":
                    c_id = args.get("customer_id")
                    logger.info(f"[AutoVerifier] Executing verify_signature tool for customer_id: {c_id}")
                    signature_result = await verify_signature(
                        c_id, validated_data.get("signature_image"), cached_ref_signature
                    )
                    return {
                        "role": "tool",
                        "name": "verify_signature",
                        "content": json.dumps(signature_result or {"status": "error"}),
                        "tool_call_id": tool_call["id"],
                    }

                elif name == "verify_face":
                    c_id = args.get("customer_id")
                    logger.info(f"[AutoVerifier] Executing verify_face tool for customer_id: {c_id}")
                    photo_result = await verify_face(
                        c_id, validated_data.get("photo_image"), cached_ref_photo
                    )
                    return {
                        "role": "tool",
                        "name": "verify_face",
                        "content": json.dumps(photo_result or {"status": "error"}),
                        "tool_call_id": tool_call["id"],
                    }

                logger.warning(f"[AutoVerifier] Unknown tool call name: {name}")
                return {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps({"error": "unknown_tool"}),
                    "tool_call_id": tool_call["id"],
                }

            tool_responses = await asyncio.gather(
                *[execute_tool(tc) for tc in response.tool_calls]
            )
            messages.extend(tool_responses)

            # No reference found — tell the model to stop and emit the final JSON,
            # otherwise it tends to keep retrying the lookup.
            if customer_ref_checked and status == "skipped":
                messages.append({
                    "role": "user",
                    "content": (
                        "No customer reference was found. Do NOT call any more tools. "
                        "Return immediately with this exact JSON: "
                        '{"status": "skipped", "reason": "no_customer_reference_found", "signature": null, "photo": null}'
                    ),
                })
                logger.info("[AutoVerifier] No customer match — injecting stop instruction to agent.")
                response = await llm.chat(
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    response_format={"type": "json_object"},
                )
                break

            logger.info("[AutoVerifier] Resuming Auto-Verifier with tool results")
            response = await llm.chat(
                messages=messages,
                system_prompt=system_prompt,
                tools=AUTO_VERIFIER_TOOLS,
                temperature=0.7,
                response_format={"type": "json_object"},
            )

        parsed = _parse_json_response(response.content)
        logger.info(f"[AutoVerifier] Auto-verification result: status={parsed.get('status')}")
        return parsed

    except Exception as e:
        logger.error(f"[AutoVerifier] Auto-Verifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "auto_verify"})
        return await execute_direct_fallback()

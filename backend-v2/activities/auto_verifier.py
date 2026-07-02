import os
import base64 as b64mod
import tempfile
import logging
import json
import mistralai.workflows as workflows
from mistralai.client import Mistral
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Document, CustomerReference
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


def save_base64_to_temp_file(base64_str: str, prefix: str, ext: str = ".png") -> str:
    """Decodes base64 string and writes it to a temporary file, returning its path."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b64mod.b64decode(base64_str))
        return path
    except Exception as e:
        logger.error(f"Failed to write temp file for {prefix}: {e}")
        try:
            os.remove(path)
        except OSError:
            pass
        raise e


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

    async def find_customer_reference_local() -> dict:
        nonlocal cached_ref_signature, cached_ref_photo
        async with AsyncSessionLocal() as session:
            doc_result = await session.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = doc_result.scalar_one_or_none()
            if not doc:
                return {"matched": False, "reason": "document_not_found"}

            customer_ref = None
            if doc.customer_id:
                ref_result = await session.execute(
                    select(CustomerReference).where(CustomerReference.customer_id == doc.customer_id)
                )
                customer_ref = ref_result.scalar_one_or_none()

            if not customer_ref:
                id_val = (
                    validated_data.get("id_number") or 
                    validated_data.get("passport_number") or 
                    validated_data.get("document_number")
                )
                if id_val:
                    ref_result = await session.execute(
                        select(CustomerReference).where(
                            (CustomerReference.national_id == str(id_val)) |
                            (CustomerReference.customer_id == str(id_val))
                        )
                    )
                    customer_ref = ref_result.scalar_one_or_none()

                if not customer_ref:
                    name_val = validated_data.get("full_name") or validated_data.get("name")
                    if name_val:
                        ref_result = await session.execute(
                            select(CustomerReference).where(
                                CustomerReference.full_name.ilike(str(name_val).strip())
                            )
                        )
                        customer_ref = ref_result.scalars().first()

            if not customer_ref:
                return {"matched": False, "reason": "no_customer_reference_found"}

            # Link customer reference
            if not doc.customer_id:
                doc.customer_id = customer_ref.customer_id
                await session.commit()

            cached_ref_signature = customer_ref.reference_signature
            cached_ref_photo = customer_ref.reference_photo

            return {
                "matched": True,
                "customer_id": customer_ref.customer_id,
                "has_doc_signature": bool(validated_data.get("signature_image")),
                "has_ref_signature": bool(customer_ref.reference_signature),
                "has_doc_photo": bool(validated_data.get("photo_image")),
                "has_ref_photo": bool(customer_ref.reference_photo)
            }

    async def verify_signature_local(customer_id: str) -> dict:
        doc_sig_b64 = validated_data.get("signature_image")
        ref_sig_b64 = cached_ref_signature

        if not ref_sig_b64:
            # Fallback reload just in case
            async with AsyncSessionLocal() as session:
                ref_res = await session.execute(
                    select(CustomerReference).where(CustomerReference.customer_id == customer_id)
                )
                c_ref = ref_res.scalar_one_or_none()
                if c_ref:
                    ref_sig_b64 = c_ref.reference_signature

        if not doc_sig_b64 or not ref_sig_b64:
            return {"status": "skipped", "reason": "missing_images"}

        doc_sig_path = None
        ref_sig_path = None
        try:
            doc_sig_path = save_base64_to_temp_file(doc_sig_b64, "auto_doc_sig_", ".png")
            ref_sig_path = save_base64_to_temp_file(ref_sig_b64, "auto_ref_sig_", ".png")

            from utils.signature_verifier import run_verification_pipeline
            sig_pipeline_result = await run_verification_pipeline(doc_sig_path, ref_sig_path)
            return sig_pipeline_result
        finally:
            for p in (doc_sig_path, ref_sig_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    async def verify_face_local(customer_id: str) -> dict:
        doc_photo_b64 = validated_data.get("photo_image")
        ref_photo_b64 = cached_ref_photo

        if not ref_photo_b64:
            # Fallback reload just in case
            async with AsyncSessionLocal() as session:
                ref_res = await session.execute(
                    select(CustomerReference).where(CustomerReference.customer_id == customer_id)
                )
                c_ref = ref_res.scalar_one_or_none()
                if c_ref:
                    ref_photo_b64 = c_ref.reference_photo

        if not doc_photo_b64 or not ref_photo_b64:
            return {"status": "skipped", "reason": "missing_images"}

        doc_photo_path = None
        ref_photo_path = None
        try:
            doc_photo_path = save_base64_to_temp_file(doc_photo_b64, "auto_doc_photo_", ".png")
            ref_photo_path = save_base64_to_temp_file(ref_photo_b64, "auto_ref_photo_", ".png")

            from utils.face_verifier import run_face_verification_pipeline
            face_pipeline_result = await run_face_verification_pipeline(doc_photo_path, ref_photo_path)
            return face_pipeline_result
        finally:
            for p in (doc_photo_path, ref_photo_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    async def execute_direct_fallback() -> dict:
        logger.info(f"[AutoVerifier] Running direct fallback verification.")
        ref_status = await find_customer_reference_local()
        if not ref_status.get("matched"):
            return {"status": "skipped", "reason": ref_status.get("reason", "no_reference")}

        c_id = ref_status["customer_id"]
        sig_res = None
        face_res = None

        if ref_status["has_doc_signature"] and ref_status["has_ref_signature"]:
            try:
                sig_res = await verify_signature_local(c_id)
            except Exception as e:
                logger.error(f"[AutoVerifier] Direct signature verifier failed: {e}")

        if ref_status["has_doc_photo"] and ref_status["has_ref_photo"]:
            try:
                face_res = await verify_face_local(c_id)
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

        # Define tools schema for Auto-Verifier Agent
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "find_customer_reference",
                    "description": "Searches the database for a matching customer reference and links it to the document.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "verify_signature",
                    "description": "Compares extracted document signature against the customer reference signature using DINOv2 verification pipeline.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "The customer reference ID."
                            }
                        },
                        "required": ["customer_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "verify_face",
                    "description": "Compares extracted document photo against the customer reference photo using parallel face verification pipelines.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "The customer reference ID."
                            }
                        },
                        "required": ["customer_id"]
                    }
                }
            }
        ]

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
                    result = await find_customer_reference_local()
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
                    signature_result = await verify_signature_local(c_id)

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
                    photo_result = await verify_face_local(c_id)

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

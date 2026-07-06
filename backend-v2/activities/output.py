import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from tools.output import OUTPUT_TOOLS, persist_final_extraction
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
async def output_activity(
    document_id: str, 
    doc_type: str, 
    validated_data: dict, 
    reviewer_result: dict, 
    confidence_score: float,
    field_confidences: dict = None,
    fraud_check: dict = None,
    raw_extracted: dict = None,
    signature_verification: dict = None,
    photo_verification: dict = None
) -> dict:
    """
    Step 7 — Output.
    Persists document validation results to database using the Output Agent.
    """
    try:
        logger.info(f"[Document {document_id}] Starting output activity")

        # Extract corrections if any
        corrections = reviewer_result.get("corrections")

        if not settings.OUTPUT_AGENT_ID:
            logger.warning(f"[Document {document_id}] OUTPUT_AGENT_ID not set. Falling back to direct database persistence.")
            return await persist_final_extraction(
                document_id, doc_type, raw_extracted, validated_data, confidence_score,
                field_confidences, fraud_check, signature_verification, photo_verification, corrections
            )

        # Use imported tools schema
        tools = OUTPUT_TOOLS

        # Remove massive base64 images from the prompt to avoid overwhelming the LLM
        prompt_validated_data = validated_data.copy() if validated_data else {}
        prompt_validated_data.pop("signature_image", None)
        prompt_validated_data.pop("photo_image", None)

        prompt_raw_extracted = raw_extracted.copy() if raw_extracted else {}
        prompt_raw_extracted.pop("signature_image", None)
        prompt_raw_extracted.pop("photo_image", None)

        prompt = (
            f"You are the Output Agent. We need to save the final extraction results and mark document '{document_id}' as completed.\n"
            f"Please call the `persist_final_extraction` tool with the following payloads:\n\n"
            f"- document_id: '{document_id}'\n"
            f"- doc_type: '{doc_type}'\n"
            f"- raw_extracted: {json.dumps(prompt_raw_extracted)}\n"
            f"- validated_data: {json.dumps(prompt_validated_data)}\n"
            f"- confidence_score: {confidence_score}\n"
            f"- field_confidences: {json.dumps(field_confidences or {})}\n"
            f"- fraud_check: {json.dumps(fraud_check or {})}\n"
            f"- signature_verification: {json.dumps(signature_verification or {})}\n"
            f"- photo_verification: {json.dumps(photo_verification or {})}\n"
            f"- corrections: {json.dumps(corrections or {})}\n\n"
            f"Output a JSON object matching exactly this schema:\n"
            f"{{\n"
            f"  \"success\": bool,\n"
            f"  \"document_id\": str,\n"
            f"  \"final_data\": dict\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Output Agent ({settings.OUTPUT_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.OUTPUT_AGENT_ID,
            messages=messages,
            tools=tools
        )
        message = response.choices[0].message

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Output Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "persist_final_extraction":
                    logger.info(f"[Document {document_id}] Executing persist_final_extraction tool")
                    
                    args = json.loads(tool_call.function.arguments)
                    
                    # Pop out massive base64 images from log prints
                    log_args = args.copy()
                    for f in ["signature_image", "photo_image"]:
                        if f in log_args.get("validated_data", {}):
                            log_args["validated_data"][f] = "<base64_hidden>"
                        if f in log_args.get("raw_extracted", {}):
                            log_args["raw_extracted"][f] = "<base64_hidden>"
                            
                    logger.info(f"[Document {document_id}] Tool arguments: {log_args}")

                    # Since the tool parameters might not include signature/photo verification if they were skipped,
                    # we use the arguments passed to the activity as fallback defaults.
                    t_doc_type = args.get("doc_type", doc_type)

                    # Merge validated_data and raw_extracted to preserve any fields (like base64 images) that were popped
                    t_validated_data = validated_data.copy() if validated_data else {}
                    if "validated_data" in args and isinstance(args["validated_data"], dict):
                        t_validated_data.update(args["validated_data"])

                    t_raw_extracted = raw_extracted.copy() if raw_extracted else {}
                    if "raw_extracted" in args and isinstance(args["raw_extracted"], dict):
                        t_raw_extracted.update(args["raw_extracted"])

                    t_confidence_score = args.get("confidence_score", confidence_score)
                    t_field_confidences = args.get("field_confidences", field_confidences)
                    t_fraud_check = args.get("fraud_check", fraud_check)
                    t_signature_verification = args.get("signature_verification", signature_verification)
                    t_photo_verification = args.get("photo_verification", photo_verification)
                    t_corrections = args.get("corrections", corrections)

                    result = await persist_final_extraction(
                        document_id=document_id,
                        doc_type=t_doc_type,
                        raw_extracted=t_raw_extracted,
                        validated_data=t_validated_data,
                        confidence_score=t_confidence_score,
                        field_confidences=t_field_confidences,
                        fraud_check=t_fraud_check,
                        signature_verification=t_signature_verification,
                        photo_verification=t_photo_verification,
                        corrections=t_corrections
                    )

                    messages.append({
                        "role": "tool",
                        "name": "persist_final_extraction",
                        "content": json.dumps({"success": result.get("success", False), "document_id": document_id}),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Output Agent with tool result")
            response = client.agents.complete(
                agent_id=settings.OUTPUT_AGENT_ID,
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
                    "Based on the tool output, please output the final output verdict "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"success\": bool,\n"
                    "  \"document_id\": str,\n"
                    "  \"final_data\": {}\n"
                    "}"
                )
            })
            response = client.agents.complete(
                agent_id=settings.OUTPUT_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        return parsed

    except Exception as e:
        logger.error(f"[Document {document_id}] Output failed: {str(e)}")
        from db.operations import update_error
        await update_error(document_id, {"error": str(e), "stage": "output"})
        raise

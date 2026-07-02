import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData
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


async def _persist_final_extraction_local(
    document_id: str, 
    doc_type: str, 
    raw_extracted: dict, 
    validated_data: dict, 
    confidence_score: float, 
    field_confidences: dict, 
    fraud_check: dict, 
    signature_verification: dict, 
    photo_verification: dict, 
    corrections: dict
) -> dict:
    """Original local persistence logic."""
    final_data = validated_data.copy()
    if corrections:
        final_data.update(corrections)
        
    async with AsyncSessionLocal() as session:
        # Check if ExtractedData exists
        result = await session.execute(select(ExtractedData).where(ExtractedData.document_id == document_id))
        extracted_record = result.scalar_one_or_none()
        
        raw_payload = {
            "raw_fields": raw_extracted or {},
            "field_confidences": field_confidences or {}
        }
        
        if not extracted_record:
            extracted_record = ExtractedData(
                document_id=document_id,
                raw_extracted=raw_payload,
                validated_data=final_data,
                confidence_score=confidence_score,
                reviewer_corrections=corrections,
                fraud_check=fraud_check,
                signature_verification=signature_verification,
                photo_verification=photo_verification
            )
            session.add(extracted_record)
        else:
            extracted_record.validated_data = final_data
            extracted_record.confidence_score = confidence_score
            extracted_record.reviewer_corrections = corrections
            extracted_record.raw_extracted = raw_payload
            if fraud_check:
                extracted_record.fraud_check = fraud_check
            if signature_verification:
                extracted_record.signature_verification = signature_verification
            if photo_verification:
                extracted_record.photo_verification = photo_verification
            
        # Update Document
        doc_result = await session.execute(select(Document).where(Document.id == document_id))
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.status = "completed"
            doc.doc_type = doc_type
            
        await session.commit()
        
    return {
        "success": True, 
        "document_id": document_id, 
        "final_data": final_data
    }


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
            return await _persist_final_extraction_local(
                document_id, doc_type, raw_extracted, validated_data, confidence_score,
                field_confidences, fraud_check, signature_verification, photo_verification, corrections
            )

        # Define persistence tool for Output Agent
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "persist_final_extraction",
                    "description": "Persists raw extracted data, validated data, reviewer corrections, OCR confidences, fraud check, and auto-verification results to the database, completing the document workflow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string", "description": "The document ID."},
                            "doc_type": {"type": "string", "description": "The classified document type."},
                            "raw_extracted": {"type": "object", "description": "The raw extracted dictionary."},
                            "validated_data": {"type": "object", "description": "The validated data dictionary."},
                            "confidence_score": {"type": "number", "description": "Average OCR confidence."},
                            "field_confidences": {"type": "object", "description": "Individual field confidences dictionary."},
                            "fraud_check": {"type": "object", "description": "Identity proofing results dictionary."},
                            "signature_verification": {"type": "object", "description": "Signature verification results dictionary."},
                            "photo_verification": {"type": "object", "description": "Face photo verification results dictionary."},
                            "corrections": {"type": "object", "description": "Human reviewer corrections dictionary."}
                        },
                        "required": ["document_id", "doc_type", "raw_extracted", "validated_data", "confidence_score"]
                    }
                }
            }
        ]

        prompt = (
            f"You are the Output Agent. We need to save the final extraction results and mark document '{document_id}' as completed.\n"
            f"Please call the `persist_final_extraction` tool with all provided validation and verification payloads.\n\n"
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
                    t_raw_extracted = args.get("raw_extracted", raw_extracted)
                    t_validated_data = args.get("validated_data", validated_data)
                    t_confidence_score = args.get("confidence_score", confidence_score)
                    t_field_confidences = args.get("field_confidences", field_confidences)
                    t_fraud_check = args.get("fraud_check", fraud_check)
                    t_signature_verification = args.get("signature_verification", signature_verification)
                    t_photo_verification = args.get("photo_verification", photo_verification)
                    t_corrections = args.get("corrections", corrections)

                    result = await _persist_final_extraction_local(
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

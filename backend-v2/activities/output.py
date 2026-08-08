import logging
import mistralai.workflows as workflows
from tools.output import persist_final_extraction

logger = logging.getLogger(__name__)

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
    vllm_fallback: dict = None,
    signature_verification: dict = None,
    photo_verification: dict = None
) -> dict:
    """
    Step 7 — Output (Direct Function Call).

    Persists document validation results to the database using the
    persist_final_extraction tool.

    Previously routed through the Output Agent, but since the agent only
    called a single deterministic tool, this now calls the tool directly
    to eliminate ~4-10s of unnecessary LLM latency.
    """
    try:
        logger.info(f"[Document {document_id}] Starting output activity (direct mode)")

        # Extract corrections if any
        corrections = reviewer_result.get("corrections")

        result = await persist_final_extraction(
            document_id=document_id,
            doc_type=doc_type,
            raw_extracted=raw_extracted,
            validated_data=validated_data,
            confidence_score=confidence_score,
            field_confidences=field_confidences,
            fraud_check=fraud_check,
            vllm_fallback=vllm_fallback,
            signature_verification=signature_verification,
            photo_verification=photo_verification,
            corrections=corrections
        )

        logger.info(f"[Document {document_id}] Output activity complete. Success: {result.get('success')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Output failed: {str(e)}")
        from db.operations import update_error
        await update_error(document_id, {"error": str(e), "stage": "output"})
        raise


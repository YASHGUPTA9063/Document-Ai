"""
Output Activity
================
Persists the final validated and verified document data to the database.

Runs as a direct function call — the Output Agent only ever invoked a single
deterministic tool (`persist_final_extraction`), so routing it through the LLM
added ~4-10s of latency for no decision-making. The prompt file
(platform_core/prompts/output.md) is retained for reference but unused.
"""

import logging
import db.operations as db
from tools.output import persist_final_extraction

logger = logging.getLogger(__name__)


async def output_activity(document_id: str, pipeline_context: dict) -> dict:
    """
    Step 8 — Output (direct call).
    Finalizes the document processing pipeline by persisting the results to the database.
    """
    try:
        logger.info(f"[Document {document_id}] Starting output activity (direct mode)")

        reviewer_result = pipeline_context.get("reviewer_result") or {}
        auto_verify_result = pipeline_context.get("auto_verify_result") or {}

        result = await persist_final_extraction(
            document_id=document_id,
            doc_type=pipeline_context.get("doc_type", "unknown"),
            raw_extracted=pipeline_context.get("raw_extracted") or {},
            validated_data=pipeline_context.get("validated_data") or {},
            confidence_score=pipeline_context.get("confidence_score", 0.0),
            field_confidences=pipeline_context.get("field_confidences") or {},
            fraud_check=pipeline_context.get("fraud_check") or {},
            signature_verification=auto_verify_result.get("signature") or {},
            photo_verification=auto_verify_result.get("photo") or {},
            corrections=reviewer_result.get("corrections") or {},
        )

        logger.info(f"[Document {document_id}] Output result: success={result.get('success')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Output failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "output"})
        raise

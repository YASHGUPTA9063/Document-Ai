import logging
import mistralai.workflows as workflows
import db.operations as db

from tools.intake import check_document_duplicates

logger = logging.getLogger(__name__)

@workflows.activity()
async def intake_activity(document_id: str, filename: str) -> dict:
    """
    Step 1 — Intake (Direct Function Call).

    Checks if the uploaded document is a duplicate by file hash or filename.
    Previously routed through the Intake Agent, but since the agent only
    called a single deterministic tool, this now calls the tool directly
    to eliminate ~4-10s of unnecessary LLM latency.
    """
    try:
        logger.info(f"[Document {document_id}] Starting intake activity (direct mode)")

        result = await check_document_duplicates(document_id, filename)

        logger.info(f"[Document {document_id}] Intake result: {result}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Intake failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "intake"})
        raise

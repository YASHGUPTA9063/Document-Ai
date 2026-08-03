"""
Intake Activity
================
Checks if a newly uploaded document is a duplicate.

Runs as a direct function call. The Intake Agent only ever invoked a single
deterministic tool (`check_document_duplicates`) and made no decisions of its
own, so the LLM round-trip was ~4-10s of pure latency. The prompt file
(platform_core/prompts/intake.md) is retained for reference but unused.
"""

import logging
import db.operations as db
from tools.intake import check_document_duplicates

logger = logging.getLogger(__name__)


async def intake_activity(document_id: str, filename: str) -> dict:
    """
    Step 1 — Intake (direct call).

    Check if a document is a duplicate by file hash and filename.

    Returns:
        {"is_duplicate": bool, "existing_document_id": str | None}
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

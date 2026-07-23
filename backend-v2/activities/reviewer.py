"""
Reviewer Activity
==================
Evaluates processed documents for human review or auto-approval.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.reviewer import REVIEWER_TOOLS, get_review_context
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def reviewer_activity(document_id: str, confidence_score: float = 0.0, validated_data: dict = None) -> dict:
    """
    Step 6 — Reviewer.
    Determines if a document needs manual review or can be auto-approved.

    Args:
        document_id: The document being reviewed.
        confidence_score: OCR confidence score from the extractor.
        validated_data: Validated data from the validator step.
    """
    try:
        logger.info(f"[Document {document_id}] Starting reviewer activity")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("reviewer")

        # Capture these from the pipeline context for the tool closure
        _confidence = confidence_score
        _validated = validated_data or {}

        async def execute_tool(name: str, args: dict):
            if name == "get_review_context":
                logger.info(f"[Document {document_id}] Executing get_review_context")
                return get_review_context(_confidence, _validated)
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"Please evaluate document '{document_id}' and determine if it requires "
            f"manual human review or can be automatically approved.\n"
            f"Call the `get_review_context` tool with document_id='{document_id}' "
            f"to get the document's validation details and confidence score."
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=REVIEWER_TOOLS,
            tool_executor=execute_tool,
            temperature=0.2,
        )

        logger.info(f"[Document {document_id}] Review result: approved={result.get('approved')}, needs_review={result.get('needs_review')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Reviewer failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "reviewer"})
        raise

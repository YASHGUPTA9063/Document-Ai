import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
import db.operations as db
from schemas.documents import ReviewerDecisionRequest

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

@workflows.activity()
async def reviewer_activity(document_id: str, validated_data: dict, confidence_score: float) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting reviewer activity. Confidence: {confidence_score}")
        
        if confidence_score >= 0.80:
            return {"approved": True, "corrections": None, "auto_approved": True}

        # Optional: Call Reviewer Agent to summarize
        try:
            summary_response = client.agents.complete(
                agent_id=settings.REVIEWER_AGENT_ID,
                messages=[{"role": "user", "content": f"Summarize this data for review: {json.dumps(validated_data)}"}]
            )
            summary = summary_response.choices[0].message.content
            logger.info(f"[Document {document_id}] Agent Review Summary: {summary}")
        except Exception as e:
            logger.warning(f"[Document {document_id}] Failed to get reviewer summary: {e}")

        # We do not pause here anymore in the activity.
        # The pause logic using wait_for_input will be moved to the InteractiveWorkflow execution block.
        # This activity just calls the summary agent.
        
        return {
            "needs_review": True,
            "summary": summary if 'summary' in locals() else None
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Reviewer failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "reviewer"})
        raise

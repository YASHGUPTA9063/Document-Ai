import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

@workflows.activity()
async def classifier_activity(document_id: str, file_path: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity")
        
        ocr_result = extract_with_ocr(file_path, "unknown")
        raw_text = ocr_result.get("raw_text", "")
        
        response = client.agents.complete(
            agent_id=settings.CLASSIFIER_AGENT_ID,
            messages=[{"role": "user", "content": raw_text}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        return {
            "doc_type": parsed.get("doc_type", "Others"),
            "confidence": parsed.get("confidence", 0.0),
            "reasoning": parsed.get("reasoning", "")
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Classifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "classifier"})
        raise

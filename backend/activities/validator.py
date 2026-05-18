import json
import logging
import mistralai.workflows as workflows
from mistralai import Mistral
from backend.config import settings
import backend.db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

@workflows.activity()
async def validator_activity(document_id: str, extracted_data: dict, doc_type: str, ocr_confidence: float) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting validator activity")
        
        json_data = json.dumps(extracted_data)
        
        response = client.agents.complete(
            agent_id=settings.VALIDATOR_AGENT_ID,
            messages=[{"role": "user", "content": f"Validate this extracted data: {json_data}"}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        return {
            "is_valid": parsed.get("is_valid", False),
            "confidence_score": ocr_confidence, # Pass through the OCR native confidence score
            "validation_errors": parsed.get("validation_errors", []),
            "validated_data": parsed.get("validated_data", extracted_data)
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

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
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")
        
        if doc_type.lower() == "invoice":
            ocr_result = extract_with_ocr(file_path, doc_type)
            raw_text = ocr_result.get("raw_text", "")
            ocr_confidence = ocr_result.get("confidence", 0.0)
            
            response = client.agents.complete(
                agent_id=settings.EXTRACTOR_AGENT_ID,
                messages=[{"role": "user", "content": raw_text}],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            fields = json.loads(content)
            
            return {
                "fields": fields,
                "raw_ocr": raw_text,
                "confidence": ocr_confidence # Bubble up OCR native confidence
            }
        else:
            return {
                "message": "Extractor not yet implemented for this document type",
                "doc_type": doc_type,
                "fields": {},
                "confidence": 0.0,
                "raw_ocr": ""
            }
            
    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

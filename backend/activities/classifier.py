import os
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

def get_supported_doc_types() -> dict:
    # Strictly load document types from user-configured templates only
    types_map = {}
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if os.path.exists(templates_path):
        try:
            with open(templates_path, "r") as f:
                templates = json.load(f)
                for key in templates.keys():
                    normalized_key = key.lower().replace(" ", "_")
                    # e.g., "purchase_order" -> "Purchase Order"
                    display_name = " ".join(word.capitalize() for word in normalized_key.split("_"))
                    types_map[normalized_key] = display_name
        except Exception as e:
            logger.error(f"Failed to read templates in classifier: {e}")
    return types_map


@workflows.activity()
async def classifier_activity(document_id: str, file_path: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity")
        
        ocr_result = extract_with_ocr(file_path, "unknown")
        raw_text = ocr_result.get("raw_text", "")
        
        # Get dynamic list of supported document types
        types_map = get_supported_doc_types()
        allowed_types = list(types_map.values()) + ["Others"]
        
        prompt = (
            f"You are an expert document classifier. Analyze the following document text and classify it into exactly one of "
            f"the supported document types.\n\n"
            f"Supported Document Types:\n"
            + "\n".join(f"- {t}" for t in allowed_types) + "\n\n"
            f"Document Content (extracted via OCR):\n{raw_text}\n\n"
            f"Your response must be a JSON object with the following fields:\n"
            f"- 'doc_type': The selected document type. This MUST be one of the supported types listed above (case-sensitive, match exactly).\n"
            f"- 'confidence': A float between 0.0 and 1.0 representing your confidence in this classification.\n"
            f"- 'reasoning': A brief explanation of why you selected this document type."
        )
        
        response = client.agents.complete(
            agent_id=settings.CLASSIFIER_AGENT_ID,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        doc_type_returned = parsed.get("doc_type", "Others").strip()
        
        # Match returned type back to the formal display name or default to Others
        matched_doc_type = "Others"
        for key, display_name in types_map.items():
            if doc_type_returned.lower() in [key.lower(), display_name.lower(), key.replace("_", " ").lower()]:
                matched_doc_type = display_name
                break
                
        return {
            "doc_type": matched_doc_type,
            "confidence": parsed.get("confidence", 0.0),
            "reasoning": parsed.get("reasoning", "")
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Classifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "classifier"})
        raise


import os
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

def get_template_fields(doc_type: str) -> list:
    normalized = doc_type.lower().replace(" ", "_")
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if os.path.exists(templates_path):
        try:
            with open(templates_path, "r") as f:
                templates = json.load(f)
                return templates.get(normalized)
        except Exception as e:
            logger.error(f"Failed to read templates from {templates_path}: {e}")
    return None

@workflows.activity()
async def validator_activity(
    document_id: str, 
    extracted_data: dict, 
    doc_type: str, 
    ocr_confidence: float,
    field_confidences: dict = None
) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting validator activity")
        
        json_data = json.dumps(extracted_data)
        
        # Load custom templates if configured
        fields_list = get_template_fields(doc_type)
        if fields_list:
            fields_desc = []
            for f in fields_list:
                req_str = "Required" if f.get("required") else "Optional"
                fields_desc.append(f"- '{f['key']}' ({f['type']}, {req_str}): {f.get('description', '')}")
            fields_instruction = "\n".join(fields_desc)
            
            prompt = (
                f"You are a schema validator. We extracted data from a {doc_type} document.\n"
                f"Please validate the extracted data against this template schema:\n{fields_instruction}\n\n"
                f"Extracted Data:\n{json_data}\n\n"
                f"Your response must be a JSON object with keys:\n"
                f"- 'is_valid': boolean (true if all required fields are present and data types match)\n"
                f"- 'validation_errors': list of strings (e.g. \"Field 'tax_id' is required but missing\")\n"
                f"- 'validated_data': the updated validated JSON object."
            )
        else:
            prompt = f"Validate this extracted data: {json_data}"
        
        response = client.agents.complete(
            agent_id=settings.VALIDATOR_AGENT_ID,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        return {
            "is_valid": parsed.get("is_valid", False),
            "confidence_score": ocr_confidence, # Pass through the OCR native confidence score
            "validation_errors": parsed.get("validation_errors", []),
            "validated_data": parsed.get("validated_data", extracted_data),
            "field_confidences": field_confidences or {}
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

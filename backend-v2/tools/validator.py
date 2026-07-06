import os
import json
import logging
from config import settings

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
VALIDATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_validation_schema",
            "description": "Fetches the validation schema fields list for the given document type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string",
                        "description": "The classified document type (e.g. Invoice, PAN Card)."
                    }
                },
                "required": ["doc_type"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def get_template_fields(doc_type: str) -> list:
    normalized = doc_type.lower().replace(" ", "_")
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if os.path.exists(templates_path):
        try:
            with open(templates_path, "r") as f:
                templates = json.load(f)
                template_data = templates.get(normalized)
                if isinstance(template_data, dict):
                    return template_data.get("fields", [])
                elif isinstance(template_data, list):
                    return template_data
                return None
        except Exception as e:
            logger.error(f"Failed to read templates from {templates_path}: {e}")
    return None

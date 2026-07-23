import os
import json
import logging
from config import settings

logger = logging.getLogger(__name__)

TEMPLATES_FILE = os.path.join(settings.STORAGE_DIR, "templates.json")

DEFAULT_TEMPLATES = {}

def load_templates():
    """Load templates, handling both old (bare list) and new ({fields, is_kyc}) formats."""
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r") as f:
                raw = json.load(f)
                # Normalize: ensure each template entry is in the new dict format
                normalized = {}
                for key, value in raw.items():
                    if isinstance(value, list):
                        # Old format: bare list of fields
                        normalized[key] = {"fields": value, "is_kyc": False}
                    elif isinstance(value, dict):
                        # New format: already has fields + is_kyc
                        if "fields" not in value:
                            value["fields"] = []
                        if "is_kyc" not in value:
                            value["is_kyc"] = False
                        normalized[key] = value
                    else:
                        normalized[key] = {"fields": [], "is_kyc": False}
                return normalized
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
    return DEFAULT_TEMPLATES

def save_templates_to_file(templates_data):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates_data, f, indent=2)

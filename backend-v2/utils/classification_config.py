import os
import json
from config import settings, SUPPORTED_DOCUMENT_TYPES

CLASSIFICATION_CONFIG_FILE = os.path.join(settings.STORAGE_DIR, "classification_config.json")

def load_classification_config() -> list[str]:
    if os.path.exists(CLASSIFICATION_CONFIG_FILE):
        try:
            with open(CLASSIFICATION_CONFIG_FILE, "r") as f:
                config = json.load(f)
                if isinstance(config, list):
                    # Ensure all entries are stripped and not empty
                    return [t.strip() for t in config if t.strip()]
        except Exception as e:
            pass
    return SUPPORTED_DOCUMENT_TYPES.copy()

def save_classification_config(doc_types: list[str]):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    cleaned_types = [t.strip() for t in doc_types if t.strip()]
    with open(CLASSIFICATION_CONFIG_FILE, "w") as f:
        json.dump(cleaned_types, f, indent=2)

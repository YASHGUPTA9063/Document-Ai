import os
import json
import logging

from config import settings

logger = logging.getLogger(__name__)

VLLM_SETTINGS_FILE = os.path.join(settings.STORAGE_DIR, "vllm_settings.json")

DEFAULT_VLLM_SETTINGS = {
    "enabled": True,
    "confidence_threshold": 75,  # percentage (0-100)
    "trigger_on_missing": True,  # re-extract when required field is missing/empty/null
    "trigger_on_low_confidence": True,  # re-extract when required field confidence < threshold
}


def load_vllm_settings() -> dict:
    """Load vLLM fallback settings from the JSON settings file."""
    if os.path.exists(VLLM_SETTINGS_FILE):
        try:
            with open(VLLM_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged = {**DEFAULT_VLLM_SETTINGS, **data}
                return merged
        except Exception as e:
            logger.error(f"Failed to load vLLM settings from {VLLM_SETTINGS_FILE}: {e}")
    return dict(DEFAULT_VLLM_SETTINGS)


def save_vllm_settings(config: dict):
    """Save vLLM fallback settings to the JSON settings file."""
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(VLLM_SETTINGS_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"vLLM settings saved: {config}")

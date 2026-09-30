"""
Document Checklist Runtime Config
=================================
Load/save helpers for `storage/checklist_config.json`, which holds the document
types that skip the Step 3.2 batch checklist.

A skipped type is still classified and processed like any other; it is simply
never asked for. It drops off the required list, so a batch is not held waiting
for it, and a batch made up of nothing but skipped types walks straight through.

A missing or malformed file falls back to the defaults, never to an error — the
checklist must not be able to take the pipeline down.
"""

import os
import json
import logging

from config import settings

logger = logging.getLogger(__name__)

CHECKLIST_CONFIG_FILE = os.path.join(settings.STORAGE_DIR, "checklist_config.json")

# The KYC application form is uploaded on its own, ahead of the identity
# documents, so requiring it would hold every document batch waiting for it.
DEFAULT_SKIP_TYPES = ["kyc_form"]


def _normalize(doc_types) -> list[str]:
    """Same key shape the classifier uses, de-duplicated, order preserved."""
    cleaned = []
    for entry in doc_types:
        if not isinstance(entry, str):
            continue
        key = entry.strip().lower().replace(" ", "_")
        if key and key not in cleaned:
            cleaned.append(key)
    return cleaned


def load_checklist_config() -> dict:
    if os.path.exists(CHECKLIST_CONFIG_FILE):
        try:
            with open(CHECKLIST_CONFIG_FILE, "r") as f:
                stored = json.load(f)
            if isinstance(stored, dict) and isinstance(stored.get("skip_types"), list):
                return {"skip_types": _normalize(stored["skip_types"])}
        except Exception as e:
            logger.warning(f"Failed to read {CHECKLIST_CONFIG_FILE}, using defaults: {e}")
    return {"skip_types": DEFAULT_SKIP_TYPES.copy()}


def save_checklist_config(config: dict) -> dict:
    """Persist the skip list; returns the resulting effective config."""
    skip_types = config.get("skip_types")
    if not isinstance(skip_types, list):
        raise ValueError("'skip_types' must be a list of document type keys")

    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(CHECKLIST_CONFIG_FILE, "w") as f:
        json.dump({"skip_types": _normalize(skip_types)}, f, indent=2)
    return load_checklist_config()

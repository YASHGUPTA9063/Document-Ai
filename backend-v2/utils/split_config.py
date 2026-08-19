"""
Document Splitting Runtime Config
=================================
Load/save helpers for `storage/splitting_config.json`, the runtime overrides
for the Step 1.5 packet splitter.

Precedence matches the other settings files in this package (see
`utils/classification_config.py`): the values in `config.Settings` are the
defaults, and any key present in the JSON file overrides them at read time. A
missing or malformed file falls back to the env defaults, never to an error —
the splitter must not be able to take the pipeline down.
"""

import os
import json
import logging

from config import settings

logger = logging.getLogger(__name__)

SPLIT_CONFIG_FILE = os.path.join(settings.STORAGE_DIR, "splitting_config.json")

# key -> (settings attribute, coercion callable)
_FIELDS = {
    "enabled":              ("ENABLE_DOC_SPLITTING", bool),
    "confidence_threshold": ("SPLIT_CONFIDENCE_THRESHOLD", float),
    "page_batch_size":      ("SPLIT_PAGE_BATCH_SIZE", int),
    "max_pages":            ("SPLIT_MAX_PAGES", int),
    "require_review":       ("SPLIT_REQUIRE_REVIEW", bool),
    "merge_orphans":        ("SPLIT_MERGE_ORPHANS", bool),
}


def _defaults() -> dict:
    return {key: getattr(settings, attr) for key, (attr, _) in _FIELDS.items()}


def load_split_config() -> dict:
    """Env defaults, overlaid with whatever `splitting_config.json` overrides."""
    config = _defaults()
    if not os.path.exists(SPLIT_CONFIG_FILE):
        return config

    try:
        with open(SPLIT_CONFIG_FILE, "r") as f:
            stored = json.load(f)
        if not isinstance(stored, dict):
            return config
    except Exception as e:
        logger.warning(f"Failed to read {SPLIT_CONFIG_FILE}, using env defaults: {e}")
        return config

    for key, (_, coerce) in _FIELDS.items():
        if key in stored and stored[key] is not None:
            try:
                config[key] = coerce(stored[key])
            except (TypeError, ValueError):
                logger.warning(f"Ignoring invalid splitting config value for '{key}': {stored[key]!r}")

    # Guard against values that would break the splitter outright.
    config["confidence_threshold"] = min(1.0, max(0.0, config["confidence_threshold"]))
    config["page_batch_size"] = max(1, config["page_batch_size"])
    config["max_pages"] = max(2, config["max_pages"])
    return config


def save_split_config(config: dict) -> dict:
    """Persist only the recognised keys; returns the resulting effective config."""
    cleaned = {}
    for key, (_, coerce) in _FIELDS.items():
        if key in config and config[key] is not None:
            try:
                cleaned[key] = coerce(config[key])
            except (TypeError, ValueError):
                raise ValueError(f"Invalid value for '{key}': {config[key]!r}")

    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(SPLIT_CONFIG_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)
    return load_split_config()

"""
Document Splitting Runtime Config
=================================
Load/save helpers for `storage/splitting_config.json`, the runtime tuning knobs
for the Step 1.5 packet splitter.

Precedence matches the other settings files in this package (see
`utils/classification_config.py`): the values in `config.Settings` are the
defaults, and any key present in the JSON file overrides them at read time. A
missing or malformed file falls back to the env defaults, never to an error —
the splitter must not be able to take the pipeline down.

The one exception is `enabled`, which is read-only here and comes from
ENABLE_DOC_SPLITTING alone. Splitting is switched on and off from the
environment only — the same way ENABLE_DOC_CHECKLIST governs Step 3.2 — so
there is exactly one place to look when asking whether the stage runs. It is
still reported by `load_split_config()` so callers have one source for "is
splitting on", and any `enabled` key sent to `save_split_config()` is ignored.
"""

import os
import json
import logging

from config import settings

logger = logging.getLogger(__name__)

SPLIT_CONFIG_FILE = os.path.join(settings.STORAGE_DIR, "splitting_config.json")

# Runtime-overridable key -> (settings attribute, coercion callable).
# `enabled` is deliberately absent: see the module docstring.
_FIELDS = {
    "confidence_threshold": ("SPLIT_CONFIDENCE_THRESHOLD", float),
    "page_batch_size":      ("SPLIT_PAGE_BATCH_SIZE", int),
    "max_pages":            ("SPLIT_MAX_PAGES", int),
    "require_review":       ("SPLIT_REQUIRE_REVIEW", bool),
    "merge_orphans":        ("SPLIT_MERGE_ORPHANS", bool),
}


def _defaults() -> dict:
    return {key: getattr(settings, attr) for key, (attr, _) in _FIELDS.items()}


def load_split_config() -> dict:
    """Env defaults, overlaid with whatever `splitting_config.json` overrides.

    `enabled` is always the env flag and is never read from the file.
    """
    config = _defaults()
    config["enabled"] = bool(settings.ENABLE_DOC_SPLITTING)
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
    """Persist only the recognised keys; returns the resulting effective config.

    `enabled` is not one of them — a client that sends it is quietly ignored
    rather than rejected, so the switch stays purely an env concern.
    """
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

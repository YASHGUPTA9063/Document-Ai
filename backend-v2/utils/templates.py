"""
Extraction Template Storage
===========================
Load/save helpers for the per-document-type extraction templates that drive
`tools/extractor.py` and the Templates UI.

Extracted verbatim from branch-vm3's main.py so the API layer can be split
into routers without duplicating the logic. Behaviour is unchanged: the same
normalization of legacy formats, the same `use_vlm` and field-`weight`
defaults.
"""

import os
import re
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
                        normalized[key] = {"fields": value, "is_kyc": False, "id_marker": None}
                    elif isinstance(value, dict):
                        # New format: already has fields + is_kyc + use_vlm
                        if "fields" not in value:
                            value["fields"] = []
                        if "is_kyc" not in value:
                            value["is_kyc"] = False
                        if "use_vlm" not in value:
                            value["use_vlm"] = False
                        # id_marker: optional regex used by the packet splitter to
                        # sanity-check that a segment really is this document type.
                        # Absent (the common case) means "no marker rule for this type".
                        if not value.get("id_marker"):
                            value["id_marker"] = None
                        normalized[key] = value
                    else:
                        normalized[key] = {"fields": [], "is_kyc": False, "use_vlm": False, "id_marker": None}
                # Normalize field-level defaults: ensure every field has a weight
                for tpl in normalized.values():
                    for field in tpl.get("fields", []):
                        if "weight" not in field or field["weight"] is None:
                            field["weight"] = 80
                return normalized
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
    return DEFAULT_TEMPLATES


def validate_id_markers(templates_data: dict) -> None:
    """
    Reject an unparseable `id_marker` regex at save time.

    The marker is compiled inside the splitter, where a bad pattern would fail a
    document mid-workflow with an opaque error. Failing here instead turns it
    into a 400 on the template save the author is looking at.
    """
    for name, tpl in (templates_data or {}).items():
        if not isinstance(tpl, dict):
            continue
        marker = tpl.get("id_marker")
        if not marker:
            continue
        try:
            re.compile(marker)
        except re.error as e:
            raise ValueError(f"Template '{name}' has an invalid id_marker regex: {e}")


def save_templates_to_file(templates_data):
    validate_id_markers(templates_data)
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates_data, f, indent=2)

import os
import json
from config import settings

CLAIM_REQUIREMENTS_FILE = os.path.join(settings.STORAGE_DIR, "claim_requirements.json")

DEFAULT_CLAIM_REQUIREMENTS = {
    "Health Insurance": [
        {"doc_type": "claim_form", "label": "Insurance Claim Form", "required": True},
        {"doc_type": "medical_report", "label": "Medical Report / Discharge Summary", "required": True},
        {"doc_type": "bills_invoices", "label": "Hospital / Medical Bills", "required": False},
        {"doc_type": "policy_document", "label": "Policy Document", "required": True},
        {"doc_type": "prescription_records", "label": "Prescription Records", "required": True},
        {"doc_type": "lab_reports", "label": "Lab Reports", "required": True},
        {"doc_type": "pan_card", "label": "ID Proof / PAN Card", "required": True},
        {"doc_type": "disability_certificate", "label": "Disability Certificate", "required": True},
        {"doc_type": "legal_letter", "label": "Police FIR / Legal Letter", "required": True},
    ],
    "Motor Insurance": [
        {"doc_type": "claim_form", "label": "Motor Claim Form", "required": True},
        {"doc_type": "bills_invoices", "label": "Repair Estimate / Garage Bill", "required": False},
        {"doc_type": "policy_document", "label": "Vehicle RC / Policy Document", "required": True},
        {"doc_type": "pan_card", "label": "Driving License / PAN Card", "required": True},
        {"doc_type": "legal_letter", "label": "Police FIR Copy", "required": True},
    ],
    "Life Insurance": [
        {"doc_type": "claim_form", "label": "Life Death Claim Form", "required": True},
        {"doc_type": "medical_report", "label": "Death Certificate / Medical Report", "required": True},
        {"doc_type": "policy_document", "label": "Original Policy Document", "required": True},
        {"doc_type": "pan_card", "label": "Nominee ID Proof / PAN Card", "required": True},
        {"doc_type": "legal_letter", "label": "Police FIR / Post-Mortem Report", "required": True},
    ],
    "default": [
        {"doc_type": "claim_form", "label": "Insurance Claim Form", "required": True},
        {"doc_type": "medical_report", "label": "Medical Report / Discharge Summary", "required": True},
        {"doc_type": "bills_invoices", "label": "Hospital / Medical Bills", "required": False},
        {"doc_type": "policy_document", "label": "Policy Document", "required": True},
        {"doc_type": "prescription_records", "label": "Prescription Records", "required": True},
        {"doc_type": "lab_reports", "label": "Lab Reports", "required": True},
        {"doc_type": "pan_card", "label": "ID Proof / PAN Card", "required": True},
        {"doc_type": "disability_certificate", "label": "Disability Certificate", "required": True},
        {"doc_type": "legal_letter", "label": "Police FIR / Legal Letter", "required": True},
    ]
}


def load_claim_requirements() -> dict:
    """Load claim document requirements from JSON storage file or return defaults."""
    if os.path.exists(CLAIM_REQUIREMENTS_FILE):
        try:
            with open(CLAIM_REQUIREMENTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CLAIM_REQUIREMENTS.copy()


def save_claim_requirements(config: dict):
    """Save updated claim requirements to storage."""
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(CLAIM_REQUIREMENTS_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_requirements_for_claim_type(claim_type: str) -> list[dict]:
    """
    Get the required document checklist for a given claim type.
    Falls back to case-insensitive, prefix/substring match or default list.
    """
    reqs = load_claim_requirements()
    if not claim_type or claim_type == "unknown":
        return reqs.get("default", DEFAULT_CLAIM_REQUIREMENTS["default"])

    if claim_type in reqs:
        return reqs[claim_type]

    norm = claim_type.strip().lower()
    for k, v in reqs.items():
        k_norm = k.lower()
        if k_norm == norm or norm in k_norm or k_norm in norm:
            return v

    return reqs.get("default", DEFAULT_CLAIM_REQUIREMENTS["default"])

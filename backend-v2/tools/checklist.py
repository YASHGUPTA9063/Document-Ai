"""
Checklist Tooling
=================
Pure helpers behind the Step 3.2 Checklist Agent. Everything here is
side-effect free and synchronous so the reconciliation can be unit-tested, and
so the pipeline still produces a verdict when the LLM is unavailable.

The required list is the live classification config — the same list the
Classifier Agent is given in Step 3 (`tools/classifier.get_supported_doc_types`).
Adding a type in Settings therefore adds a checklist line immediately; there is
deliberately no second place to keep in sync.
"""

import hashlib
import logging

from tools.classifier import get_supported_doc_types
from utils.checklist_config import load_checklist_config

logger = logging.getLogger(__name__)

# "others" is the classifier's escape hatch, not a document a user can be asked
# to upload, so it never appears on the checklist.
OTHERS_KEY = "others"


def skipped_types() -> set[str]:
    """
    Types that are classified like any other but never required in a batch.

    Configured in Settings → Document Checklist (`utils/checklist_config.py`);
    the KYC application form is there by default.
    """
    return set(load_checklist_config()["skip_types"])

# Statuses that mean a document will never produce a doc_type. Anything else
# without one is still on its way through the pipeline, and the batch is not
# ready to be judged yet.
TERMINAL_STATUSES = {"completed", "rejected", "failed", "deleted"}

# A split parent is a container, never a document in its own right — its
# children are what count towards the checklist.
EXCLUDED_STATUSES = {"deleted", "split"}


def build_required_types() -> list[dict]:
    """The configured classification types, as ordered checklist lines."""
    not_required = skipped_types() | {OTHERS_KEY}
    return [
        {"doc_type": key, "label": label}
        for key, label in get_supported_doc_types().items()
        if key not in not_required
    ]


def is_excluded(doc) -> bool:
    """Split parents and deleted rows are not part of the batch's contents."""
    return bool(getattr(doc, "is_split_parent", False)) or doc.status in EXCLUDED_STATUSES


def observed_type(doc) -> str:
    """
    The type a document contributes to the batch.

    Falls back to the splitter's hint so a child that is still queued behind its
    siblings already counts for the type the split assigned it — otherwise a
    packet containing every required document would still trip the gate purely
    because its children had not caught up yet.
    """
    return (doc.doc_type or doc.split_doc_type_hint or "").strip().lower()


def is_settled(doc) -> bool:
    """Has this document reached a point where its type will no longer change?"""
    return bool(doc.doc_type) or doc.status in TERMINAL_STATUSES


def pending_documents(documents: list) -> list:
    """Documents still in flight, i.e. ones that could yet supply a missing type."""
    return [d for d in documents if not is_excluded(d) and not is_settled(d)]


def only_skipped_types(documents: list) -> bool:
    """
    Is the batch made up of nothing but types that skip the checklist?

    Such a batch has no set to reconcile — judging it would report every
    required type as missing for an upload that was never meant to carry them.
    """
    types = {observed_type(d) for d in documents if not is_excluded(d)}
    return bool(types) and types <= skipped_types()


def reconcile(documents: list, required: list[dict] | None = None) -> dict:
    """
    Compare what the batch actually contains against what it should contain.

    This is the deterministic ground truth. The Checklist Agent is asked to
    explain it, never to decide it — a missing document is a set difference, and
    letting a model overrule that would be a regression dressed up as judgement.
    """
    required = required if required is not None else build_required_types()
    required_keys = {entry["doc_type"] for entry in required}

    seen: dict[str, list[str]] = {}
    unclassified: list[str] = []

    for doc in documents:
        if is_excluded(doc):
            continue
        doc_type = observed_type(doc)
        if not doc_type or doc_type == OTHERS_KEY:
            unclassified.append(doc.id)
            continue
        seen.setdefault(doc_type, []).append(doc.id)

    present = [
        {"doc_type": key, "label": _label_for(key, required), "document_ids": ids}
        for key, ids in seen.items()
        if key in required_keys
    ]
    present.sort(key=lambda entry: entry["doc_type"])

    missing = [entry for entry in required if entry["doc_type"] not in seen]
    extra = sorted(key for key in seen if key not in required_keys)

    return {
        "required": required,
        "present": present,
        "missing": missing,
        "extra": extra,
        "unclassified": unclassified,
        "complete": not missing,
    }


def _label_for(doc_type: str, required: list[dict]) -> str:
    for entry in required:
        if entry["doc_type"] == doc_type:
            return entry["label"]
    return doc_type.replace("_", " ").title()


def batch_signature(documents: list, required: list[dict]) -> str:
    """
    Fingerprint of "what the batch looks like right now".

    Covers both the types present and the required list, so editing the
    classification types in Settings re-opens the checklist for a batch that had
    already been judged complete under the old list.
    """
    types = sorted({observed_type(d) for d in documents if not is_excluded(d)} - {""})
    payload = "|".join(types) + "::" + "|".join(sorted(e["doc_type"] for e in required))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def format_checklist_prompt(result: dict, documents: list) -> str:
    """Render the reconciliation for the agent to summarise."""
    lines = ["DOCUMENTS IN THIS UPLOAD BATCH:"]
    for doc in documents:
        if is_excluded(doc):
            continue
        lines.append(
            f"  - {doc.filename} → {observed_type(doc) or 'unclassified'} (status: {doc.status})"
        )

    lines += ["", "REQUIRED DOCUMENT TYPES (from the classification config):"]
    for entry in result["required"]:
        state = "PRESENT" if any(p["doc_type"] == entry["doc_type"] for p in result["present"]) else "MISSING"
        lines.append(f"  - {entry['label']} ({entry['doc_type']}): {state}")

    if result["extra"]:
        lines += ["", "TYPES PRESENT BUT NOT ON THE CONFIGURED LIST:", "  " + ", ".join(result["extra"])]
    if result["unclassified"]:
        lines += ["", f"UNCLASSIFIED / 'others' DOCUMENTS: {len(result['unclassified'])}"]

    lines += [
        "",
        f"VERDICT (already computed, do not change it): "
        f"{'COMPLETE' if result['complete'] else 'INCOMPLETE'} — "
        f"{len(result['missing'])} of {len(result['required'])} required type(s) missing.",
        "",
        "Write the summary for the reviewer as per your instructions. Return ONLY the JSON object.",
    ]
    return "\n".join(lines)


def fallback_summary(result: dict) -> str:
    """Deterministic wording used when the Checklist Agent is not available."""
    if result["complete"]:
        return (
            f"All {len(result['required'])} configured document types are present in this "
            f"upload batch. Nothing is outstanding."
        )
    missing_labels = ", ".join(entry["label"] for entry in result["missing"])
    return (
        f"{len(result['missing'])} of {len(result['required'])} required document types have not "
        f"been uploaded in this batch: {missing_labels}. Upload the missing documents, or "
        f"continue anyway if they do not apply to this submission."
    )

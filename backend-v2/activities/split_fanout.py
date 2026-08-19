"""
Step 1.5b — Split Fan-Out
=========================
Takes the segments `activities/splitter.py` decided on, writes one PDF per
segment, creates a child Document row for each, and launches an independent
`document_processing_workflow` for every child.

Children are launched with:
  * `auto_split=False`     — a child can never re-split (recursion guard)
  * `preclassified_*`      — the segment's doc_type, so the child SKIPS Step 3
                             instead of paying for a classification the splitter
                             already did

The pre-classification is withheld — leaving the child to classify normally —
when the segment resolved to `others` or came in under the confidence threshold.
A boundary confirmed by a human is not the same thing as a type confirmed by a
human, so a weak type never silently drives extraction.

Idempotent on (parent_id, page_range): a retry of this activity adopts the
children it already created rather than duplicating them.
"""

import os
import asyncio
import hashlib
import logging

import mistralai.workflows as workflows

from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
from tools.classifier import get_supported_doc_types
from tools.splitter import OTHERS_KEY, Segment
from utils.split_config import load_split_config
import db.operations as db
import db.claim_operations as claim_db

logger = logging.getLogger(__name__)
client = get_mistral_client()


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _child_filename(parent_filename: str, segment: Segment, display_types: dict) -> str:
    stem = os.path.splitext(parent_filename)[0]
    display = display_types.get(segment.doc_type, segment.doc_type.replace("_", " ").title())
    return f"{stem} — {display} (p{segment.page_range_label}).pdf"


def _reusable_doc_type(segment: Segment, threshold: float) -> tuple[str, str]:
    """
    Should the child reuse this segment's classification, or classify itself?

    Returns (doc_type, skip_reason). An empty doc_type means "run Step 3".
    """
    if segment.doc_type == OTHERS_KEY:
        return "", "type resolved to others"
    if segment.min_confidence < threshold:
        return "", f"confidence {segment.min_confidence:.2f} below threshold {threshold:.2f}"
    return segment.doc_type, ""


@workflows.activity()
async def split_fanout_activity(document_id: str, filename: str, file_path: str,
                                segments: list[dict], pages: list[dict] | None = None) -> dict:
    """Materialise the segments as child documents and start their workflows."""
    logger.info(f"[Document {document_id}] Fanning out {len(segments)} split segments")

    threshold = load_split_config()["confidence_threshold"]
    display_types = get_supported_doc_types()

    parent = await db.get_document(document_id)
    customer_id = parent.customer_id if parent else None

    out_dir = os.path.join(settings.STORAGE_DIR, "splits", document_id)

    # Physical split. Done here rather than in the detection activity so nothing is
    # written to disk for a split the reviewer may still reject.
    from tools.splitter import split_pdf
    segment_models = [Segment(**segment) for segment in segments]
    # Writing one PDF per segment is blocking I/O on an event loop shared with the
    # API, so it goes to a thread — otherwise the UI's status polls hang until the
    # whole packet has been carved up.
    segment_models = await asyncio.to_thread(split_pdf, file_path, segment_models, out_dir)

    # A packet linked to a claim hands its links down to the documents inside it.
    claim_links = await claim_db.get_claim_links_for_document(document_id)
    claim_ids = [link.claim_id for link in claim_links]

    children = []
    for segment in segment_models:
        child_name = _child_filename(filename, segment, display_types)
        child_id, created = await db.get_or_create_split_child(
            parent_id=document_id,
            filename=child_name,
            file_path=segment.output_file,
            file_hash=await asyncio.to_thread(_sha256, segment.output_file),
            page_range=segment.page_range_label,
            doc_type_hint=segment.doc_type,
            split_confidence=segment.min_confidence,
            customer_id=customer_id,
        )
        segment.child_document_id = child_id

        if not created:
            logger.info(f"[Document {document_id}] Child for pages {segment.page_range_label} already exists ({child_id})")
            children.append({
                "document_id": child_id, "filename": child_name,
                "page_range": segment.page_range_label, "doc_type": segment.doc_type,
                "workflow_run_id": None, "reused": True,
            })
            continue

        doc_type, skip_reason = _reusable_doc_type(segment, threshold)
        if skip_reason:
            logger.info(
                f"[Document {document_id}] Child {child_id} will re-classify — {skip_reason}"
            )

        run_id = "unknown_run_id"
        try:
            run_response = await client.workflows.execute_workflow_async(
                workflow_identifier="document_processing_workflow",
                input={
                    "document_id": child_id,
                    "filename": child_name,
                    "file_path": segment.output_file,
                    "auto_split": False,
                    "preclassified_doc_type": doc_type,
                    "preclassified_confidence": segment.min_confidence if doc_type else 0.0,
                    "preclassified_reasoning": (
                        f"Classified during packet split of {filename}, pages {segment.page_range_label}."
                        if doc_type else ""
                    ),
                },
            )
            run_id = getattr(run_response, "execution_id", "unknown_run_id")
            await db.update_workflow_run_id(child_id, run_id)
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to start workflow for child {child_id}: {e}")
            await db.update_error(child_id, {"error": str(e), "stage": "split_fanout"})

        for claim_id in claim_ids:
            try:
                await claim_db.link_document_to_claim(
                    claim_id=claim_id,
                    document_id=child_id,
                    doc_type=doc_type or "classification_pending",
                )
            except Exception as e:
                logger.warning(f"[Document {document_id}] Failed to link child {child_id} to claim {claim_id}: {e}")

        children.append({
            "document_id": child_id,
            "filename": child_name,
            "page_range": segment.page_range_label,
            "doc_type": segment.doc_type,
            "reused_classification": bool(doc_type),
            "workflow_run_id": run_id,
            "reused": False,
        })

    # The packet itself is no longer a claim document — its contents are.
    if claim_ids:
        removed = await claim_db.remove_claim_links_for_document(document_id)
        logger.info(f"[Document {document_id}] Replaced {removed} parent claim link(s) with per-child links")

    manifest = {
        "segments": [s.model_dump() for s in segment_models],
        "pages": pages or [],
        "children": children,
        "output_dir": out_dir,
    }
    await db.mark_split_parent(document_id, manifest)

    logger.info(f"[Document {document_id}] Fan-out complete — {len(children)} child documents")
    return {"children": children, "segment_count": len(segment_models)}

"""
Step 3.2 — Batch Checklist
==========================
Runs straight after classification, and is a **batch-wide barrier**: every
document in an upload stops here, and they all continue together or not at all.

Why a barrier rather than a per-document check. "Did we upload all the types?"
can only be answered across the whole upload, and the answer is not knowable
until every file in it has classified. Letting documents that classified early
run ahead to extraction would mean the batch is half-extracted by the time
anyone is told a document is missing — and the reviewer's decision would apply
to whatever had not overtaken it yet.

The shape of one document's pass through this step:

  1. If the batch has already been released, walk straight through. Release is
     sticky, so a document that joins late never re-gates a batch that moved on.
  2. If any sibling has yet to classify, park at `checklist_hold`.
  3. Otherwise this is the last document to classify, so evaluate the batch:
     reconcile what was uploaded against the configured classification types.
       - Nothing missing → release the whole batch automatically and continue.
         Nobody is asked anything; the hold was only ever about waiting for the
         batch to be knowable.
       - Something missing → open the human gate at `awaiting_checklist_review`
         and park here too. Every document is now waiting on one decision.

The verdict itself is a set difference computed in `tools/checklist.py`. The
Checklist Agent only writes the reviewer-facing summary; if it is unconfigured
or fails, a deterministic summary is used and the verdict is unchanged.
"""

import json
import logging

import mistralai.workflows as workflows

from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
from tools.checklist import (
    batch_signature,
    build_required_types,
    fallback_summary,
    format_checklist_prompt,
    pending_documents,
    reconcile,
)
from utils.workflow_resume import submit_input_with_retry
import db.checklist_operations as checklist_db
import db.operations as db

logger = logging.getLogger(__name__)
client = get_mistral_client()


def _extract_text(content) -> str:
    """Safely extract text from the various Mistral response content shapes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif hasattr(chunk, "text") and chunk.text:
                parts.append(chunk.text)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _go(reason: str, **extra) -> dict:
    """Walk through the gate."""
    return {"wait": False, "gate_holder": False, "reason": reason, "message": "", **extra}


def _hold(reason: str, message: str, gate_holder: bool = False, **extra) -> dict:
    """Park behind the gate."""
    return {"wait": True, "gate_holder": gate_holder, "reason": reason,
            "message": message, **extra}


async def _summarise(batch_id: str, result: dict, documents: list) -> tuple[str, str]:
    """Ask the Checklist Agent to narrate the verdict. Returns (summary, source)."""
    if not settings.CHECKLIST_AGENT_ID:
        logger.info(f"[Batch {batch_id}] CHECKLIST_AGENT_ID not set — using the deterministic summary.")
        return fallback_summary(result), "deterministic"

    try:
        response = await client.agents.complete_async(
            agent_id=settings.CHECKLIST_AGENT_ID,
            messages=[{"role": "user", "content": format_checklist_prompt(result, documents)}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(_extract_text(response.choices[0].message.content).strip())
        summary = (parsed.get("summary") or "").strip()
        return (summary, "agent") if summary else (fallback_summary(result), "deterministic")
    except Exception as e:
        # A narration failure must not stop a batch whose verdict is already known.
        logger.warning(f"[Batch {batch_id}] Checklist Agent failed ({e}) — using the deterministic summary.")
        return fallback_summary(result), "deterministic"


async def release_batch(batch_id: str, proceed: bool, note: str = "", mode: str = "auto") -> dict:
    """
    Let the whole batch through the gate and resume every document behind it.

    `mark_released` is the mutex: two callers racing — an auto-release and a
    reviewer pressing Continue — cannot both fan out. The loser returns the
    already-released result rather than double-submitting inputs.
    """
    await checklist_db.ensure_row(batch_id)

    if not await checklist_db.mark_released(batch_id, mode, note or None):
        logger.info(f"[Batch {batch_id}] Already released — skipping the fan-out.")
        return {"batch_id": batch_id, "released": False, "resumed": 0, "already_released": True}

    held = await checklist_db.get_gate_documents(batch_id)
    payload = {"proceed": proceed, "note": note or None,
               "rejection_reason": None if proceed else (note or None)}

    resumed, missed = 0, []
    for doc in held:
        if await submit_input_with_retry(doc.workflow_run_id, payload):
            resumed += 1
        else:
            missed.append(doc.id)

    logger.info(
        f"[Batch {batch_id}] Released ({mode}, proceed={proceed}) — resumed {resumed}/{len(held)} document(s)"
        + (f"; could not resume {missed}" if missed else "")
    )
    return {"batch_id": batch_id, "released": True, "resumed": resumed,
            "missed": missed, "already_released": False}


async def evaluate_batch(batch_id: str, gate_document_id: str | None = None) -> dict:
    """
    Reconcile a batch and decide what happens to it.

    Shared by the pipeline (the last document to classify calls it) and by the
    API's re-check, which is how a reviewer un-sticks a batch whose last
    document failed before ever reaching this step.

    Returns the verdict plus `action`: "released" | "gate" | "waiting" | "skipped".
    """
    documents = await checklist_db.get_batch_documents(batch_id)
    if not documents:
        return {"action": "skipped", "reason": "empty_batch", "batch_id": batch_id}

    still_pending = pending_documents(documents)
    if still_pending:
        return {"action": "waiting", "reason": "batch_incomplete", "batch_id": batch_id,
                "pending": len(still_pending)}

    required = build_required_types()
    if not required:
        logger.warning(f"[Batch {batch_id}] No classification types configured — releasing.")
        await release_batch(batch_id, True, "No document types configured.", "auto")
        return {"action": "released", "reason": "no_required_types", "batch_id": batch_id,
                "complete": True}

    signature = batch_signature(documents, required)
    result = reconcile(documents, required)

    # Only the caller that wins the claim pays for the agent call and the write.
    # Everyone else reads the verdict it stored.
    if await checklist_db.claim_evaluation(batch_id, signature, gate_document_id):
        try:
            summary, source = await _summarise(batch_id, result, documents)
            await checklist_db.save_evaluation(batch_id, result, summary, source)
        except Exception as e:
            # Give the claim back so a retry can try again, rather than leaving
            # the batch pinned at "evaluating" with every document behind it.
            logger.error(f"[Batch {batch_id}] Checklist evaluation failed: {e}")
            await checklist_db.release_claim(batch_id)
            raise
    else:
        stored = await checklist_db.get_checklist(batch_id)
        summary = (stored.summary if stored else None) or fallback_summary(result)

    logger.info(
        f"[Batch {batch_id}] Checklist: {len(result['present'])}/{len(required)} types present"
        + (f" — missing {[m['doc_type'] for m in result['missing']]}" if result["missing"] else " — complete")
    )

    row = await checklist_db.get_checklist(batch_id)
    gate_already_open = bool(row and row.gate_opened)

    # Nothing missing, and no reviewer is mid-decision: let the batch go.
    if result["complete"] and not gate_already_open:
        await release_batch(batch_id, True, "", "auto")
        return {"action": "released", "batch_id": batch_id, "summary": summary,
                "complete": True, **result}

    # Something is missing — or a reviewer already holds this batch, in which
    # case the decision stays theirs even though the gap has since been filled.
    await checklist_db.mark_gate_opened(batch_id)
    return {"action": "gate", "batch_id": batch_id, "summary": summary, **result}


@workflows.activity()
async def checklist_activity(document_id: str) -> dict:
    """
    Decide whether this document walks through the batch checklist or parks.

    Returns:
      {"wait": False, ...}                       — continue the pipeline
      {"wait": True, "gate_holder": False, ...}  — park, batch not yet knowable
      {"wait": True, "gate_holder": True, ...}   — park and hold the human gate
    """
    if not settings.ENABLE_DOC_CHECKLIST:
        return _go("disabled")

    document = await db.get_document(document_id)
    batch_id = getattr(document, "batch_id", None) if document else None
    if not batch_id:
        # Documents ingested before batches existed have no set to reconcile.
        logger.info(f"[Document {document_id}] No batch_id — skipping the checklist.")
        return _go("no_batch")

    # Sticky release: a batch that has already been let through never re-gates,
    # so documents uploaded into it afterwards are not stranded behind a
    # decision that was made without them.
    if await checklist_db.is_released(batch_id):
        return _go("already_released", batch_id=batch_id)

    verdict = await evaluate_batch(batch_id, gate_document_id=document_id)
    action = verdict["action"]

    if action == "released":
        # This document performed the release, so it is not in the fan-out.
        return _go("batch_complete", batch_id=batch_id, complete=True,
                   summary=verdict.get("summary", ""))

    if action == "waiting":
        return _hold(
            "waiting_for_batch",
            f"Waiting for the rest of this upload to be classified "
            f"({verdict.get('pending', 0)} still in progress).",
            batch_id=batch_id,
        )

    if action == "skipped":
        return _go(verdict.get("reason", "skipped"), batch_id=batch_id)

    # action == "gate" — this document opens (or joins) the human gate.
    missing = verdict.get("missing", [])
    missing_labels = ", ".join(entry["label"] for entry in missing)

    if not settings.CHECKLIST_REQUIRE_REVIEW:
        logger.warning(
            f"[Batch {batch_id}] Missing {missing_labels} — CHECKLIST_REQUIRE_REVIEW "
            f"is off, releasing anyway."
        )
        await release_batch(batch_id, True, "Review disabled by configuration.", "auto")
        return _go("review_disabled", batch_id=batch_id, missing=missing)

    row = await checklist_db.get_checklist(batch_id)
    holder = row.gate_document_id if row else document_id

    logger.info(
        f"[Document {document_id}] Batch {batch_id} held at the checklist gate — "
        f"missing {[entry['doc_type'] for entry in missing]}"
    )
    return _hold(
        "incomplete",
        f"{len(missing)} document type(s) missing from this upload: {missing_labels}.",
        gate_holder=(holder == document_id),
        batch_id=batch_id,
        missing=missing,
        summary=verdict.get("summary", ""),
    )


@workflows.activity()
async def release_batch_activity(batch_id: str, proceed: bool, note: str = "",
                                 mode: str = "human") -> dict:
    """Release a batch from inside a workflow (used on the reviewer's answer)."""
    return await release_batch(batch_id, proceed, note, mode)

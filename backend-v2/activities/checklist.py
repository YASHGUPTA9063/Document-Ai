"""
Step 3.2 — Batch Checklist
==========================
Runs straight after classification. Reconciles the document types seen across
the whole upload batch against the configured classification types, and tells
the workflow whether the batch is missing anything.

Two things make this step unusual in an otherwise per-document pipeline:

  * It is *set-scoped*. Every file of one upload shares a `batch_id`, and the
    question "did we upload all the types?" can only be answered across that
    set — never from the single document the workflow is holding.

  * It is *barriered*. A document that reaches Step 3.2 while its siblings are
    still queued behind it would see a half-classified batch and report types as
    missing that are moments away from arriving. So the step no-ops for every
    document except the last one to classify, which then evaluates on behalf of
    the batch and holds the review gate for it.

The verdict is a set difference computed in `tools/checklist.py`, not something
the model decides. The Checklist Agent only writes the reviewer-facing summary;
if it is unconfigured or fails, a deterministic summary is used and the pipeline
carries on with the same verdict.
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


def _skip(reason: str, **extra) -> dict:
    """A no-op verdict — the workflow continues without opening a gate."""
    return {"evaluated": False, "reason": reason, "complete": True, **extra}


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


@workflows.activity()
async def checklist_activity(document_id: str) -> dict:
    """
    Decide whether this upload batch holds every configured document type.

    Returns either:
      {"evaluated": False, "reason": "batch_incomplete" | "no_batch" | ..., "complete": True}
      {"evaluated": True, "complete": bool, "batch_id": str, "required": [...],
       "present": [...], "missing": [...], "extra": [...], "unclassified": [...],
       "summary": str, "source": "agent" | "deterministic"}

    Only an `evaluated` result with `complete` false should open a review gate.
    """
    if not settings.ENABLE_DOC_CHECKLIST:
        return _skip("disabled")

    document = await db.get_document(document_id)
    batch_id = getattr(document, "batch_id", None) if document else None
    if not batch_id:
        # Documents uploaded before batches existed, or through a path that does
        # not assign one, have no set to be reconciled against.
        logger.info(f"[Document {document_id}] No batch_id — skipping the checklist.")
        return _skip("no_batch")

    documents = await checklist_db.get_batch_documents(batch_id)
    if not documents:
        return _skip("empty_batch", batch_id=batch_id)

    # ── Barrier: let the batch finish classifying before judging it ──
    # The caller's own type was persisted by the workflow immediately before this
    # step, so it is already settled and drops out of `pending` on its own. It is
    # deliberately not special-cased: if its type somehow did not land, deferring
    # is the safe answer — a batch that never opens a gate beats one that opens a
    # gate over documents whose types simply had not been written yet.
    still_pending = pending_documents(documents)
    if still_pending:
        logger.info(
            f"[Document {document_id}] Batch {batch_id} still has {len(still_pending)} "
            f"document(s) to classify — deferring the checklist to the last one."
        )
        return _skip("batch_incomplete", batch_id=batch_id)

    required = build_required_types()
    if not required:
        logger.warning(f"[Batch {batch_id}] No classification types configured — nothing to check.")
        return _skip("no_required_types", batch_id=batch_id)

    signature = batch_signature(documents, required)
    if not await checklist_db.claim_evaluation(batch_id, signature, document_id):
        logger.info(f"[Document {document_id}] Batch {batch_id} already evaluated for this content.")
        return _skip("already_evaluated", batch_id=batch_id)

    try:
        result = reconcile(documents, required)
        summary, source = await _summarise(batch_id, result, documents)
        await checklist_db.save_evaluation(batch_id, result, summary, source)
    except Exception as e:
        # Give the claim back so a retry — or a sibling document — can try again,
        # rather than leaving the batch permanently marked "evaluating".
        logger.error(f"[Batch {batch_id}] Checklist evaluation failed: {e}")
        await checklist_db.release_claim(batch_id)
        raise

    logger.info(
        f"[Batch {batch_id}] Checklist: {len(result['present'])}/{len(required)} types present"
        + (f" — missing {[m['doc_type'] for m in result['missing']]}" if result["missing"] else " — complete")
    )

    return {
        "evaluated": True,
        "reason": "",
        "batch_id": batch_id,
        "summary": summary,
        "source": source,
        **result,
    }


@workflows.activity()
async def record_checklist_decision_activity(batch_id: str, proceed: bool, note: str = "") -> dict:
    """Persist the reviewer's answer so the UI stops showing an open gate."""
    await checklist_db.record_decision(batch_id, proceed, note or None)
    return {"batch_id": batch_id, "proceed": proceed}

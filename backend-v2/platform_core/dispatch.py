"""
Mistral Studio dispatch
=======================
The only module that starts a workflow run. Everything that used to call
`client.workflows.execute_workflow_async` directly — the upload endpoint, the
arq dispatcher, the split fan-out, the claims router — goes through here.

There were three call sites before this existed and three different
conventions: the upload endpoint passed neither `execution_id` nor
`deployment_name`, the arq worker passed both, and `split_fanout` passed
neither and used a different workflow identifier. That made a Studio execution
impossible to correlate back to a document, and meant a retry could either
collide on a duplicate execution id or start a second run of the same document.

One place now owns:
  * the execution-id scheme (correlatable, and unique per attempt)
  * `deployment_name`, which is the worker-pool version — see config.py
  * what a dispatch failure does to the document row
"""

import logging
import uuid

from config import settings
from platform_core.adapters.resilient_mistral import get_mistral_client

logger = logging.getLogger(__name__)

DOCUMENT_WORKFLOW = "document_processing_workflow"
CLAIM_WORKFLOW = "claim_processing_workflow"

UNKNOWN_RUN_ID = "unknown_run_id"


class DispatchError(RuntimeError):
    """A workflow run could not be started on Mistral Studio."""


def _execution_id(kind: str, entity_id: str) -> str:
    """
    A Studio execution id that reads back to the entity that caused it.

    The uuid suffix is required, not cosmetic: an entity can legitimately be
    run more than once (a duplicate override, a retry, a re-run) and Studio
    rejects a reused execution id.
    """
    return f"{kind}-{entity_id}-{uuid.uuid4().hex[:8]}"


def _resolve_document_workflow() -> str:
    """
    Prefer the Studio workflow ID when one is configured, else the registered
    workflow name. Both are accepted as `workflow_identifier`; the ID is what
    makes the run show up against the right Studio workflow.
    """
    return settings.MISTRAL_WORKFLOW_ID or DOCUMENT_WORKFLOW


async def start_document_run(
    document_id: str,
    filename: str,
    file_path: str,
    *,
    auto_split: bool = True,
    preclassified_doc_type: str = "",
    preclassified_confidence: float = 0.0,
    preclassified_reasoning: str = "",
) -> str:
    """
    Start `document_processing_workflow` for one document.

    The keyword arguments mirror `workflow.DocumentProcessingWorkflow.run`'s
    signature exactly. `auto_split=False` plus the `preclassified_*` fields is
    how the split fan-out launches a child: it can never re-split, and it skips
    the classifier because the splitter already typed that segment.

    Returns the Studio execution id. Raises DispatchError on failure so the
    caller decides whether that fails the request or gets retried by arq.
    """
    execution_id = _execution_id("doc", document_id)
    workflow_identifier = _resolve_document_workflow()

    logger.info(
        "[Dispatch] Starting %s for document %s (execution_id=%s, deployment=%s)",
        workflow_identifier, document_id, execution_id, settings.DEPLOYMENT_NAME,
    )

    try:
        response = await get_mistral_client().workflows.execute_workflow_async(
            workflow_identifier=workflow_identifier,
            input={
                "document_id": document_id,
                "filename": filename,
                "file_path": file_path,
                "auto_split": auto_split,
                "preclassified_doc_type": preclassified_doc_type,
                "preclassified_confidence": preclassified_confidence,
                "preclassified_reasoning": preclassified_reasoning,
            },
            deployment_name=settings.DEPLOYMENT_NAME,
            execution_id=execution_id,
        )
    except Exception as e:
        logger.error("[Dispatch] Failed to start run for document %s: %s", document_id, e)
        raise DispatchError(f"Could not start workflow for document {document_id}: {e}") from e

    return getattr(response, "execution_id", execution_id)


async def start_claim_run(claim_id: str, claimant_id: str, policy_id: str) -> str:
    """Start `claim_processing_workflow` for one claim."""
    execution_id = _execution_id("claim", claim_id)

    logger.info(
        "[Dispatch] Starting %s for claim %s (execution_id=%s)",
        CLAIM_WORKFLOW, claim_id, execution_id,
    )

    try:
        response = await get_mistral_client().workflows.execute_workflow_async(
            workflow_identifier=CLAIM_WORKFLOW,
            input={
                "claim_id": claim_id,
                "claimant_id": claimant_id,
                "policy_id": policy_id,
            },
            deployment_name=settings.DEPLOYMENT_NAME,
            execution_id=execution_id,
        )
    except Exception as e:
        logger.error("[Dispatch] Failed to start run for claim %s: %s", claim_id, e)
        raise DispatchError(f"Could not start workflow for claim {claim_id}: {e}") from e

    return getattr(response, "execution_id", execution_id)


async def start_document_run_and_record(
    document_id: str, filename: str, file_path: str, **kwargs
) -> str:
    """
    Start a run and persist its execution id on the document row.

    `workflow_run_id` is what every resume endpoint addresses, so a document
    whose run started but whose id was never written back cannot be released
    from any human gate. On failure the error is recorded on the document and
    re-raised.
    """
    import db.operations as db

    try:
        run_id = await start_document_run(document_id, filename, file_path, **kwargs)
    except DispatchError as e:
        await db.update_error(document_id, {"error": str(e), "stage": "dispatch"})
        await db.update_status_and_message(
            document_id, "failed", "Could not start processing. Please retry."
        )
        raise

    await db.update_workflow_run_id(document_id, run_id)
    return run_id

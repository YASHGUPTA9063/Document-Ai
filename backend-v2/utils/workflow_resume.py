"""
Workflow Resume Helper
======================
Submitting an input to a paused Mistral workflow execution is a two-step
protocol: query `__get_pending_inputs` for the waiting task, then post the
payload to `__submit_input` against that task id.

It lived inline in the API router while only a human could resume a workflow.
The batch checklist changed that — releasing a batch has to resume *every*
document paused behind the gate, and the release can be triggered by the
pipeline itself (an auto-release when nothing is missing) as well as by a
reviewer. Both paths need the same protocol, so it lives here.
"""

import asyncio
import logging

from platform_core.adapters.resilient_mistral import get_mistral_client

logger = logging.getLogger(__name__)


async def get_pending_task_id(run_id: str) -> str | None:
    """The task id of the input a paused execution is waiting on, if any."""
    if not run_id or run_id == "unknown_run_id":
        return None
    try:
        client = get_mistral_client()
        query_result = await client.workflows.executions.query_workflow_execution_async(
            execution_id=run_id,
            name="__get_pending_inputs",
        )
        pending = (query_result.result or {}).get("pending_inputs", [])
        return pending[0]["task_id"] if pending else None
    except Exception as e:
        logger.warning(f"[Workflow {run_id}] Could not read pending inputs: {e}")
        return None


async def submit_input(run_id: str, payload: dict) -> bool:
    """
    Resume one paused execution. Returns False when it was not waiting.

    A False here is not necessarily an error: a workflow that has not yet
    reached its wait, or has already been resumed, both look like this.
    """
    task_id = await get_pending_task_id(run_id)
    if task_id is None:
        return False

    try:
        client = get_mistral_client()
        await client.workflows.executions.update_workflow_execution_async(
            execution_id=run_id,
            name="__submit_input",
            input={"task_id": task_id, "input": payload},
        )
        return True
    except Exception as e:
        logger.warning(f"[Workflow {run_id}] Failed to submit input: {e}")
        return False


async def submit_input_with_retry(run_id: str, payload: dict,
                                  attempts: int = 8, delay: float = 2.0) -> bool:
    """
    Resume an execution that may not have reached its wait yet.

    A document releases the gate for its siblings the instant it evaluates the
    batch, and a sibling can be in the gap between "decided to wait" and having
    actually registered the wait. Retrying over ~15s covers that gap; the
    reviewer pressing Continue again is the backstop if it somehow does not.
    """
    for attempt in range(attempts):
        if await submit_input(run_id, payload):
            return True
        if attempt < attempts - 1:
            await asyncio.sleep(delay)
    return False

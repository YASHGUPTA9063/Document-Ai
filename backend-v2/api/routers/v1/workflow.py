"""
Workflow Router
===============
Resume endpoints for workflows paused at a `wait_for_input` step.

Moved verbatim from branch-vm3's monolithic main.py. The path parameter is
still named `workflow_run_id` (not development's `pipeline_id`) because the
frontend posts to /workflow/{workflowRunId}/resume/... and the value is a
Mistral execution ID.
"""

import logging

from fastapi import APIRouter, HTTPException

from schemas.documents import DuplicateDecisionRequest, ReviewerDecisionRequest
from api.deps import get_mistral_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflow"])


@router.post("/workflow/{workflow_run_id}/resume/duplicate")
async def resume_duplicate(workflow_run_id: str, decision: DuplicateDecisionRequest):
    """
    Resume a workflow paused at wait_for_input (duplicate check).
    The Mistral InteractiveWorkflow SDK uses Temporal *Updates* (NOT signals).
    Protocol:
      1. Query '__get_pending_inputs' to get the task_id for the pending input.
      2. Call update '__submit_input' with that task_id and the user's decision payload.
    """
    try:
        client = get_mistral_client()

        # Step 1: get the pending task_id
        query_result = await client.workflows.executions.query_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__get_pending_inputs",
        )
        pending_inputs = (query_result.result or {}).get("pending_inputs", [])
        if not pending_inputs:
            raise HTTPException(status_code=409, detail="No pending inputs found. Workflow may not be paused yet.")
        task_id = pending_inputs[0]["task_id"]

        # Step 2: submit the decision
        await client.workflows.executions.update_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__submit_input",
            input={"task_id": task_id, "input": decision.model_dump()},
        )
        return {"message": "Workflow resumed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming duplicate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/{workflow_run_id}/resume/review")
async def resume_review(workflow_run_id: str, decision: ReviewerDecisionRequest):
    """
    Resume a workflow paused at wait_for_input (human review).
    Same two-step protocol: query pending inputs, then submit via update.
    """
    try:
        client = get_mistral_client()

        # Step 1: get the pending task_id
        query_result = await client.workflows.executions.query_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__get_pending_inputs",
        )
        pending_inputs = (query_result.result or {}).get("pending_inputs", [])
        if not pending_inputs:
            raise HTTPException(status_code=409, detail="No pending inputs found. Workflow may not be paused yet.")
        task_id = pending_inputs[0]["task_id"]

        # Step 2: submit the decision
        await client.workflows.executions.update_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__submit_input",
            input={"task_id": task_id, "input": decision.model_dump()},
        )
        return {"message": "Workflow resumed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming review: {e}")
        raise HTTPException(status_code=500, detail=str(e))

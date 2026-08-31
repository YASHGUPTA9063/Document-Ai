"""
Claims Router
=============
Claim creation, listing, status, workflow triggering, reporting and decisions.

Claim processing runs on Mistral Studio as `claim_processing_workflow` (see
claim_workflow.ClaimProcessingWorkflow). This router never starts a run
directly: it goes through api.queue.submit_claim_run, so a run is enqueued for
the dispatcher under EXECUTION_MODE=queue and started in-request under
`inline`. Response shapes are unchanged.
"""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select as _sel

from db.database import AsyncSessionLocal
from db.models import Claim as _Claim, ClaimReport as _CR
import db.claim_operations as claim_db
from schemas.claims import CreateClaimRequest, ClaimDecisionRequest
from api.queue import submit_claim_run

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Claims"])


@router.post("/claims")
async def create_claim(request: CreateClaimRequest):
    """
    Create a new claim record.
    Returns the generated claim_id — the frontend uses this to link subsequent uploads.
    """
    claim = await claim_db.create_claim(
        claimant_name=request.claimant_name,
        claim_type=request.claim_type,
        policy_number=request.policy_number,
        description=request.description,
        priority=request.priority or "medium",
        amount=request.amount or 0.0,
    )
    return {
        "claim_id": claim.claim_id,
        "claimant_name": claim.claimant_name,
        "claim_type": claim.claim_type,
        "policy_number": claim.policy_id,
        "priority": claim.priority,
        "amount": claim.amount,
        "description": claim.description,
        "status": claim.status,
        "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
    }


@router.get("/claims")
async def list_claims():
    """
    Return all claims ordered by newest first.
    Each claim includes its current status and basic metadata.
    """
    claims = await claim_db.get_all_claims()
    result = []
    for c in claims:
        result.append({
            "claim_id": c.claim_id,
            "claimant_name": c.claimant_name,
            "claim_type": c.claim_type,
            "policy_number": c.policy_id,
            "priority": c.priority,
            "amount": c.amount,
            "description": c.description,
            "status": c.status,
            "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
            "workflow_run_id": c.workflow_run_id,
        })
    return result


@router.get("/claims/{claim_id}/status")
async def get_claim_status(claim_id: str):
    """
    Returns processing status and any agent results written so far.
    agent_results is populated incrementally as each agent finishes,
    so the frontend can show live reasoning without waiting for the full workflow.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    status_info = await claim_db.get_claim_extraction_status(claim_id)

    # Fetch any partial agent results written incrementally by the workflow
    agent_results = {}
    async with AsyncSessionLocal() as session:
        res = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        partial_report = res.scalar_one_or_none()
        if partial_report:
            agent_results = partial_report.agent_results or {}

    return {
        "claim_id": claim_id,
        "claim_type": status_info.get("claim_type", claim.claim_type),
        "claim_status": claim.status,
        "agent_results": agent_results,
        "total_docs": status_info["total_docs"],
        "completed_docs": status_info["completed_docs"],
        "failed_docs": status_info["failed_docs"],
        "ready_to_process": status_info["ready_to_process"],
        "doc_statuses": status_info["doc_statuses"],
        "required_docs": status_info.get("required_docs", []),
        "missing_required_count": status_info.get("missing_required_count", 0),
        "all_required_completed": status_info.get("all_required_completed", False),
    }


@router.post("/claims/{claim_id}/run")
async def run_claim_workflow(claim_id: str):
    """
    Triggers the claim_processing_workflow for a given claim.
    Only allowed when claim status is 'ready'.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Claim is not ready to process. Current status: {claim.status}"
        )

    status_info = await claim_db.get_claim_extraction_status(claim_id)
    if status_info.get("missing_required_count", 0) > 0 and claim.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run claim processing. {status_info['missing_required_count']} required document(s) are missing or pending extraction."
        )

    try:
        # Under `queue` this returns None: the dispatcher starts the run and
        # writes workflow_run_id itself. Mark the claim processing either way so
        # the UI does not offer Run a second time while it is in flight.
        run_id = await submit_claim_run(claim_id, claim.claimant_id, claim.policy_id)
        if run_id is None:
            await claim_db.update_claim_status(claim_id, "processing")

        return {"claim_id": claim_id, "workflow_run_id": run_id or "", "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to start claim workflow for {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/claims/{claim_id}/rerun")
async def rerun_claim_workflow(claim_id: str):
    """
    Resets a completed/approved/rejected/failed claim back to 'ready'
    and re-fires the claim_processing_workflow.
    Deletes the existing report so the workflow starts fresh.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    async with AsyncSessionLocal() as session:
        # Delete old report so the workflow can write a fresh one
        res = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        old_report = res.scalar_one_or_none()
        if old_report:
            await session.delete(old_report)

        # Reset claim status to 'ready'
        res2 = await session.execute(_sel(_Claim).where(_Claim.claim_id == claim_id))
        c = res2.scalar_one_or_none()
        if c:
            c.status = "ready"
            c.workflow_run_id = None
        await session.commit()

    try:
        run_id = await submit_claim_run(claim_id, claim.claimant_id, claim.policy_id)
        if run_id is None:
            await claim_db.update_claim_status(claim_id, "processing")

        return {"claim_id": claim_id, "workflow_run_id": run_id or "", "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to rerun claim workflow for {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/claims/{claim_id}/report")
async def get_claim_report(claim_id: str):
    """
    Returns the final ClaimReport for a completed claim.
    Contains all 5 agent results and the suggestion paragraph.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for claim {claim_id}. Has the workflow completed?")

    return {
        "claim_id": report.claim_id,
        "claimant_name": report.claimant_name,
        "overall_status": report.overall_status,
        "suggestion": report.suggestion,
        "agent_results": report.agent_results,
        "processed_at": report.processed_at.isoformat() if report.processed_at else None,
    }


@router.post("/claims/{claim_id}/decision")
async def submit_claim_decision(claim_id: str, request: ClaimDecisionRequest):
    """
    Records the adjuster's final decision on a claim (approve or reject).
    Updates claim status in the DB.
    """
    if request.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    new_status = "approved" if request.decision == "approve" else "rejected"
    await claim_db.update_claim_status(claim_id, new_status)

    logger.info(f"[Claim {claim_id}] Decision: {new_status}. Notes: {request.notes}")
    return {"claim_id": claim_id, "decision": new_status, "notes": request.notes}


@router.delete("/claims/{claim_id}")
async def delete_claim(claim_id: str):
    """
    Permanently deletes a claim and all its linked document associations.
    Does NOT delete the underlying document files from storage.
    """
    deleted = await claim_db.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return {"claim_id": claim_id, "deleted": True}

"""
Claims Routes (v1)
==================
Handles claim creation, listing, status, execution, and decisions.

Response shapes mirror the legacy monolith (main_legacy.py) — that is the
contract frontend-v2 was written against. Execution goes through the v2
PipelineEngine (or the Redis worker queue) rather than Mistral Workflows.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Claim, ClaimReport
import db.claim_operations as claim_db
from schemas.claims import CreateClaimRequest, ClaimDecisionRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["Claims"])


def _serialize_claim(c: Claim) -> dict:
    """Common claim representation used by create and list."""
    return {
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
    }


@router.post("")
async def create_claim(request: CreateClaimRequest):
    """
    Create a new claim record.
    Returns the generated claim_id — the frontend uses this to link subsequent uploads.
    """
    try:
        claim = await claim_db.create_claim(
            claimant_name=request.claimant_name,
            claim_type=request.claim_type,
            policy_number=request.policy_number,
            description=request.description,
            priority=request.priority or "medium",
            amount=request.amount or 0.0,
        )
        return _serialize_claim(claim)
    except Exception as e:
        logger.error(f"Error creating claim: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_claims():
    """Return all claims, newest first."""
    claims = await claim_db.get_all_claims()
    return [_serialize_claim(c) for c in claims]


@router.get("/{claim_id}/status")
async def get_claim_status(claim_id: str):
    """
    Returns processing status, the required-document checklist, and any agent
    results written so far. agent_results is populated incrementally as each
    agent finishes, so the frontend can show live reasoning without waiting
    for the full workflow.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    status_info = await claim_db.get_claim_extraction_status(claim_id)

    # Partial agent results written incrementally by the workflow
    agent_results = {}
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(ClaimReport).where(ClaimReport.claim_id == claim_id))
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


async def _assert_required_docs_present(claim: Claim):
    """
    Block claim processing when the claim type's required document checklist is
    not satisfied. A claim already in 'failed' is allowed through so it can be retried.
    """
    status_info = await claim_db.get_claim_extraction_status(claim.claim_id)
    if status_info.get("missing_required_count", 0) > 0 and claim.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot run claim processing. {status_info['missing_required_count']} "
                f"required document(s) are missing or pending extraction."
            ),
        )


async def _start_claim_pipeline(request: Request, claim: Claim):
    """Enqueue the claim pipeline, or run it in-process when no Redis pool is configured."""
    import asyncio
    from platform_core.pipeline.definitions import build_claim_pipeline
    from platform_core.pipeline.engine import PipelineEngine
    from platform_core.pipeline.checkpoint import CheckpointManager
    from platform_core.config import load_config

    context = {
        "claim_id": claim.claim_id,
        "claimant_id": claim.claimant_id,
        "policy_id": claim.policy_id,
    }

    redis_pool = getattr(request.app.state, "redis_pool", None)
    if redis_pool:
        await redis_pool.enqueue_job("run_claim_pipeline", **context)
    else:
        config = load_config()
        pipeline = build_claim_pipeline(config)
        engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
        asyncio.create_task(engine.run(pipeline=pipeline, context=context))


@router.post("/{claim_id}/run")
async def run_claim_workflow(request: Request, claim_id: str):
    """Trigger the claim-level AI workflow."""
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    if claim.status in ("processing", "evaluating"):
        raise HTTPException(status_code=409, detail="Claim workflow is already running")

    # Gate before taking a write session — get_claim_extraction_status opens its own.
    await _assert_required_docs_present(claim)

    await claim_db.update_claim_status(claim_id, "processing")

    try:
        await _start_claim_pipeline(request, claim)
        return {"message": "Claim workflow started", "claim_id": claim.claim_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to start claim workflow: {e}")
        await claim_db.update_claim_status(claim_id, "failed")
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {e}")


@router.post("/{claim_id}/rerun")
async def rerun_claim_workflow(request: Request, claim_id: str):
    """
    Reset a completed/approved/rejected/failed claim back to 'ready' and re-fire
    the claim pipeline. The existing report is deleted so the run starts fresh.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    await _assert_required_docs_present(claim)

    async with AsyncSessionLocal() as session:
        # Delete the old report so the workflow can write a fresh one
        res = await session.execute(select(ClaimReport).where(ClaimReport.claim_id == claim_id))
        old_report = res.scalar_one_or_none()
        if old_report:
            await session.delete(old_report)

        res2 = await session.execute(select(Claim).where(Claim.claim_id == claim_id))
        c = res2.scalar_one_or_none()
        if c:
            c.status = "ready"
            c.workflow_run_id = None
        await session.commit()

    try:
        await _start_claim_pipeline(request, claim)
        await claim_db.update_claim_status(claim_id, "processing")
        return {"claim_id": claim_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to rerun claim workflow for {claim_id}: {e}")
        await claim_db.update_claim_status(claim_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{claim_id}/report")
async def get_claim_report(claim_id: str):
    """
    Returns the final ClaimReport for a completed claim.
    Contains all agent results and the suggestion paragraph.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ClaimReport).where(ClaimReport.claim_id == claim_id))
        report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for claim {claim_id}. Has the workflow completed?",
        )

    return {
        "claim_id": report.claim_id,
        "claimant_name": report.claimant_name,
        "overall_status": report.overall_status,
        "suggestion": report.suggestion,
        "agent_results": report.agent_results,
        "processed_at": report.processed_at.isoformat() if report.processed_at else None,
    }


@router.post("/{claim_id}/decision")
async def submit_claim_decision(claim_id: str, request: ClaimDecisionRequest):
    """Record the adjuster's final decision on a claim (approve or reject)."""
    if request.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    new_status = "approved" if request.decision == "approve" else "rejected"
    await claim_db.update_claim_status(claim_id, new_status)

    logger.info(f"[Claim {claim_id}] Decision: {new_status}. Notes: {request.notes}")
    return {"claim_id": claim_id, "decision": new_status, "notes": request.notes}


@router.delete("/{claim_id}")
async def delete_claim(claim_id: str):
    """
    Permanently delete a claim and all its linked document associations.
    Does NOT delete the underlying document files from storage.
    """
    deleted = await claim_db.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return {"claim_id": claim_id, "deleted": True}

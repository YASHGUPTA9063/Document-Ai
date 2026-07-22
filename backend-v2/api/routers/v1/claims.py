"""
Claims Routes (v1)
==================
Handles claim creation, listing, status, execution, and decisions.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from db.database import AsyncSessionLocal
from db.models import Claim
import db.claim_operations as claim_db
from schemas.claims import (
    CreateClaimRequest,
    ClaimResponse,
    ClaimStatusResponse,
    ClaimReportResponse,
    ClaimDecisionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["Claims"])


@router.post("", response_model=ClaimResponse)
async def create_claim(request: CreateClaimRequest):
    """Create a new empty claim."""
    try:
        claim_id = await claim_db.create_claim(
            customer_id=request.customer_id,
            claim_type=request.claim_type,
            metadata=request.metadata,
        )
        return ClaimResponse(
            id=claim_id,
            status="pending",
            message="Claim created successfully. You can now upload documents linked to this claim.",
        )
    except Exception as e:
        logger.error(f"Error creating claim: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_claims():
    """List all claims."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).order_by(Claim.created_at.desc())
        )
        claims = result.scalars().all()
        return [
            {
                "id": c.id,
                "customer_id": c.customer_id,
                "claim_type": c.claim_type,
                "status": c.status,
                "created_at": c.created_at,
                "workflow_run_id": c.workflow_run_id,
                "message": c.error_details.get("error", "") if c.error_details else "",
            }
            for c in claims
        ]


@router.get("/{claim_id}/status", response_model=ClaimStatusResponse)
async def get_claim_status(claim_id: str):
    """Get the overall status of a claim and all its linked documents."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).options(selectinload(Claim.documents)).where(Claim.id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        docs_status = []
        for d in claim.documents:
            docs_status.append(
                {
                    "document_id": d.id,
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "status": d.status,
                }
            )

        return ClaimStatusResponse(
            claim_id=claim.id,
            status=claim.status,
            documents=docs_status,
            workflow_run_id=claim.workflow_run_id,
            message=claim.error_details.get("error", "") if claim.error_details else "",
        )

@router.post("/{claim_id}/run")
async def run_claim_workflow(request: Request, claim_id: str):
    """Trigger the claim-level AI workflow."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        if claim.status in ("processing", "evaluating"):
            raise HTTPException(status_code=409, detail="Claim workflow is already running")

        claim.status = "processing"
        claim.error_details = None
        await session.commit()

        # Start claim pipeline in background
        import asyncio
        from platform_core.pipeline.definitions import build_claim_pipeline
        from platform_core.pipeline.engine import PipelineEngine
        from platform_core.pipeline.checkpoint import CheckpointManager
        from platform_core.config import load_config

        try:
            redis_pool = getattr(request.app.state, "redis_pool", None)
            if redis_pool:
                await redis_pool.enqueue_job(
                    "run_claim_pipeline",
                    claim_id=claim.id,
                    claimant_id=claim.claimant_id,
                    policy_id=claim.policy_id,
                )
            else:
                config = load_config()
                pipeline = build_claim_pipeline(config)
                engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
                asyncio.create_task(
                    engine.run(
                        pipeline=pipeline,
                        context={"claim_id": claim.id, "claimant_id": claim.claimant_id, "policy_id": claim.policy_id},
                    )
                )
            return {"message": "Claim workflow started", "claim_id": claim.id}
        except Exception as e:
            logger.error(f"Failed to start claim workflow: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start workflow: {e}")


@router.get("/{claim_id}/report")
async def get_claim_report(claim_id: str):
    """Get the final structured report and suggestion for a claim."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        return {
            "claim_id": claim.id,
            "status": claim.status,
            "extracted_claim_data": claim.extracted_claim_data,
            "discrepancies": claim.discrepancies,
            "final_suggestion": claim.final_suggestion,
            "reviewer_decision": claim.reviewer_decision,
        }


@router.post("/{claim_id}/decision")
async def submit_claim_decision(claim_id: str, request: ClaimDecisionRequest):
    """Submit the final human decision (Approve/Reject) for a claim."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        claim.reviewer_decision = {
            "decision": request.decision,
            "reason": request.reason,
            "timestamp": "now", # Ideally use actual timestamp
        }
        claim.status = "completed" if request.decision.lower() == "approve" else "rejected"
        await session.commit()

        return {"message": f"Decision '{request.decision}' recorded successfully"}


@router.delete("/{claim_id}")
async def delete_claim(claim_id: str):
    """Soft-delete a claim."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        claim.status = "deleted"
        await session.commit()
        return {"message": f"Claim {claim_id} deleted"}

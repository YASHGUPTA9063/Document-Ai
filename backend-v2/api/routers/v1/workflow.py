"""
Workflow Routes (v1)
====================
Handles resuming workflows that are paused for Human-In-The-Loop (HITL) input.
"""

import logging
from fastapi import APIRouter, HTTPException

from schemas.documents import DuplicateDecisionRequest, ReviewerDecisionRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["Workflow"])


@router.post("/{pipeline_id}/resume/duplicate")
async def resume_duplicate(pipeline_id: str, decision: DuplicateDecisionRequest):
    """
    Resume a pipeline paused at the intake duplicate check.
    """
    try:
        import asyncio
        from platform_core.pipeline.definitions import build_document_pipeline
        from platform_core.pipeline.engine import PipelineEngine
        from platform_core.pipeline.checkpoint import CheckpointManager
        from platform_core.config import load_config

        cp_mgr = CheckpointManager()
        checkpoint = await cp_mgr.load(pipeline_id)
        
        if not checkpoint:
            raise HTTPException(status_code=409, detail="Pipeline is not paused or checkpoint not found.")
            
        context = checkpoint.get("context", {})
        if context.get("_paused_at") != "intake":
             raise HTTPException(status_code=409, detail=f"Pipeline is not paused at intake (currently at {context.get('_paused_at')}).")

        # Inject human decision into context
        context["duplicate_override"] = decision.override
        
        # Resume pipeline
        config = load_config()
        pipeline = build_document_pipeline(config)
        engine = PipelineEngine(checkpoint_mgr=cp_mgr)
        
        asyncio.create_task(
            engine.run(
                pipeline=pipeline,
                context=context,
            )
        )
        return {"message": "Pipeline resumed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming duplicate check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pipeline_id}/resume/review")
async def resume_review(pipeline_id: str, decision: ReviewerDecisionRequest):
    """
    Resume a pipeline paused at human review.
    """
    try:
        import asyncio
        from platform_core.pipeline.definitions import build_document_pipeline
        from platform_core.pipeline.engine import PipelineEngine
        from platform_core.pipeline.checkpoint import CheckpointManager
        from platform_core.config import load_config

        cp_mgr = CheckpointManager()
        checkpoint = await cp_mgr.load(pipeline_id)
        
        if not checkpoint:
            raise HTTPException(status_code=409, detail="Pipeline is not paused or checkpoint not found.")
            
        context = checkpoint.get("context", {})
        if context.get("_paused_at") != "review":
             raise HTTPException(status_code=409, detail=f"Pipeline is not paused at review (currently at {context.get('_paused_at')}).")

        # Inject human decision into context
        context["human_review_decision"] = {
            "approved": decision.approved,
            "corrections": decision.corrections,
            "rejection_reason": decision.rejection_reason
        }
        
        # Resume pipeline
        config = load_config()
        pipeline = build_document_pipeline(config)
        engine = PipelineEngine(checkpoint_mgr=cp_mgr)
        
        asyncio.create_task(
            engine.run(
                pipeline=pipeline,
                context=context,
            )
        )
        return {"message": "Pipeline resumed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming review: {e}")
        raise HTTPException(status_code=500, detail=str(e))

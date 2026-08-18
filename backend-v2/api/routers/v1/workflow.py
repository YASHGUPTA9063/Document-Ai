"""
Workflow Routes (v1)
====================
Handles resuming workflows that are paused for Human-In-The-Loop (HITL) input.
"""

import logging
from fastapi import APIRouter, HTTPException, Request

from schemas.documents import DuplicateDecisionRequest, ReviewerDecisionRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["Workflow"])


async def _restart_document_pipeline(request: Request, doc, context_overrides: dict):
    """Kick off a fresh pipeline run for a document, via the worker if available."""
    import asyncio

    redis_pool = getattr(request.app.state, "redis_pool", None)
    if redis_pool:
        await redis_pool.enqueue_job(
            "run_document_pipeline",
            document_id=doc.id,
            filename=doc.filename,
            file_path=doc.file_path,
            context_overrides=context_overrides,
        )
        return

    from platform_core.pipeline.definitions import build_document_pipeline
    from platform_core.pipeline.engine import PipelineEngine
    from platform_core.pipeline.checkpoint import CheckpointManager
    from platform_core.config import load_config

    pipeline = build_document_pipeline(load_config())
    engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
    asyncio.create_task(
        engine.run(
            pipeline=pipeline,
            context={
                "document_id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                **context_overrides,
            },
        )
    )


@router.post("/{pipeline_id}/resume/duplicate")
async def resume_duplicate(request: Request, pipeline_id: str, decision: DuplicateDecisionRequest):
    """
    Apply a reviewer's decision on a document flagged as a duplicate.

    Two engines land here:
      - Local PipelineEngine: the run is genuinely paused mid-pipeline with a
        checkpoint, so the decision is injected and the run continues.
      - Mistral Workflows: the cloud run already ended at the intake gate, so
        there is nothing to resume — an override re-runs the pipeline with the
        duplicate check disabled, and a rejection just marks the document.
    """
    try:
        import asyncio
        import db.operations as db
        from platform_core.pipeline.definitions import build_document_pipeline
        from platform_core.pipeline.engine import PipelineEngine
        from platform_core.pipeline.checkpoint import CheckpointManager
        from platform_core.config import load_config

        cp_mgr = CheckpointManager()
        checkpoint = await cp_mgr.load(pipeline_id)

        # ── Local engine: a real paused run exists ────────────────────────
        if checkpoint:
            context = checkpoint.get("context", {})
            if context.get("_paused_at") != "intake":
                raise HTTPException(
                    status_code=409,
                    detail=f"Pipeline is not paused at intake (currently at {context.get('_paused_at')}).",
                )

            if not decision.override:
                await cp_mgr.clear(pipeline_id)
                await db.update_status_and_message(
                    pipeline_id, "rejected", "Rejected as a duplicate by reviewer."
                )
                return {"message": "Document rejected as duplicate", "status": "rejected"}

            context["skip_duplicate_check"] = True
            context["duplicate_override"] = True

            pipeline = build_document_pipeline(load_config())
            engine = PipelineEngine(checkpoint_mgr=cp_mgr)
            asyncio.create_task(engine.run(pipeline=pipeline, context=context))
            return {"message": "Pipeline resumed", "status": "processing"}

        # ── Cloud engine: nothing to resume, act on the document ──────────
        doc = await db.get_document(pipeline_id)
        if not doc or doc.status == "deleted":
            raise HTTPException(status_code=404, detail="Document not found.")

        if doc.status != "duplicate":
            raise HTTPException(
                status_code=409,
                detail=f"Document is not awaiting a duplicate decision (status: '{doc.status}').",
            )

        if not decision.override:
            await db.update_status_and_message(
                pipeline_id, "rejected", "Rejected as a duplicate by reviewer."
            )
            return {"message": "Document rejected as duplicate", "status": "rejected"}

        await db.update_status_and_message(
            pipeline_id, "pending", "Duplicate overridden by reviewer — reprocessing."
        )
        await _restart_document_pipeline(request, doc, {"skip_duplicate_check": True})
        return {"message": "Duplicate overridden, pipeline restarted", "status": "pending"}

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

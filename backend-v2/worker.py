"""
Background Task Worker (arq)
============================
Processes document and claim pipelines asynchronously using Redis.

Supports two execution engines:
  - Mistral Workflows SDK (when provider is Mistral and workflow_engine != "local")
  - Local PipelineEngine (fallback for non-Mistral providers or explicit "local" config)
"""

import asyncio
import logging
from arq import Worker
from arq.connections import RedisSettings

from config import settings
from platform_core.config import load_config
from platform_core.registry import ProviderRegistry
from platform_core.pipeline.definitions import build_document_pipeline, build_claim_pipeline
from platform_core.pipeline.engine import PipelineEngine
from platform_core.pipeline.checkpoint import CheckpointManager

from logging_config import setup_logging

# Configure structured JSON logging
setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
logger = logging.getLogger(__name__)


# ─── Engine Detection ────────────────────────────────────────────────────────

def _should_use_mistral_workflow(platform_config: dict) -> bool:
    """
    Determine if the Mistral Workflows SDK should be used for document processing.

    Rules:
      - workflow_engine: "mistral" → always use Mistral
      - workflow_engine: "local"   → always use local PipelineEngine
      - workflow_engine: "auto" (default) → use Mistral if the default LLM is Mistral
    """
    pipeline_config = platform_config.get("pipelines", {}).get("document_processing", {})
    engine_setting = pipeline_config.get("workflow_engine", "auto")

    if engine_setting == "local":
        return False
    if engine_setting == "mistral":
        return True

    # "auto" — check if the default LLM chain is Mistral
    fallback_chains = platform_config.get("fallback_chains", {})
    default_chain = fallback_chains.get("llm.default", [])
    return len(default_chain) > 0 and default_chain[0] == "mistral"


# ─── Worker Lifecycle ────────────────────────────────────────────────────────

_mistral_worker_task = None  # Background task running the Mistral workflow worker


async def startup(ctx):
    """Run on worker startup."""
    logger.info("Initializing worker environment...")
    platform_config = load_config()
    registry = ProviderRegistry.from_config(platform_config)

    # Preload models if needed
    try:
        registry.get_embedding("dinov2")
    except Exception as e:
        logger.warning(f"Failed to preload models in worker: {e}")

    ctx['registry'] = registry
    ctx['platform_config'] = platform_config
    ctx['checkpoint_mgr'] = CheckpointManager()

    # Determine workflow engine
    use_mistral = _should_use_mistral_workflow(platform_config)
    ctx['use_mistral_workflow'] = use_mistral

    if use_mistral:
        logger.info("[Worker] Mistral Workflows SDK enabled — starting workflow worker...")
        global _mistral_worker_task
        _mistral_worker_task = asyncio.create_task(_start_mistral_worker())
    else:
        logger.info("[Worker] Using local PipelineEngine for document processing")


async def _start_mistral_worker():
    """Start the Mistral Workflows worker in a background task."""
    try:
        import mistralai.workflows as workflows
        from platform_core.pipeline.mistral_workflow import DocumentProcessingWorkflow

        logger.info("[MistralWorker] Starting Mistral Workflows worker...")
        await workflows.run_worker([DocumentProcessingWorkflow])
    except Exception as e:
        logger.error(f"[MistralWorker] Failed to start Mistral workflow worker: {e}")


async def shutdown(ctx):
    """Run on worker shutdown."""
    logger.info("Shutting down worker...")
    global _mistral_worker_task
    if _mistral_worker_task and not _mistral_worker_task.done():
        _mistral_worker_task.cancel()
        try:
            await _mistral_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("[MistralWorker] Mistral workflow worker stopped")


# ─── Document Pipeline Task ─────────────────────────────────────────────────

async def run_document_pipeline(ctx, document_id: str, filename: str, file_path: str, context_overrides: dict = None):
    """
    Task to execute the document processing pipeline.

    Routes to Mistral Workflows SDK or local PipelineEngine based on config.
    """
    logger.info(f"Starting pipeline task for document {document_id}")

    if ctx.get('use_mistral_workflow'):
        return await _run_mistral_document_pipeline(
            document_id, filename, file_path,
            ctx['platform_config'],
            context_overrides,
        )
    else:
        return await _run_local_document_pipeline(
            ctx, document_id, filename, file_path, context_overrides,
        )


async def _run_mistral_document_pipeline(
    document_id: str,
    filename: str,
    file_path: str,
    platform_config: dict,
    context_overrides: dict = None,
) -> dict:
    """Execute the document pipeline using Mistral's native Workflows SDK."""
    import mistralai.workflows as workflows
    from platform_core.pipeline.mistral_workflow import DocumentProcessingWorkflow, DocumentInput

    logger.info(f"[MistralWorkflow] Triggering workflow for document {document_id}")

    # Build input
    pipeline_config = platform_config.get("pipelines", {}).get("document_processing", {})
    workflow_input = DocumentInput(
        document_id=document_id,
        filename=filename,
        file_path=file_path,
        enable_pre_validation=pipeline_config.get("enable_pre_validation", True),
        enable_preprocessing=pipeline_config.get("enable_preprocessing", False),
    )

    # Execute the workflow
    result = await workflows.execute_workflow(
        workflow=DocumentProcessingWorkflow,
        params=workflow_input,
        execution_id=f"doc-pipeline-{document_id}",
    )

    logger.info(f"[MistralWorkflow] Completed workflow for document {document_id}: status={result.status}")
    return {
        "document_id": result.document_id,
        "status": result.status,
        "doc_type": result.doc_type,
        "error": result.error,
    }


async def _run_local_document_pipeline(
    ctx, document_id: str, filename: str, file_path: str, context_overrides: dict = None,
) -> dict:
    """Execute the document pipeline using the local PipelineEngine (fallback)."""
    logger.info(f"[LocalEngine] Running pipeline for document {document_id}")

    pipeline = build_document_pipeline(ctx['platform_config'])
    engine = PipelineEngine(checkpoint_mgr=ctx['checkpoint_mgr'])

    base_context = {
        "document_id": document_id,
        "filename": filename,
        "file_path": file_path,
    }

    if context_overrides:
        base_context.update(context_overrides)

    result = await engine.run(
        pipeline=pipeline,
        context=base_context,
    )

    logger.info(f"Completed pipeline task for document {document_id}")
    return result


# ─── Claim Pipeline Task ────────────────────────────────────────────────────

async def run_claim_pipeline(ctx, claim_id: str, claimant_id: str, policy_id: str):
    """
    Task to execute the claim processing pipeline.
    Always uses the local PipelineEngine (Mistral Workflows not implemented for claims yet).
    """
    logger.info(f"Starting pipeline task for claim {claim_id}")

    pipeline = build_claim_pipeline(ctx['platform_config'])
    engine = PipelineEngine(checkpoint_mgr=ctx['checkpoint_mgr'])

    base_context = {
        "claim_id": claim_id,
        "claimant_id": claimant_id,
        "policy_id": policy_id,
    }

    result = await engine.run(
        pipeline=pipeline,
        context=base_context,
    )

    logger.info(f"Completed pipeline task for claim {claim_id}")
    return result


# ─── arq Worker Settings ────────────────────────────────────────────────────

class WorkerSettings:
    """arq worker settings."""
    # Parse REDIS_URL from env or default to localhost
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")

    # We parse the URL for arq
    import urllib.parse
    parsed = urllib.parse.urlparse(redis_url)

    redis_settings = RedisSettings(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 6379,
        database=int((parsed.path or '/0').lstrip('/')),
        password=parsed.password
    )

    functions = [run_document_pipeline, run_claim_pipeline]
    on_startup = startup
    on_shutdown = shutdown

    # Adjust concurrency as needed
    max_jobs = 10

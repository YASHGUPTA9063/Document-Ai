"""
Background Task Worker (arq)
============================
Processes document and claim pipelines asynchronously using Redis.
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


async def shutdown(ctx):
    """Run on worker shutdown."""
    logger.info("Shutting down worker...")


async def run_document_pipeline(ctx, document_id: str, filename: str, file_path: str, context_overrides: dict = None):
    """
    Task to execute the document processing pipeline.
    """
    logger.info(f"Starting pipeline task for document {document_id}")
    
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


async def run_claim_pipeline(ctx, claim_id: str, claimant_id: str, policy_id: str):
    """
    Task to execute the claim processing pipeline.
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

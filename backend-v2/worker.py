"""
Dispatcher worker (arq)
=======================
Takes uploads off the Redis queue and starts the corresponding Mistral Studio
run. That is all it does — it never executes a pipeline step. The steps run in
`workflow_worker.py`, dispatched there by Studio.

Why a queue in front of a single API call: starting a run is a network call to
Mistral, and doing it inside the upload request couples the user's upload to
Mistral's availability. Here a dispatch failure is retried with backoff and the
upload has long since returned 202. `EXECUTION_MODE=inline` skips this process
entirely for local runs where no Redis exists.

Run it with:
    arq worker.WorkerSettings
"""

import logging
import urllib.parse

from arq.connections import RedisSettings

from config import settings
from logging_config import setup_logging

setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
logger = logging.getLogger(__name__)


# ─── Worker lifecycle ────────────────────────────────────────────────────────

async def startup(ctx):
    """
    Bring up only what dispatching needs.

    No DINOv2 and no health monitor: this process resolves no providers and
    runs no activities, so loading embedding weights here would waste a
    gigabyte of RSS per replica for a model it never calls.
    """
    from bootstrap import init_platform, assert_workflow_binding

    await init_platform(
        "dispatcher",
        start_health_monitor=False,
        preload_dinov2=False,
    )
    assert_workflow_binding()
    logger.info("[Dispatcher] Ready — starting runs on deployment '%s'", settings.DEPLOYMENT_NAME)


async def shutdown(ctx):
    from bootstrap import shutdown_platform
    await shutdown_platform()
    logger.info("[Dispatcher] Stopped")


# ─── Jobs ────────────────────────────────────────────────────────────────────

async def run_document_pipeline(
    ctx,
    document_id: str,
    filename: str,
    file_path: str,
    auto_split: bool = True,
    preclassified_doc_type: str = "",
    preclassified_confidence: float = 0.0,
    preclassified_reasoning: str = "",
):
    """
    Start the document workflow on Mistral Studio.

    Raising on failure is deliberate: arq retries the job with backoff, which is
    the entire reason dispatch sits behind a queue. `start_document_run_and_record`
    has already marked the document failed and written the reason, so a document
    that exhausts every retry is visible in the UI rather than stuck at pending.
    """
    from platform_core.dispatch import start_document_run_and_record

    logger.info("[Dispatcher] Dispatching document %s (attempt %s)", document_id, ctx.get("job_try", 1))

    run_id = await start_document_run_and_record(
        document_id,
        filename,
        file_path,
        auto_split=auto_split,
        preclassified_doc_type=preclassified_doc_type,
        preclassified_confidence=preclassified_confidence,
        preclassified_reasoning=preclassified_reasoning,
    )

    logger.info("[Dispatcher] Document %s running as execution %s", document_id, run_id)
    return {"document_id": document_id, "workflow_run_id": run_id, "status": "dispatched"}


async def run_claim_pipeline(ctx, claim_id: str, claimant_id: str, policy_id: str):
    """Start the claim workflow on Mistral Studio and record the run id."""
    from platform_core.dispatch import start_claim_run
    import db.claim_operations as claim_db

    logger.info("[Dispatcher] Dispatching claim %s (attempt %s)", claim_id, ctx.get("job_try", 1))

    run_id = await start_claim_run(claim_id, claimant_id, policy_id)
    await claim_db.set_claim_run_id(claim_id, run_id, status="processing")

    logger.info("[Dispatcher] Claim %s running as execution %s", claim_id, run_id)
    return {"claim_id": claim_id, "workflow_run_id": run_id, "status": "dispatched"}


# ─── arq settings ────────────────────────────────────────────────────────────

def _redis_settings() -> RedisSettings:
    parsed = urllib.parse.urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/")),
        password=parsed.password,
    )


class WorkerSettings:
    """arq worker settings."""

    redis_settings = _redis_settings()

    functions = [run_document_pipeline, run_claim_pipeline]
    on_startup = startup
    on_shutdown = shutdown

    # Dispatch is a single API call, so a job should never run long. A low
    # timeout turns a hung Mistral connection into a retry instead of a
    # permanently occupied worker slot.
    job_timeout = 60

    # Five attempts over exponential backoff covers a Mistral blip or a
    # redeploy without giving up on the document.
    max_tries = 5

    # Dispatching is cheap and IO-bound; the real concurrency limit lives in
    # the workflow worker, which is where the actual work happens.
    max_jobs = 20

    # Keep finished job results long enough to debug a failed dispatch.
    keep_result = 3600

"""
Dispatch queue client
=====================
Owns the one decision every upload path needs: does this run get handed to the
arq dispatcher, or started here and now?

  EXECUTION_MODE=queue   the production path. The API enqueues and returns; the
                         dispatcher (worker.py) starts the Studio run with
                         retry and backoff, so a Mistral blip never fails an
                         upload.
  EXECUTION_MODE=inline  the API starts the Studio run in the request handler.
                         No Redis needed, which is what makes a bare
                         `uvicorn main:app` a working stack in a local venv.

The mode is explicit rather than "use Redis if it happens to be reachable".
A silent fallback means a production deployment can quietly lose its retry
behaviour the moment Redis blips, with nothing to show for it.
"""

import logging
import urllib.parse
import uuid

from arq import create_pool
from arq.connections import RedisSettings

from config import settings

logger = logging.getLogger(__name__)

_pool = None


def _redis_settings() -> RedisSettings:
    parsed = urllib.parse.urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/")),
        password=parsed.password,
    )


async def get_redis_pool():
    """
    The process-wide arq pool, created on first use.

    A pool per request would open a TCP connection per upload; this keeps one
    for the process and lets main.py close it on shutdown.
    """
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
        logger.info("[Queue] Redis pool connected (%s)", settings.REDIS_URL)
    return _pool


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception as e:
            logger.warning("[Queue] Pool close failed: %s", e)
        _pool = None


async def ping() -> bool:
    """True when Redis answers. Backs GET /ready under EXECUTION_MODE=queue."""
    try:
        pool = await get_redis_pool()
        await pool.ping()
        return True
    except Exception as e:
        logger.warning("[Queue] Ping failed: %s", e)
        return False


async def submit_document_run(
    document_id: str,
    filename: str,
    file_path: str,
    *,
    auto_split: bool = True,
    preclassified_doc_type: str = "",
    preclassified_confidence: float = 0.0,
    preclassified_reasoning: str = "",
    job_key: str | None = None,
) -> str | None:
    """
    Get a document processing.

    Returns the Studio execution id under `inline`, or None under `queue` —
    where the id is not known until the dispatcher starts the run and writes it
    to the document row itself. Callers must treat None as "started, id
    pending" rather than as a failure.

    `job_key` is the arq deduplication key. It defaults to the document id,
    which makes a double-submitted upload a no-op. A deliberate re-run (the
    retry endpoint) must pass a fresh key: arq refuses to enqueue a job whose
    id it still holds a result for, so reusing the default would drop the
    retry silently for as long as WorkerSettings.keep_result.
    """
    kwargs = {
        "auto_split": auto_split,
        "preclassified_doc_type": preclassified_doc_type,
        "preclassified_confidence": preclassified_confidence,
        "preclassified_reasoning": preclassified_reasoning,
    }

    if settings.EXECUTION_MODE == "inline":
        from platform_core.dispatch import start_document_run_and_record
        return await start_document_run_and_record(document_id, filename, file_path, **kwargs)

    pool = await get_redis_pool()
    await pool.enqueue_job(
        "run_document_pipeline",
        document_id,
        filename,
        file_path,
        _job_id=job_key or f"doc-{document_id}",
        **kwargs,
    )
    logger.info("[Queue] Enqueued document %s for dispatch", document_id)
    return None


async def submit_claim_run(claim_id: str, claimant_id: str, policy_id: str) -> str | None:
    """Get a claim processing. Same return contract as submit_document_run."""
    if settings.EXECUTION_MODE == "inline":
        from platform_core.dispatch import start_claim_run
        import db.claim_operations as claim_db

        run_id = await start_claim_run(claim_id, claimant_id, policy_id)
        await claim_db.set_claim_run_id(claim_id, run_id, status="processing")
        return run_id

    pool = await get_redis_pool()
    # Unique per call, not per claim: /claims/{id}/rerun is an explicit user
    # action and must never be deduplicated against the previous run. The
    # endpoints already gate on claim status, so this cannot be double-fired
    # by accident.
    await pool.enqueue_job(
        "run_claim_pipeline",
        claim_id,
        claimant_id,
        policy_id,
        _job_id=f"claim-{claim_id}-{uuid.uuid4().hex[:8]}",
    )
    logger.info("[Queue] Enqueued claim %s for dispatch", claim_id)
    return None

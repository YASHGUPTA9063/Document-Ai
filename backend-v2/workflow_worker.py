"""
Mistral Studio workflow worker
==============================
The process that actually does the work. Mistral Studio owns the orchestration
— durability, retries, and the 24-hour human-input waits — and dispatches each
workflow and activity to a worker registered under DEPLOYMENT_NAME. This is
that worker.

Run it with:
    python workflow_worker.py

It used to be an `asyncio.create_task` inside the FastAPI lifespan, which meant
the API could only ever run one uvicorn worker (a second one would register a
duplicate worker pool and double-execute activities) and that CPU-bound
activities competed with HTTP request handling on the same event loop. As its
own process it scales independently:

    docker compose up -d --scale workflow-worker=3

## Deploying a change to workflow.py

Studio replays an in-flight execution's history against whatever code the pool
is running. A document parked at a 24h `wait_for_input` will still be replaying
tomorrow. So a change to the *step sequence* in workflow.py is not a
hot-deployable edit:

  1. bump DEPLOYMENT_NAME (it is a version — see config.py)
  2. start the new pool alongside the old one
  3. let the old pool drain its in-flight executions, then stop it

Editing only an activity's body is safe; activities are not replayed.
"""

import asyncio
import logging
import os
import signal

# The SDK validates these on import, so they have to be in os.environ before
# `import mistralai.workflows` runs — not after.
from config import settings

os.environ.setdefault("MISTRAL_API_KEY", settings.MISTRAL_API_KEY)
os.environ.setdefault("DEPLOYMENT_NAME", settings.DEPLOYMENT_NAME)

# Installs the timing hooks the performance reports are built from. Imported
# before the activities so it can wrap them.
from utils.perf_logger import install_performance_hooks  # noqa: E402

install_performance_hooks()

import mistralai.workflows as workflows  # noqa: E402

from logging_config import setup_logging  # noqa: E402
from bootstrap import init_platform, shutdown_platform, assert_agent_bindings  # noqa: E402
from db.database import init_db  # noqa: E402
from workflow import DocumentProcessingWorkflow  # noqa: E402
from claim_workflow import ClaimProcessingWorkflow  # noqa: E402

setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
logger = logging.getLogger(__name__)

WORKFLOWS = [DocumentProcessingWorkflow, ClaimProcessingWorkflow]


async def main() -> None:
    logger.info(
        "[WorkflowWorker] Starting — deployment=%s, workflows=%s",
        settings.DEPLOYMENT_NAME,
        [w.__name__ for w in WORKFLOWS],
    )

    # Activities read and write the database directly, so the schema has to be
    # reachable. On a Postgres deployment alembic has already run in the
    # entrypoint; this is a no-op there.
    await init_db()

    # The registry populated here is what activities/extractor.py resolves the
    # vLLM fallback through, and the DINOv2 preload is what keeps the first KYC
    # document from paying a model download inside an activity timeout.
    # Skipping either fails silently rather than loudly — see bootstrap.py.
    await init_platform("workflow-worker")
    assert_agent_bindings()

    stop = asyncio.Event()

    def _request_stop(signum, _frame):
        logger.info("[WorkflowWorker] Signal %s received — draining", signum)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, AttributeError, OSError):
            # Not every platform/thread combination allows handler installation
            # (Windows lacks SIGTERM semantics); fall back to SDK-level cancel.
            pass

    worker_task = asyncio.create_task(workflows.run_worker(WORKFLOWS))
    stop_task = asyncio.create_task(stop.wait())

    done, pending = await asyncio.wait(
        {worker_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )

    if worker_task in done:
        # The worker exited on its own — surface why rather than exiting 0.
        exc = worker_task.exception()
        if exc:
            logger.error("[WorkflowWorker] Worker stopped with an error: %s", exc)
            for task in pending:
                task.cancel()
            await shutdown_platform()
            raise exc
        logger.warning("[WorkflowWorker] Worker returned unexpectedly")
    else:
        logger.info("[WorkflowWorker] Draining in-flight activities...")
        worker_task.cancel()
        try:
            await asyncio.wait_for(worker_task, timeout=30)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    for task in pending:
        task.cancel()

    await shutdown_platform()
    logger.info("[WorkflowWorker] Stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

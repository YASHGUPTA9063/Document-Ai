"""
Document AI Platform — API entrypoint
=====================================
Serves HTTP and nothing else. It writes the intake row, hands the document to
the dispatcher, and answers status and review queries. It never executes a
pipeline step.

Execution happens on Mistral Studio, which dispatches workflows and activities
to `workflow_worker.py` — its own process, registered under DEPLOYMENT_NAME.
That separation is what lets this app run several uvicorn workers: the previous
build started `workflows.run_worker(...)` as an asyncio task in the lifespan, so
a second uvicorn worker would have registered a duplicate pool and executed
every activity twice.

Routers are mounted under `/api/v1` (canonical) and, while
ENABLE_LEGACY_ROOT_ROUTES is on, also at the root for the older frontend
contract. Both mounts serve the same handler objects, so there is no drift.
"""

import os
import logging
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.database import init_db, init_claim_tables, ping as db_ping
from bootstrap import (
    init_platform,
    shutdown_platform,
    platform_state,
    assert_agent_bindings,
    assert_workflow_binding,
)
from api.routers.v1 import build_root_router, build_v1_router

try:
    from logging_config import setup_logging

    setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
except Exception:  # pragma: no cover — fall back to stdlib logging
    logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)

logger = logging.getLogger(__name__)

# Only set when RUN_WORKFLOW_WORKER_IN_API is on — a local-dev convenience so a
# single `uvicorn` command is a complete stack. Never used in Docker.
_embedded_worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Initializing database...")
    await init_db()
    await init_claim_tables()

    logger.info("Ensuring storage directory exists...")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    # Shared with workflow_worker.py so both processes resolve providers the
    # same way. The API needs it for /documents/{id}/verify-signature, which
    # runs DINOv2 in-process.
    await init_platform("api")
    assert_agent_bindings()

    if settings.EXECUTION_MODE == "inline":
        # Inline dispatch means this process starts Studio runs itself, so it
        # needs a workflow to start.
        assert_workflow_binding()
    else:
        # Connect the pool up front rather than on the first upload: a broken
        # REDIS_URL should show up at boot and in /ready, not as one user's
        # failed upload minutes later.
        from api.queue import get_redis_pool
        try:
            await get_redis_pool()
        except Exception as e:
            logger.error(
                "Redis is unreachable at %s and EXECUTION_MODE=queue — uploads "
                "will fail until it recovers. %s", settings.REDIS_URL, e,
            )

    if settings.RUN_WORKFLOW_WORKER_IN_API:
        logger.warning(
            "RUN_WORKFLOW_WORKER_IN_API=true — hosting the Mistral workflow worker "
            "inside the API process. Local development only: run a single uvicorn "
            "worker, or activities will execute more than once."
        )
        import asyncio
        import mistralai.workflows as workflows
        from workflow import DocumentProcessingWorkflow
        from claim_workflow import ClaimProcessingWorkflow

        os.environ.setdefault("MISTRAL_API_KEY", settings.MISTRAL_API_KEY)
        os.environ.setdefault("DEPLOYMENT_NAME", settings.DEPLOYMENT_NAME)

        global _embedded_worker_task
        _embedded_worker_task = asyncio.create_task(
            workflows.run_worker([DocumentProcessingWorkflow, ClaimProcessingWorkflow])
        )

    logger.info(
        "API ready — execution_mode=%s, legacy_root_routes=%s",
        settings.EXECUTION_MODE,
        settings.ENABLE_LEGACY_ROOT_ROUTES,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    # No os._exit() here. The previous build called it to escape a workflow
    # worker that would not cancel, which also skipped every other shutdown
    # hook and gave in-flight requests no chance to finish.
    if _embedded_worker_task and not _embedded_worker_task.done():
        import asyncio
        _embedded_worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
            await asyncio.wait_for(_embedded_worker_task, timeout=10.0)

    if settings.EXECUTION_MODE == "queue":
        from api.queue import close_redis_pool
        with contextlib.suppress(Exception):
            await close_redis_pool()

    await shutdown_platform()
    logger.info("API stopped")


app = FastAPI(
    title="Document AI Platform",
    version="1.0",
    lifespan=lifespan,
)

# `allow_credentials=True` with `allow_origins=["*"]` is rejected by browsers —
# the wildcard cannot be echoed back on a credentialed request. Set
# CORS_ORIGINS to real origins in production and credentials turn on with them.
_allow_credentials = "*" not in settings.CORS_ORIGINS
if not _allow_credentials and not settings.DEBUG:
    logger.warning(
        "CORS_ORIGINS is '*' — credentialed cross-origin requests will be refused "
        "by the browser. Set explicit origins for production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Canonical, versioned surface.
app.include_router(build_v1_router())

# Legacy unprefixed paths, for frontend builds predating the /api/v1 move.
if settings.ENABLE_LEGACY_ROOT_ROUTES:
    app.include_router(build_root_router())


@app.get("/health", tags=["Platform"])
async def health():
    """
    Liveness. Always reports up so a degraded provider never causes an
    orchestrator to restart a perfectly serviceable container. Use /ready for
    the question "should traffic go here".
    """
    state = platform_state()
    return {
        "status": "ok",
        "execution_mode": state["execution_mode"],
        "providers": state["providers"],
        "circuit_breakers": state["circuit_breakers"],
    }


@app.get("/ready", tags=["Platform"])
async def ready():
    """
    Readiness: can this process actually serve requests, and is the deployment
    bound to everything it needs?

    Reports 503 when the database is unreachable or a required Studio agent is
    unbound. Redis only counts when EXECUTION_MODE=queue — under `inline` there
    is no queue to be unready for.
    """
    from fastapi.responses import JSONResponse

    state = platform_state()
    checks: dict = {"database": await db_ping()}

    if settings.EXECUTION_MODE == "queue":
        from api.queue import ping as redis_ping
        checks["redis"] = await redis_ping()

    agents = state["agents"]
    checks["required_agents_bound"] = not agents["required_missing"]
    checks["workflow_id_bound"] = agents["workflow_id_bound"]

    ok = all(checks.values())
    body = {
        "status": "ready" if ok else "not_ready",
        "checks": checks,
        "execution_mode": state["execution_mode"],
        "deployment_name": state["deployment_name"],
        "agents": agents,
        "provider_health": state["provider_health"],
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)

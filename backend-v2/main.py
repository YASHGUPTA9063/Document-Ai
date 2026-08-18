"""
Document AI Platform — Main Application Entrypoint
==================================================
Thin entrypoint: initializes platform_core (config, provider registry, health
monitor), boots the database, starts the Mistral Workflow worker, and mounts
the v1 API routers.

All endpoints previously defined inline here now live in api/routers/v1/*.
They are mounted twice — at the root (branch-vm3's original paths, which the
shipped frontend calls) and under /api/v1 (the versioned surface adopted from
`development`). Both mounts serve the same handlers.

Document and claim processing continue to run on the Mistral Workflows SDK
via workflow.DocumentProcessingWorkflow and claim_workflow.ClaimProcessingWorkflow.
platform_core's PipelineEngine is available (see platform_core/pipeline/) but
is deliberately not placed in front of those workflows.
"""

import os

os.environ["DEPLOYMENT_NAME"] = "document-processing-workflow"

from utils.perf_logger import install_performance_hooks

install_performance_hooks()

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import mistralai.workflows as workflows

from config import settings
from db.database import init_db, init_claim_tables
from workflow import DocumentProcessingWorkflow
from claim_workflow import ClaimProcessingWorkflow

from platform_core.config import load_config
from platform_core.registry import ProviderRegistry
from platform_core.resilience.health import HealthMonitor
from platform_core.adapters.resilient_mistral import breaker_status

from api.routers.v1 import build_root_router, build_v1_router

try:
    from logging_config import setup_logging

    setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
except Exception:  # pragma: no cover — fall back to stdlib logging
    logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)

logger = logging.getLogger(__name__)

worker_task = None
health_monitor: HealthMonitor | None = None
platform_config: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Initializing database...")
    await init_db()
    await init_claim_tables()

    logger.info("Ensuring storage directory exists...")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    # Platform core: config → provider registry → health monitor.
    # Failures here are non-fatal: the Mistral workflows below are the live
    # processing path and must still start even if a provider is misconfigured.
    global platform_config, health_monitor
    try:
        logger.info("[Startup] Loading platform config...")
        platform_config = load_config()

        logger.info("[Startup] Initializing Provider Registry...")
        registry = ProviderRegistry.from_config(platform_config)
        app.state.registry = registry
        logger.info(f"[Startup] Providers registered: {registry.summary()}")

        resilience_cfg = platform_config.get("resilience", {}).get("health_check", {})
        health_monitor = HealthMonitor(
            registry,
            interval_seconds=resilience_cfg.get("interval_seconds", 30),
            timeout_seconds=resilience_cfg.get("timeout_seconds", 15),
        )
        await health_monitor.start()
        logger.info("[Startup] Health monitor started.")
    except Exception as e:
        logger.warning(f"[Startup] platform_core initialization skipped: {e}")
        app.state.registry = None

    # Preload DINOv2 model at startup for fast signature verification
    logger.info("Preloading DINOv2 model for signature verification...")
    try:
        from utils.signature_verifier import DinoVerifier
        # Run in a background thread to prevent blocking server startup while downloading weights
        asyncio.create_task(asyncio.to_thread(DinoVerifier.preload))
    except Exception as e:
        logger.warning(f"Failed to initiate DINOv2 preload: {e}")

    logger.info("Starting Mistral Workflow worker...")
    global worker_task
    worker_task = asyncio.create_task(
        workflows.run_worker([DocumentProcessingWorkflow, ClaimProcessingWorkflow])
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    if health_monitor:
        with contextlib.suppress(Exception):
            await health_monitor.stop()

    logger.info("Shutting down Mistral Workflow worker...")
    if worker_task:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(worker_task, timeout=2.0)
    os._exit(0)


app = FastAPI(title="Mistral Document Processing POC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root mount — the paths the shipped frontend calls (nginx strips /api).
app.include_router(build_root_router())

# Versioned mount — same handlers under /api/v1.
app.include_router(build_v1_router())


@app.get("/health", tags=["Platform"])
async def health():
    """
    Liveness plus provider/circuit-breaker diagnostics.

    Always reports the app as up; provider detail is best-effort so a
    degraded provider never fails the liveness probe.
    """
    providers = {}
    registry = getattr(app.state, "registry", None)
    if registry is not None:
        with contextlib.suppress(Exception):
            providers = registry.summary()

    return {
        "status": "ok",
        "providers": providers,
        "circuit_breakers": breaker_status(),
    }

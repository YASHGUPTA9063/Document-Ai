"""
Document AI Platform — Main Application Entrypoint
=================================================
Initializes the platform core, database, and mounts API versioned routers.
Replaces the legacy monolithic main.py.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.database import init_db, init_claim_tables
from platform_core.config import load_config
from platform_core.registry import ProviderRegistry
from platform_core.resilience.health import HealthMonitor

# Import the v1 API router
from api.routers.v1 import api_v1_router
from api.queue import get_redis_pool

from logging_config import setup_logging

# Configure structured JSON logging
setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
logger = logging.getLogger(__name__)

# Global instances
health_monitor: HealthMonitor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    
    # 1. Initialize Database
    logger.info("[Startup] Initializing database...")
    await init_db()
    await init_claim_tables()
    
    # 2. Ensure storage directory exists (legacy fallback)
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    
    # 3. Initialize Platform Core
    logger.info("[Startup] Loading platform config...")
    platform_config = load_config()
    
    logger.info("[Startup] Initializing Provider Registry...")
    registry = ProviderRegistry.from_config(platform_config)
    
    # 4. Start Health Monitor
    logger.info("[Startup] Starting Health Monitor...")
    global health_monitor
    interval = platform_config.get("resilience", {}).get("health_check", {}).get("interval_seconds", 30)
    timeout = platform_config.get("resilience", {}).get("health_check", {}).get("timeout_seconds", 15)
    health_monitor = HealthMonitor(registry, interval_seconds=interval, timeout_seconds=timeout)
    await health_monitor.start()
    
    # (Optional) Preload DINOv2 model if defined in config
    dinov2_config = platform_config.get("providers", {}).get("embedding", {}).get("dinov2")
    if dinov2_config:
        logger.info("[Startup] Triggering DINOv2 model preload...")
        try:
            # Getting the provider will initialize the model in its __init__
            registry.get_embedding("dinov2")
        except Exception as e:
            logger.warning(f"[Startup] Failed to preload DINOv2: {e}")

    # 5. Initialize Redis Pool
    try:
        app.state.redis_pool = await get_redis_pool()
        logger.info("[Startup] Redis pool initialized.")
    except Exception as e:
        logger.warning(f"[Startup] Failed to connect to Redis: {e}")
        app.state.redis_pool = None

    logger.info("[Startup] Application is ready to receive requests.")
    yield
    
    # Shutdown
    logger.info("[Shutdown] Stopping Health Monitor...")
    if health_monitor:
        await health_monitor.stop()
        
    if hasattr(app.state, "redis_pool") and app.state.redis_pool:
        await app.state.redis_pool.close()

    logger.info("[Shutdown] Application shut down gracefully.")


app = FastAPI(title="Document AI Platform API", version="2.0.0", lifespan=lifespan, docs_url=None)

from fastapi.openapi.docs import get_swagger_ui_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css",
    )

# Setup Observability (Metrics & Tracing)
from observability import setup_observability
setup_observability(app)

# Setup CORS based on platform config (falling back to open for now)
platform_cfg = load_config()
cors_origins = platform_cfg.get("cors", {}).get("allowed_origins", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(api_v1_router)


@app.get("/health")
async def health_check():
    """System health check endpoint."""
    registry = ProviderRegistry.get()
    
    # Return registry summary and last known health status
    return {
        "status": "healthy",
        "providers": registry.summary(),
        "last_health_check": health_monitor.last_results if health_monitor else None
    }


if __name__ == "__main__":
    import uvicorn
    # Use config for host/port if available, fallback to 8000
    host = platform_cfg.get("app", {}).get("host", "0.0.0.0")
    port = platform_cfg.get("app", {}).get("port", 8000)
    uvicorn.run("main:app", host=host, port=port, reload=True)

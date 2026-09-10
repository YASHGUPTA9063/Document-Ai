"""
Shared process bootstrap
========================
Everything a process needs before it can do useful work: platform config, the
provider registry, the health monitor, and the DINOv2 weights.

This exists because the API and the Mistral workflow worker are now separate
processes, and both need the same initialisation. When the worker lived inside
the API process it inherited `main.py`'s lifespan setup for free; split apart,
anything the worker forgets to initialise fails *silently* rather than loudly:

  * `activities/extractor.py` resolves the vLLM fallback through
    `ProviderRegistry.get()`. That call returns an **empty** registry rather
    than raising when nothing populated it, and the vLLM call site swallows
    every exception — so an unbootstrapped worker just quietly stops doing
    second-pass extraction, with nothing in any log to say so.
  * `activities/auto_verifier.py` reaches DINOv2 through
    `utils/signature_verifier.py`. Without a preload the first KYC document to
    arrive pays a multi-minute model download inside an activity timeout.

So: one bootstrap, imported by `main.py` and `workflow_worker.py` alike.
"""

import asyncio
import logging

from config import settings, REQUIRED_AGENT_IDS, agent_binding_report

logger = logging.getLogger(__name__)

# Process-wide state, populated by init_platform().
platform_config: dict = {}
health_monitor = None
_dinov2_task: "asyncio.Task | None" = None


class MisconfiguredDeployment(RuntimeError):
    """Raised when the process cannot serve its role as configured."""


def assert_agent_bindings() -> None:
    """
    Refuse to start when a required Mistral Studio agent is unbound.

    Every *_AGENT_ID defaults to "" and every call site degrades quietly when
    one is missing, which in a container reads as a healthy deployment doing
    less work. In DEBUG this warns; outside it, it stops the process.
    """
    report = agent_binding_report()
    missing = report["required_missing"]

    if report["degraded_capabilities"]:
        logger.warning(
            "[Bootstrap] %d optional agent binding(s) unset — these capabilities are OFF: %s",
            len(report["degraded_capabilities"]),
            ", ".join(sorted(report["degraded_capabilities"].values())),
        )

    if not missing:
        return

    message = (
        f"Required Mistral Studio agent IDs are unset: {', '.join(missing)}. "
        f"Run create_or_update_agents.py and copy the IDs into .env."
    )
    if settings.DEBUG:
        logger.warning("[Bootstrap] %s (allowed because DEBUG=true)", message)
    else:
        raise MisconfiguredDeployment(message)


def assert_workflow_binding() -> None:
    """
    The dispatcher cannot start a run without a workflow ID. Checked separately
    from the agents because only dispatching processes need it — the workflow
    worker is addressed by DEPLOYMENT_NAME, not by workflow ID.
    """
    if settings.MISTRAL_WORKFLOW_ID:
        return
    message = (
        "MISTRAL_WORKFLOW_ID is unset — no document or claim run can be started. "
        "Copy the workflow ID from Mistral Studio into .env."
    )
    if settings.DEBUG:
        logger.warning("[Bootstrap] %s (allowed because DEBUG=true)", message)
    else:
        raise MisconfiguredDeployment(message)


async def init_platform(role: str, *, start_health_monitor: bool = True,
                        preload_dinov2: bool = True) -> dict:
    """
    Bring up the shared platform services for this process.

    Args:
        role: "api" | "workflow-worker" | "dispatcher" — used in logs so a
              container's output identifies which process it is.
        start_health_monitor: background provider polling. Off for short-lived
              processes that would never read the results.
        preload_dinov2: load signature/face embedding weights up front.

    Returns the loaded platform config.
    """
    global platform_config, health_monitor, _dinov2_task

    logger.info("[Bootstrap] Initialising platform for role=%s", role)

    from platform_core.config import load_config
    from platform_core.registry import ProviderRegistry
    from platform_core.resilience.health import HealthMonitor

    platform_config = load_config()

    # from_config() assigns the singleton that ProviderRegistry.get() returns.
    # This line is what keeps the vLLM fallback alive in the worker process.
    registry = ProviderRegistry.from_config(platform_config)
    logger.info("[Bootstrap] Providers registered: %s", registry.summary())

    if "vllm_fallback" not in registry.summary().get("llm", []):
        # Not fatal — the fallback is opt-in — but it must never be silent.
        logger.warning(
            "[Bootstrap] LLM provider 'vllm_fallback' is not registered. "
            "Second-pass extraction will not run even when "
            "pipelines.document_processing.enable_vllm_fallback is true."
        )

    if start_health_monitor:
        hc = platform_config.get("resilience", {}).get("health_check", {})
        health_monitor = HealthMonitor(
            registry,
            interval_seconds=hc.get("interval_seconds", 30),
            timeout_seconds=hc.get("timeout_seconds", 15),
        )
        await health_monitor.start()
        logger.info("[Bootstrap] Health monitor started")

    if preload_dinov2:
        # Downloading weights can take minutes on a cold image, so it runs in a
        # thread and the process comes up while it warms. Callers that need the
        # model block on it themselves via DinoVerifier's own lazy init.
        async def _preload():
            try:
                from utils.signature_verifier import DinoVerifier
                await asyncio.to_thread(DinoVerifier.preload)
                logger.info("[Bootstrap] DINOv2 preloaded")
            except Exception as e:
                logger.warning("[Bootstrap] DINOv2 preload failed: %s", e)

        _dinov2_task = asyncio.create_task(_preload())

    return platform_config


async def shutdown_platform() -> None:
    """Stop background services started by init_platform()."""
    global health_monitor, _dinov2_task

    if _dinov2_task and not _dinov2_task.done():
        _dinov2_task.cancel()
        try:
            await _dinov2_task
        except (asyncio.CancelledError, Exception):
            pass
        _dinov2_task = None

    if health_monitor is not None:
        try:
            await health_monitor.stop()
            logger.info("[Bootstrap] Health monitor stopped")
        except Exception as e:
            logger.warning("[Bootstrap] Health monitor shutdown failed: %s", e)
        health_monitor = None


def platform_state() -> dict:
    """Diagnostics for /health and /ready."""
    from platform_core.adapters.resilient_mistral import breaker_status
    from platform_core.registry import ProviderRegistry

    providers: dict = {}
    try:
        providers = ProviderRegistry.get().summary()
    except Exception:
        pass

    return {
        "execution_mode": settings.EXECUTION_MODE,
        "deployment_name": settings.DEPLOYMENT_NAME,
        "providers": providers,
        "provider_health": health_monitor.last_results if health_monitor else {},
        "circuit_breakers": breaker_status(),
        "agents": agent_binding_report(),
    }

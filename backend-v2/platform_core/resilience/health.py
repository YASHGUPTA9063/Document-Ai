"""
Health Monitor
==============
Periodically checks provider health and updates circuit breaker states.
Runs as a background task during server lifetime.
"""

import asyncio
import logging
from platform_core.providers.interfaces import ProviderStatus

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Background health checker for all registered providers.

    Usage:
        monitor = HealthMonitor(registry, interval_seconds=30)
        await monitor.start()   # Call in lifespan startup
        await monitor.stop()    # Call in lifespan shutdown
    """

    def __init__(self, registry, interval_seconds: int = 30, timeout_seconds: int = 5):
        self._registry = registry
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_results: dict[str, str] = {}

    async def start(self):
        """Start the background health check loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"[HealthMonitor] Started — checking every {self._interval}s"
        )

    async def stop(self):
        """Stop the background health check loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[HealthMonitor] Stopped")

    async def _loop(self):
        """Main health check loop."""
        while self._running:
            try:
                await self._check_all()
            except Exception as e:
                logger.error(f"[HealthMonitor] Check loop error: {e}")
            await asyncio.sleep(self._interval)

    async def _check_all(self):
        """Run health checks on all providers with a timeout."""
        try:
            results = await asyncio.wait_for(
                self._registry.health_check_all(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[HealthMonitor] Health check timed out after {self._timeout}s"
            )
            return

        self._last_results = results

        for provider_name, status in results.items():
            if status == ProviderStatus.DOWN.value or status == "down":
                logger.warning(
                    f"[HealthMonitor] Provider '{provider_name}' is DOWN"
                )
            elif status == ProviderStatus.DEGRADED.value or status == "degraded":
                logger.warning(
                    f"[HealthMonitor] Provider '{provider_name}' is DEGRADED"
                )

    @property
    def last_results(self) -> dict[str, str]:
        """Get the most recent health check results."""
        return self._last_results

    @property
    def is_running(self) -> bool:
        return self._running

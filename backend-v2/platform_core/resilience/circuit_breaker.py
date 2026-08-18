"""
Circuit Breaker
===============
Prevents cascade failures by short-circuiting calls to unhealthy providers.

States:
  CLOSED    → Normal operation, calls pass through
  OPEN      → Provider is down, calls immediately skipped (fallback to next)
  HALF_OPEN → Testing if provider recovered (allows 1 probe call)

Transitions:
  CLOSED → OPEN:      After `failure_threshold` consecutive failures
  OPEN → HALF_OPEN:   After `recovery_timeout` seconds
  HALF_OPEN → CLOSED: If probe call succeeds
  HALF_OPEN → OPEN:   If probe call fails
"""

import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Tracks failure/success for a single provider and trips open
    after too many consecutive failures.
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.success_count = 0

    @property
    def is_open(self) -> bool:
        """Check if the circuit is currently open (blocking calls)."""
        if self.state == CircuitState.OPEN:
            # Check if enough time has passed to try again
            if (
                self.last_failure_time is not None
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                logger.info(
                    f"[CircuitBreaker:{self.provider_name}] "
                    f"Recovery timeout elapsed, transitioning to HALF_OPEN"
                )
                self.state = CircuitState.HALF_OPEN
                return False  # Allow one probe call
            return True
        return False

    def record_success(self):
        """Record a successful call — resets the breaker to CLOSED."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(
                f"[CircuitBreaker:{self.provider_name}] "
                f"Probe call succeeded, transitioning to CLOSED"
            )
        self.failure_count = 0
        self.success_count += 1
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """Record a failed call — may trip the breaker to OPEN."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Probe failed — go back to OPEN
            self.state = CircuitState.OPEN
            logger.warning(
                f"[CircuitBreaker:{self.provider_name}] "
                f"Probe call failed, staying OPEN"
            )
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.critical(
                f"[CircuitBreaker:{self.provider_name}] "
                f"Circuit OPENED after {self.failure_count} consecutive failures"
            )

    def force_open(self):
        """Manually open the circuit (e.g., from health monitor)."""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        logger.warning(
            f"[CircuitBreaker:{self.provider_name}] Force-opened by health monitor"
        )

    def reset(self):
        """Reset the circuit breaker to its initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def status(self) -> dict:
        """Return current circuit breaker status for observability."""
        return {
            "provider": self.provider_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }

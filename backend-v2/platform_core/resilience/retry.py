"""
Retry Policy
=============
Configurable retry with exponential backoff + jitter for transient failures.
Used by the FallbackChain internally and available for standalone use.
"""

import asyncio
import random
import logging
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)


# Default set of transient errors that should trigger a retry
TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
    OSError,
)


class RetryPolicy:
    """
    Retries a function call with exponential backoff + jitter.

    Usage:
        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        result = await policy.execute(some_async_function, arg1, arg2)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        retryable_errors: tuple = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_errors = retryable_errors or TRANSIENT_ERRORS

    def _delay_for(self, attempt: int) -> float:
        """Exponential backoff with jitter: min(base * 2^attempt + jitter, max_delay)."""
        return min(
            self.base_delay * (2**attempt) + random.uniform(0, 1),
            self.max_delay,
        )

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute `func` with retry on transient errors.

        Uses exponential backoff: delay = min(base * 2^attempt + jitter, max_delay)
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_errors as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self._delay_for(attempt)
                    logger.warning(
                        f"[Retry] Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[Retry] All {self.max_retries} retries exhausted. Last error: {e}"
                    )
            except Exception:
                # Non-retryable error — raise immediately
                raise

        raise last_error

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Blocking counterpart of `execute`, for call sites that are synchronous.

        Several branch-vm3 tools (tools/extractor.py, tools/vllm_fallback.py,
        utils/ocr.py, utils/signature_extractor.py) call the Mistral SDK
        synchronously from inside worker threads. Converting them to async
        would change their threading behaviour, so they get a sync retry path
        with identical backoff semantics instead.
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.retryable_errors as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self._delay_for(attempt)
                    logger.warning(
                        f"[Retry] Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[Retry] All {self.max_retries} retries exhausted. Last error: {e}"
                    )
            except Exception:
                # Non-retryable error — raise immediately
                raise

        raise last_error

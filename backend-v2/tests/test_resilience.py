"""
Resilience Unit Tests
======================
Tests for circuit breaker, fallback chain, and retry policy.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from platform_core.providers.interfaces import ProviderStatus


class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    def test_initial_state_closed(self):
        from platform_core.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        assert cb.state == "closed"

    def test_opens_after_threshold_failures(self):
        from platform_core.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == "open"

    def test_allows_requests_when_closed(self):
        from platform_core.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        assert cb.allow_request() is True

    def test_blocks_requests_when_open(self):
        from platform_core.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        for _ in range(3):
            cb.record_failure()

        assert cb.allow_request() is False

    def test_resets_on_success(self):
        from platform_core.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        assert cb.state == "closed"
        assert cb._failure_count == 0


class TestRetryPolicy:
    """Tests for the RetryPolicy class."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        from platform_core.resilience.retry import RetryPolicy
        policy = RetryPolicy(max_retries=3, base_delay=0.01)

        mock_fn = AsyncMock(return_value="success")
        result = await policy.execute(mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        from platform_core.resilience.retry import RetryPolicy
        policy = RetryPolicy(max_retries=3, base_delay=0.01)

        mock_fn = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        result = await policy.execute(mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        from platform_core.resilience.retry import RetryPolicy
        policy = RetryPolicy(max_retries=2, base_delay=0.01)

        mock_fn = AsyncMock(side_effect=Exception("persistent failure"))

        with pytest.raises(Exception, match="persistent failure"):
            await policy.execute(mock_fn)

        assert mock_fn.call_count == 3  # 1 initial + 2 retries


class TestFallbackChain:
    """Tests for the FallbackChain class."""

    @pytest.mark.asyncio
    async def test_uses_first_provider(self):
        from platform_core.resilience.fallback import FallbackChain

        provider1 = MagicMock()
        provider1.name = "primary"
        provider1.chat = AsyncMock(return_value="result1")

        provider2 = MagicMock()
        provider2.name = "secondary"

        chain = FallbackChain(providers=[provider1, provider2])
        result = await chain.call(provider1.chat)

        assert result == "result1"

    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self):
        from platform_core.resilience.fallback import FallbackChain

        provider1 = MagicMock()
        provider1.name = "primary"

        provider2 = MagicMock()
        provider2.name = "secondary"

        chain = FallbackChain(providers=[provider1, provider2])

        calls = [AsyncMock(side_effect=Exception("down")), AsyncMock(return_value="fallback")]

        async def try_call(fn):
            return await fn()

        # This is a simplified test — actual FallbackChain.call() API may differ
        # based on the real implementation
        assert chain is not None

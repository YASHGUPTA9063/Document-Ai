"""
Resilience unit tests
=====================
Circuit breaker, retry policy and fallback chain.

These were previously written against an imagined API — `cb.state == "closed"`
when state is an Enum, an `allow_request()` method that does not exist, a
`FallbackChain.call()` taking a callable when it takes a method *name*. They
could never have passed; nothing provided pytest, so nobody found out. They are
now written against the real contracts in platform_core/resilience/.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from platform_core.resilience.circuit_breaker import CircuitBreaker, CircuitState
from platform_core.resilience.fallback import FallbackChain, AllProvidersFailedError
from platform_core.resilience.retry import RetryPolicy


def _breaker(**kwargs) -> CircuitBreaker:
    kwargs.setdefault("provider_name", "test-provider")
    kwargs.setdefault("failure_threshold", 3)
    kwargs.setdefault("recovery_timeout", 10)
    return CircuitBreaker(**kwargs)


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = _breaker()
        assert cb.state is CircuitState.CLOSED
        assert cb.is_open is False

    def test_opens_after_threshold_failures(self):
        cb = _breaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state is CircuitState.OPEN
        assert cb.is_open is True

    def test_stays_closed_below_threshold(self):
        cb = _breaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.CLOSED
        assert cb.is_open is False

    def test_resets_on_success(self):
        cb = _breaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_opens_after_recovery_timeout(self):
        """
        An open breaker must let exactly one probe through once the recovery
        window elapses, otherwise a provider that comes back stays shut out.
        """
        cb = _breaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

        assert cb.is_open is False          # probe allowed
        assert cb.state is CircuitState.HALF_OPEN

        cb.record_failure()                  # probe failed
        assert cb.state is CircuitState.OPEN

    def test_status_is_serialisable(self):
        """/health surfaces this, so it has to be plain JSON-able values."""
        cb = _breaker()
        cb.record_failure()
        status = cb.status()
        assert status["provider"] == "test-provider"
        assert status["state"] == CircuitState.CLOSED.value
        assert status["failure_count"] == 1


class TestRetryPolicy:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        fn = AsyncMock(return_value="success")

        assert await policy.execute(fn) == "success"
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_transient_errors(self):
        """Only TRANSIENT_ERRORS are retried — ConnectionError is one."""
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        fn = AsyncMock(side_effect=[ConnectionError("down"), ConnectionError("down"), "success"])

        assert await policy.execute(fn) == "success"
        assert fn.call_count == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_non_transient_errors(self):
        """
        A bad request is not a blip. Retrying it burns quota and delays the
        error the caller needs to see.
        """
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        fn = AsyncMock(side_effect=ValueError("bad request"))

        with pytest.raises(ValueError, match="bad request"):
            await policy.execute(fn)
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        fn = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(asyncio.TimeoutError):
            await policy.execute(fn)
        assert fn.call_count == 3  # 1 initial + 2 retries


def _provider(name: str, **methods) -> MagicMock:
    """A provider stub. `name` must be a real str — FallbackChain keys on it."""
    p = MagicMock()
    p.name = name
    for method_name, impl in methods.items():
        setattr(p, method_name, impl)
    return p


class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_uses_first_provider(self):
        primary = _provider("primary", chat=AsyncMock(return_value="result1"))
        secondary = _provider("secondary", chat=AsyncMock(return_value="result2"))

        chain = FallbackChain(providers=[primary, secondary], purpose="llm.test")

        # call() takes the method NAME, not a bound callable.
        assert await chain.call("chat", prompt="hi") == "result1"
        secondary.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self):
        primary = _provider("primary", chat=AsyncMock(side_effect=ConnectionError("down")))
        secondary = _provider("secondary", chat=AsyncMock(return_value="fallback"))

        chain = FallbackChain(providers=[primary, secondary], purpose="llm.test")

        assert await chain.call("chat", prompt="hi") == "fallback"
        secondary.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_every_provider_fails(self):
        primary = _provider("primary", chat=AsyncMock(side_effect=ConnectionError("down")))
        secondary = _provider("secondary", chat=AsyncMock(side_effect=ConnectionError("also down")))

        chain = FallbackChain(providers=[primary, secondary], purpose="llm.test")

        with pytest.raises(AllProvidersFailedError):
            await chain.call("chat", prompt="hi")

    @pytest.mark.asyncio
    async def test_open_breaker_skips_a_provider(self):
        """
        A provider whose breaker has tripped must be skipped entirely rather
        than retried on every call — that is the whole point of the breaker.
        """
        primary = _provider("primary", chat=AsyncMock(side_effect=ConnectionError("down")))
        secondary = _provider("secondary", chat=AsyncMock(return_value="fallback"))

        chain = FallbackChain(
            providers=[primary, secondary],
            purpose="llm.test",
            circuit_breaker_threshold=1,
        )

        await chain.call("chat")            # trips primary's breaker
        primary.chat.reset_mock()

        assert await chain.call("chat") == "fallback"
        primary.chat.assert_not_called()

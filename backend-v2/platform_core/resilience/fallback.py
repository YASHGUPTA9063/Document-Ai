"""
Fallback Chain
==============
Wraps multiple providers of the same type and tries them in order.
If Provider A fails, automatically falls through to Provider B, then C, etc.
Each provider is protected by a CircuitBreaker to prevent cascade failures.
"""

import logging
from typing import TypeVar, Generic, Any
from platform_core.providers.interfaces import ProviderStatus
from platform_core.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AllProvidersFailedError(Exception):
    """Raised when every provider in the fallback chain has failed."""

    def __init__(self, message: str, errors: list[tuple[str, str]]):
        super().__init__(message)
        self.errors = errors


class FallbackChain(Generic[T]):
    """
    Wraps multiple providers of the same type.
    Tries them in order until one succeeds.

    Usage:
        chain = FallbackChain([mistral_llm, openai_llm, anthropic_llm], purpose="classifier")
        response = await chain.call(messages=..., system_prompt=..., tools=...)
    """

    def __init__(
        self,
        providers: list[T],
        purpose: str = "default",
        circuit_breaker_threshold: int = 5,
        circuit_breaker_recovery: int = 60,
    ):
        self._providers = providers
        self._purpose = purpose
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(
                provider_name=p.name,
                failure_threshold=circuit_breaker_threshold,
                recovery_timeout=circuit_breaker_recovery,
            )
            for p in providers
        }

    @property
    def purpose(self) -> str:
        return self._purpose

    @property
    def providers(self) -> list[T]:
        return self._providers

    async def call(self, method: str = "chat", **kwargs) -> Any:
        """
        Try each provider in the chain until one succeeds.
        Skip providers whose circuit breaker is open.

        Args:
            method: The method name to call on the provider (e.g., "chat", "extract", "analyze")
            **kwargs: Arguments forwarded to the provider method.
        """
        errors: list[tuple[str, str]] = []

        for provider in self._providers:
            cb = self._circuit_breakers[provider.name]

            if cb.is_open:
                logger.warning(
                    f"[FallbackChain:{self._purpose}] Skipping {provider.name} "
                    f"— circuit breaker OPEN"
                )
                errors.append((provider.name, "circuit_breaker_open"))
                continue

            try:
                # Get the method from the provider and call it
                provider_method = getattr(provider, method)
                result = await provider_method(**kwargs)

                # Record success
                cb.record_success()
                logger.info(
                    f"[FallbackChain:{self._purpose}] {provider.name} succeeded"
                )
                return result

            except Exception as e:
                cb.record_failure()
                errors.append((provider.name, str(e)))
                logger.error(
                    f"[FallbackChain:{self._purpose}] {provider.name} failed: {e}. "
                    f"Trying next provider..."
                )
                continue

        # ALL providers failed
        raise AllProvidersFailedError(
            f"All {len(self._providers)} providers failed for '{self._purpose}': "
            + ", ".join(f"{name}={err}" for name, err in errors),
            errors=errors,
        )

    async def health_check(self) -> dict[str, ProviderStatus]:
        """Check health of all providers in the chain."""
        results = {}
        for provider in self._providers:
            try:
                results[provider.name] = await provider.health_check()
            except Exception:
                results[provider.name] = ProviderStatus.DOWN
        return results

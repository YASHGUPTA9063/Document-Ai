"""
Step Sandbox
============
Provides isolation guarantees for each pipeline step execution:
    - Scoped configuration (step only sees what it needs)
    - Timeout boundary (cannot run forever)
    - Error boundary (crash in one step doesn't corrupt pipeline state)
    - Scoped provider access (step can only use declared providers)
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable

from platform_core.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class StepTimeoutError(Exception):
    """Raised when a step exceeds its timeout."""
    pass


class StepExecutionError(Exception):
    """Wraps any exception from a step with step-specific context."""

    def __init__(self, step_name: str, original: Exception):
        self.step_name = step_name
        self.original = original
        super().__init__(f"Step '{step_name}' failed: {original}")


class ScopedProviderRegistry:
    """
    A restricted view of the ProviderRegistry that only exposes
    the provider types declared for a specific step.

    Prevents a step from accessing providers it shouldn't use
    (e.g., the classifier step accessing the storage provider).
    """

    def __init__(self, step_name: str, allowed_types: list[str], registry: ProviderRegistry):
        self._step_name = step_name
        self._allowed_types = set(allowed_types)
        self._registry = registry

    def get_llm(self, name: str | None = None):
        self._check("llm")
        return self._registry.get_llm(name)

    def get_llm_chain(self, purpose: str = "default"):
        self._check("llm")
        return self._registry.get_llm_chain(purpose)

    def get_ocr(self, name: str | None = None):
        self._check("ocr")
        return self._registry.get_ocr(name)

    def get_ocr_chain(self, purpose: str = "default"):
        self._check("ocr")
        return self._registry.get_ocr_chain(purpose)

    def get_storage(self, name: str | None = None):
        self._check("storage")
        return self._registry.get_storage(name)

    def get_embedding(self, name: str):
        self._check("embedding")
        return self._registry.get_embedding(name)

    def get_vision(self, name: str | None = None):
        self._check("vision")
        return self._registry.get_vision(name)

    def get_vision_chain(self, purpose: str = "default"):
        self._check("vision")
        return self._registry.get_vision_chain(purpose)

    def _check(self, provider_type: str):
        if provider_type not in self._allowed_types:
            raise PermissionError(
                f"Step '{self._step_name}' is not allowed to access "
                f"'{provider_type}' providers. Allowed: {self._allowed_types}"
            )


class StepSandbox:
    """
    Provides isolation guarantees for a pipeline step.

    Usage:
        sandbox = StepSandbox("classify", config={"timeout_seconds": 120, "allowed_providers": ["llm", "ocr"]})
        result = await sandbox.execute(classify_handler, context)
    """

    # Default provider access for each step
    DEFAULT_PROVIDER_ACCESS = {
        "intake":         ["llm"],
        "pre_validate":   ["llm", "vision"],
        "preprocess":     ["llm"],
        "classify":       ["llm", "ocr"],
        "fraud_check":    ["llm", "ocr", "vision"],
        "extract":        ["llm", "ocr"],
        "validate":       ["llm"],
        "auto_verify":    ["llm", "embedding", "vision"],
        "review":         ["llm"],
        "output":         ["llm", "storage"],
    }

    def __init__(self, step_name: str, config: dict | None = None):
        config = config or {}
        self.step_name = step_name
        self.allowed_providers = config.get(
            "allowed_providers",
            self.DEFAULT_PROVIDER_ACCESS.get(step_name, ["llm"]),
        )
        self.timeout = config.get("timeout_seconds", 300)

    async def execute(
        self,
        handler: Callable[..., Awaitable[dict]],
        context: dict,
        registry: ProviderRegistry | None = None,
    ) -> dict:
        """
        Execute handler within isolation boundaries.

        Args:
            handler: The step function. Receives (context, scoped_registry).
            context: Pipeline context dict.
            registry: Full provider registry (will be scoped).

        Returns:
            Step result dict.
        """
        # 1. Scope the registry
        scoped_registry = None
        if registry:
            scoped_registry = ScopedProviderRegistry(
                self.step_name, self.allowed_providers, registry
            )

        # 2. Execute with timeout + error boundary
        try:
            async with asyncio.timeout(self.timeout):
                if scoped_registry:
                    result = await handler(context, scoped_registry)
                else:
                    result = await handler(context)
        except asyncio.TimeoutError:
            raise StepTimeoutError(
                f"Step '{self.step_name}' exceeded {self.timeout}s timeout"
            )
        except (StepTimeoutError, StepExecutionError):
            raise  # Don't double-wrap our own errors
        except Exception as e:
            raise StepExecutionError(self.step_name, original=e)

        # 3. Validate output (no leaking internal state)
        if result is not None and not isinstance(result, dict):
            raise StepExecutionError(
                self.step_name,
                original=TypeError(
                    f"Step must return dict or None, got {type(result).__name__}"
                ),
            )

        return result or {}

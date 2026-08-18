"""
Resilient Mistral Client
========================
A drop-in replacement for `mistralai.client.Mistral` that adds circuit
breaker + retry protection to every SDK call, without changing the call
signature of a single existing call site.

Motivation
----------
branch-vm3 calls the Mistral SDK from ~20 modules, in two different styles:

    client = Mistral(api_key=settings.MISTRAL_API_KEY)
    client.chat.complete(...)                  # sync, from worker threads
    await client.agents.complete_async(...)    # async, from activities
    client.ocr.process(...)                    # sync
    client.beta.agents.get(...)                # sync, nested namespace
    await client.workflows.executions.query_workflow_execution_async(...)

Rewriting those into `registry.get_llm().chat(...)` would mean rewriting the
prompt handling, tool-call parsing and threading model of every one of them —
exactly the business logic that must stay untouched. Instead, this client
proxies the real SDK and wraps only the *transport*:

    client = get_mistral_client()   # <- only line that changes
    client.chat.complete(...)       # unchanged, now retried + breaker-protected

Failure semantics
-----------------
Only transient transport errors (connection resets, timeouts, 429/5xx) are
retried and counted toward the circuit breaker. Application-level errors —
a bad request, a JSON parse failure downstream, a business rule violation —
propagate immediately and untouched, exactly as before. This keeps the
breaker from tripping on errors that a retry could never fix, and guarantees
no existing error-handling path changes meaning.

Breakers are keyed per API surface ("chat", "ocr", "agents", "workflows", …)
so a failing OCR endpoint cannot open the circuit for chat completions.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from typing import Any, Callable

from platform_core.resilience.circuit_breaker import CircuitBreaker
from platform_core.resilience.retry import RetryPolicy

logger = logging.getLogger(__name__)


# ─── Retryable transport errors ──────────────────────────────────────────────

def _build_retryable_errors() -> tuple[type[BaseException], ...]:
    """
    Assemble the set of exception types worth retrying.

    Built defensively: httpx and the Mistral SDK are optional at import time
    so this module stays importable in environments (tests, tooling) where
    they are absent.
    """
    errors: list[type[BaseException]] = [
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
    ]

    try:
        import httpx

        errors.extend(
            [
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
                httpx.PoolTimeout,
            ]
        )
    except Exception:  # pragma: no cover - httpx always present in practice
        pass

    return tuple(errors)


RETRYABLE_ERRORS = _build_retryable_errors()

# HTTP status codes that represent a transient server-side condition.
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def _status_code_of(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status code from an SDK exception."""
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def _is_transient(exc: BaseException) -> bool:
    """True when `exc` represents a transport hiccup that a retry could fix."""
    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    status = _status_code_of(exc)
    return status in RETRYABLE_STATUS_CODES if status is not None else False


class _TransientError(Exception):
    """
    Internal marker used to drive RetryPolicy.

    RetryPolicy selects what to retry by exception *type*, but transience here
    depends on an exception's status code as well. Candidate errors are
    re-raised wrapped in this type, then unwrapped before reaching the caller,
    so callers only ever see the original exception.
    """

    def __init__(self, original: BaseException):
        super().__init__(str(original))
        self.original = original


# ─── Breaker registry ────────────────────────────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def _get_breaker(surface: str, threshold: int, recovery: int) -> CircuitBreaker:
    """Fetch (or lazily create) the circuit breaker for one API surface."""
    with _breakers_lock:
        breaker = _breakers.get(surface)
        if breaker is None:
            breaker = CircuitBreaker(
                provider_name=f"mistral.{surface}",
                failure_threshold=threshold,
                recovery_timeout=recovery,
            )
            _breakers[surface] = breaker
        return breaker


def breaker_status() -> dict[str, dict]:
    """Snapshot of every Mistral circuit breaker, for /health and diagnostics."""
    with _breakers_lock:
        return {name: cb.status() for name, cb in _breakers.items()}


class CircuitOpenError(RuntimeError):
    """Raised when a call is short-circuited because the breaker is open."""


# ─── Proxy machinery ─────────────────────────────────────────────────────────

class _ResilientNamespace:
    """
    Recursive attribute proxy over one SDK namespace (``client.chat``,
    ``client.workflows.executions``, …).

    Attribute access returns either another namespace proxy (for objects) or a
    resilience-wrapped callable (for methods). Non-callable leaf values are
    passed straight through.
    """

    __slots__ = ("_target", "_surface", "_config")

    def __init__(self, target: Any, surface: str, config: "_ResilienceConfig"):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_surface", surface)
        object.__setattr__(self, "_config", config)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)

        if callable(attr) and not inspect.isclass(attr):
            return _wrap_callable(attr, self._surface, name, self._config)

        # Nested namespace (e.g. client.workflows.executions) — keep proxying.
        if hasattr(attr, "__dict__") or hasattr(attr, "__slots__"):
            if not isinstance(attr, (str, bytes, int, float, bool, list, dict, tuple, set)):
                return _ResilientNamespace(attr, self._surface, self._config)

        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._target, name, value)

    def __repr__(self) -> str:
        return f"<ResilientNamespace {self._surface} wrapping {self._target!r}>"


class _ResilienceConfig:
    """Retry/breaker tuning shared by every wrapped call on one client."""

    __slots__ = ("max_retries", "base_delay", "max_delay", "threshold", "recovery")

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        threshold: int = 5,
        recovery: int = 60,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.threshold = threshold
        self.recovery = recovery

    def policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            retryable_errors=(_TransientError,),
        )


def _wrap_callable(
    func: Callable,
    surface: str,
    method_name: str,
    config: _ResilienceConfig,
) -> Callable:
    """Wrap one SDK method with circuit breaker + retry, preserving sync/async."""
    label = f"{surface}.{method_name}"
    breaker = _get_breaker(surface, config.threshold, config.recovery)
    policy = config.policy()

    def _guard_open() -> None:
        if breaker.is_open:
            raise CircuitOpenError(
                f"[Mistral:{surface}] Circuit breaker is OPEN — skipping {label}. "
                f"Provider has failed {breaker.failure_count} consecutive times."
            )

    if inspect.iscoroutinefunction(func):

        async def async_wrapper(*args, **kwargs):
            _guard_open()

            async def _attempt():
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if _is_transient(exc):
                        raise _TransientError(exc) from exc
                    raise

            try:
                result = await policy.execute(_attempt)
            except _TransientError as wrapped:
                breaker.record_failure()
                raise wrapped.original from None
            except Exception:
                # Non-transient: surfaced unchanged, and not held against the
                # breaker — retrying would not have helped.
                raise
            breaker.record_success()
            return result

        async_wrapper.__name__ = getattr(func, "__name__", method_name)
        async_wrapper.__doc__ = func.__doc__
        return async_wrapper

    def sync_wrapper(*args, **kwargs):
        _guard_open()

        def _attempt():
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if _is_transient(exc):
                    raise _TransientError(exc) from exc
                raise

        try:
            result = policy.execute_sync(_attempt)
        except _TransientError as wrapped:
            breaker.record_failure()
            raise wrapped.original from None
        except Exception:
            raise
        breaker.record_success()
        return result

    sync_wrapper.__name__ = getattr(func, "__name__", method_name)
    sync_wrapper.__doc__ = func.__doc__
    return sync_wrapper


# ─── Public client ───────────────────────────────────────────────────────────

class ResilientMistralClient:
    """
    Duck-type-compatible stand-in for `mistralai.client.Mistral`.

    Every attribute of the underlying client is reachable with an identical
    signature; only transport resilience is added. Pass one of these anywhere
    a raw `Mistral` instance was used before.
    """

    def __init__(
        self,
        api_key: str,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        client: Any = None,
    ):
        from mistralai.client import Mistral

        self._client = client if client is not None else Mistral(api_key=api_key)
        self._config = _ResilienceConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            threshold=failure_threshold,
            recovery=recovery_timeout,
        )
        logger.info(
            "[ResilientMistral] Initialized (retries=%s, breaker_threshold=%s, "
            "recovery=%ss)",
            max_retries,
            failure_threshold,
            recovery_timeout,
        )

    @property
    def raw(self) -> Any:
        """Escape hatch: the unwrapped SDK client, with no resilience applied."""
        return self._client

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not found on self — i.e. SDK surfaces.
        attr = getattr(self._client, name)

        if callable(attr) and not inspect.isclass(attr):
            return _wrap_callable(attr, name, "__call__", self._config)

        if not isinstance(attr, (str, bytes, int, float, bool, list, dict, tuple, set)):
            return _ResilientNamespace(attr, name, self._config)

        return attr

    def __repr__(self) -> str:
        return f"<ResilientMistralClient wrapping {self._client!r}>"


# ─── Singleton accessor ──────────────────────────────────────────────────────

_client_singleton: ResilientMistralClient | None = None
_client_lock = threading.Lock()


def get_mistral_client(api_key: str | None = None) -> ResilientMistralClient:
    """
    Return the process-wide resilient Mistral client.

    Drop-in replacement for ``Mistral(api_key=settings.MISTRAL_API_KEY)``.
    The API key defaults to ``settings.MISTRAL_API_KEY``, matching what every
    existing call site already passed.
    """
    global _client_singleton

    # An explicit key always builds a fresh, uncached client; the no-arg call
    # (what every call site uses) shares the singleton.
    caller_supplied_key = api_key is not None

    if _client_singleton is not None and not caller_supplied_key:
        return _client_singleton

    with _client_lock:
        if _client_singleton is not None and not caller_supplied_key:
            return _client_singleton

        if api_key is None:
            from config import settings

            api_key = settings.MISTRAL_API_KEY

        resilience: dict[str, Any] = {}
        try:
            from platform_core.config import load_config

            cfg = load_config().get("resilience", {})
            retry_cfg = cfg.get("retry", {}) or {}
            breaker_cfg = cfg.get("circuit_breaker", {}) or {}
            resilience = {
                "max_retries": retry_cfg.get("max_retries", 3),
                "base_delay": retry_cfg.get("base_delay_seconds", 1.0),
                "max_delay": retry_cfg.get("max_delay_seconds", 30.0),
                "failure_threshold": breaker_cfg.get("failure_threshold", 5),
                "recovery_timeout": breaker_cfg.get("recovery_timeout_seconds", 60),
            }
        except Exception as e:
            # Config is advisory here — defaults keep the client usable even if
            # platform.yaml is missing (e.g. in unit tests).
            logger.debug(f"[ResilientMistral] Using default resilience settings: {e}")

        client = ResilientMistralClient(api_key=api_key, **resilience)

        if not caller_supplied_key:
            _client_singleton = client
        return client


def reset_mistral_client() -> None:
    """Drop the cached client and all breakers (used by tests)."""
    global _client_singleton
    with _client_lock:
        _client_singleton = None
    with _breakers_lock:
        _breakers.clear()

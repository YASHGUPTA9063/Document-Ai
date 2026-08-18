"""
Platform Adapters
=================
Thin wrappers that bring existing branch-vm3 code under the platform_core
abstractions *without* rewriting its business logic.

The rule for everything in this package: behaviour of the wrapped code stays
byte-for-byte identical on the happy path. Adapters only add cross-cutting
concerns — resilience, registry lookup, observability.
"""

from platform_core.adapters.resilient_mistral import (
    ResilientMistralClient,
    get_mistral_client,
    breaker_status,
)

__all__ = [
    "ResilientMistralClient",
    "get_mistral_client",
    "breaker_status",
]

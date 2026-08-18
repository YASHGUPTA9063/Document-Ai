"""
Shared API Dependencies
=======================
Objects and constants that more than one v1 router needs.

The Mistral client here is the resilient adapter (circuit breaker + retry),
not a raw SDK client — see platform_core/adapters/resilient_mistral.py. It is
call-signature-compatible with the `mistral_client` that branch-vm3's
monolithic main.py used, so router code moved out of main.py works unchanged.
"""

from platform_core.adapters.resilient_mistral import get_mistral_client

# Upload allow-list, moved verbatim from branch-vm3 main.py.
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def mistral_client():
    """Resilient Mistral client (singleton)."""
    return get_mistral_client()


__all__ = ["ALLOWED_TYPES", "mistral_client", "get_mistral_client"]

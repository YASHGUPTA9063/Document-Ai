"""
vLLM Fallback Extraction Provider
=================================
Wraps branch-vm3's `tools/vllm_fallback.py` as a registry-managed provider.

This is the second stage of extraction: after the primary two-step chat
extraction in `tools/extractor.py` runs, any *required* template field that
came back missing — or below the configured confidence threshold — is
re-extracted by sending the rasterised document pages to a vision-capable
Mistral model.

The extraction logic itself is NOT reimplemented here. This class is a thin
provider-shaped surface over `vllm_reextract_required_fields()`; the field
selection rules, prompt, JSON-repair and result annotation all remain in
`tools/vllm_fallback.py` exactly as branch-vm3 wrote them.

Usage:
    registry = ProviderRegistry.get()
    vllm = registry.get_llm("vllm_fallback")
    patches = await vllm.reextract_fields(
        file_path=..., doc_type=..., document_id=...,
        normalized_extracted=..., field_confidences=...,
    )
"""

import asyncio
import logging
from typing import Any

from platform_core.providers.interfaces import LLMProvider, LLMResponse, ProviderStatus

logger = logging.getLogger(__name__)


class VLLMFallbackProvider(LLMProvider):
    """
    Registry-managed wrapper around the vLLM fallback re-extraction pass.

    Registered under the LLM provider type (it is an LLM call under the hood)
    but its real entry point is `reextract_fields`, which carries the
    document-extraction contract the pipeline needs.
    """

    def __init__(
        self,
        model: str = "mistral-large-latest",
        enabled: bool | None = None,
        confidence_threshold: float | None = None,
    ):
        self._model = model
        # `None` means "defer to storage/vllm_settings.json at call time", which
        # keeps the Settings UI authoritative. Explicit values act as overrides.
        self._enabled_override = enabled
        self._threshold_override = confidence_threshold
        logger.info(f"[VLLMFallback] Initialized with model={model}")

    @property
    def name(self) -> str:
        return "vllm_fallback"

    # ─── Settings resolution ─────────────────────────────────────────────

    def _resolve_settings(self) -> dict:
        """
        Read live vLLM settings, applying any config-file overrides.

        Settings live in storage/vllm_settings.json and are edited through
        GET/PUT /settings/vllm, so they are read per call rather than cached.
        """
        from utils.vllm_settings import load_vllm_settings

        resolved = dict(load_vllm_settings())
        if self._enabled_override is not None:
            resolved["enabled"] = self._enabled_override
        if self._threshold_override is not None:
            resolved["confidence_threshold"] = self._threshold_override
        return resolved

    # ─── Primary entry point ─────────────────────────────────────────────

    async def reextract_fields(
        self,
        file_path: str,
        doc_type: str,
        document_id: str,
        normalized_extracted: dict,
        field_confidences: dict,
        threshold: float | None = None,
        trigger_on_missing: bool | None = None,
        trigger_on_low_confidence: bool | None = None,
    ) -> dict:
        """
        Re-extract required fields that are missing or low-confidence.

        Returns a dict of ``{field_key: {value, confidence, source, reason,
        original_value, original_confidence}}`` — the exact shape
        `tools/vllm_fallback.py` produces. Returns ``{}`` when the feature is
        disabled or nothing needs re-extraction.

        The underlying call is synchronous (it rasterises pages with PyMuPDF
        and calls the Mistral SDK); it is run in a worker thread so the event
        loop is never blocked.
        """
        settings_ = self._resolve_settings()

        if not settings_.get("enabled", True):
            logger.info(
                f"[Document {document_id}] vLLM fallback disabled in settings — skipping"
            )
            return {}

        effective_threshold = (
            threshold if threshold is not None
            else settings_.get("confidence_threshold", 75)
        )
        effective_on_missing = (
            trigger_on_missing if trigger_on_missing is not None
            else settings_.get("trigger_on_missing", True)
        )
        effective_on_low_conf = (
            trigger_on_low_confidence if trigger_on_low_confidence is not None
            else settings_.get("trigger_on_low_confidence", True)
        )

        # Imported lazily: tools.vllm_fallback pulls in tools.extractor, which
        # would otherwise create an import cycle during registry construction.
        from tools.vllm_fallback import vllm_reextract_required_fields

        return await asyncio.to_thread(
            vllm_reextract_required_fields,
            file_path=file_path,
            doc_type=doc_type,
            document_id=document_id,
            normalized_extracted=normalized_extracted,
            field_confidences=field_confidences,
            threshold=effective_threshold,
            trigger_on_missing=effective_on_missing,
            trigger_on_low_confidence=effective_on_low_conf,
        )

    # ─── LLMProvider contract ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        Generic chat, satisfying the LLMProvider interface.

        Delegates to the resilient Mistral client so this provider can also
        serve as a plain fallback link in an LLM FallbackChain.
        """
        from platform_core.adapters.resilient_mistral import get_mistral_client

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format

        client = get_mistral_client()
        resp = await asyncio.to_thread(lambda: client.chat.complete(**kwargs))
        choice = resp.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            finish_reason=choice.finish_reason or "stop",
            provider=self.name,
            raw_response=resp,
        )

    async def health_check(self) -> ProviderStatus:
        """
        Report health without spending a vision call.

        Disabled-by-settings is reported as DEGRADED rather than DOWN: the
        provider is reachable, the operator has simply turned the pass off.
        """
        try:
            if not self._resolve_settings().get("enabled", True):
                return ProviderStatus.DEGRADED
            return ProviderStatus.HEALTHY
        except Exception as e:
            logger.warning(f"[VLLMFallback] Health check failed: {e}")
            return ProviderStatus.DOWN

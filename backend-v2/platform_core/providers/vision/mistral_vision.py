"""
Mistral Vision Provider
=======================
Implements VisionProvider interface using Mistral's multimodal chat
(pixtral model) for image analysis tasks like signature and face comparison.

Derived from utils/signature_verifier.py which uses:
    client.beta.conversations.start_async(agent_id=..., inputs=[multimodal_content])

The new provider uses chat.complete_async with pixtral (vision model)
and a system prompt instead of a Mistral Agent ID.
"""

import time
import logging
import mimetypes
import base64
from mistralai.client import Mistral
from platform_core.providers.interfaces import VisionProvider, LLMResponse, ProviderStatus

logger = logging.getLogger(__name__)


class MistralVision(VisionProvider):
    """
    Mistral Vision provider for image analysis tasks.

    Source reference:
        - utils/signature_verifier.py:196-254 — run_mistral_vision()
        - utils/signature_verifier.py:261-302 — run_judge()

    Handles:
        - Signature comparison (two images → similarity verdict)
        - Face comparison (two images → match verdict)
        - General document image analysis
    """

    def __init__(self, api_key: str, model: str = "pixtral-large-latest"):
        self._client = Mistral(api_key=api_key)
        self._model = model
        logger.info(f"[MistralVision] Initialized with model={model}")

    @property
    def name(self) -> str:
        return "mistral_vision"

    async def analyze(
        self,
        images: list[str],
        prompt: str,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        Analyze one or more images with a text prompt.

        images: list of file paths, base64 strings, or data URLs.

        Maps the current multimodal input pattern from signature_verifier.py:
            content = [
                {"type": "text", "text": "Compare these two signatures:"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]
        """
        content_parts: list[dict] = [{"type": "text", "text": prompt}]

        for img in images:
            url = self._resolve_image_url(img)
            content_parts.append(
                {"type": "image_url", "image_url": {"url": url}}
            )

        messages = [{"role": "user", "content": content_parts}]

        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.0,
        }
        if response_format:
            kwargs["response_format"] = response_format

        start = time.monotonic()
        try:
            resp = await self._client.chat.complete_async(**kwargs)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(f"[MistralVision] Analyze failed after {elapsed:.0f}ms: {e}")
            raise
        elapsed = (time.monotonic() - start) * 1000

        choice = resp.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=None,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                "total_tokens": getattr(resp.usage, "total_tokens", 0),
            },
            provider="mistral_vision",
            latency_ms=elapsed,
            raw_response=resp,
        )

    async def health_check(self) -> ProviderStatus:
        """Verify Mistral Vision API is reachable."""
        try:
            await self._client.chat.complete_async(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return ProviderStatus.HEALTHY
        except Exception as e:
            logger.warning(f"[MistralVision] Health check failed: {e}")
            return ProviderStatus.DOWN

    @staticmethod
    def _resolve_image_url(img: str) -> str:
        """
        Convert a file path, raw base64, or data URL to a data URL.

        Matches the encoding pattern from signature_verifier.py:
            doc_b64, doc_mime = _encode_image_base64(doc_path)
            url = f"data:{doc_mime};base64,{doc_b64}"
        """
        # Already a data URL
        if img.startswith("data:"):
            return img

        # File path — encode from disk
        import os
        if os.path.exists(img):
            mime, _ = mimetypes.guess_type(img)
            if mime is None:
                mime = "image/png"
            with open(img, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode()
            return f"data:{mime};base64,{b64_data}"

        # Assume raw base64 string
        return f"data:image/png;base64,{img}"

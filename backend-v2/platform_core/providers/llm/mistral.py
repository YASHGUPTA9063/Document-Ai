"""
Mistral LLM Provider
====================
Implements LLMProvider interface using the Mistral AI SDK.

Replaces the current pattern in all 16 activity files where each does:
    from mistralai.client import Mistral
    client = Mistral(api_key=settings.MISTRAL_API_KEY)
    response = await client.agents.complete_async(agent_id=..., messages=..., tools=...)

With the new pattern:
    llm = registry.get_llm_chain("classifier")
    response = await llm.call(messages=..., system_prompt=..., tools=...)

Key change: Instead of Mistral Agent IDs (pre-configured on Mistral Studio),
we use local system prompts loaded from platform/prompts/*.md files.
"""

import time
import logging
from mistralai.client import Mistral
from platform_core.providers.interfaces import LLMProvider, LLMResponse, ProviderStatus

logger = logging.getLogger(__name__)


class MistralLLM(LLMProvider):
    """
    Mistral AI LLM provider.

    Source reference:
        - activities/classifier.py:53-57 — client.agents.complete_async()
        - activities/extractor.py:18 — client = Mistral(api_key=...)
        - activities/reviewer.py:10 — client = Mistral(api_key=...)
        - (14 more activity files follow the same pattern)
    """

    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        self._client = Mistral(api_key=api_key)
        self._model = model
        logger.info(f"[MistralLLM] Initialized with model={model}")

    @property
    def name(self) -> str:
        return "mistral"

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
        Send a chat completion request to Mistral.

        Replaces:
            response = await client.agents.complete_async(
                agent_id=settings.CLASSIFIER_AGENT_ID,
                messages=messages, tools=tools
            )

        With:
            response = await mistral_llm.chat(
                messages=messages,
                system_prompt=prompts.get("classifier"),
                tools=CLASSIFIER_TOOLS,
            )
        """
        # Prepend system prompt (replaces Mistral Agent's baked-in system prompt)
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format

        start = time.monotonic()
        try:
            resp = await self._client.chat.complete_async(**kwargs)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(f"[MistralLLM] Chat failed after {elapsed:.0f}ms: {e}")
            raise
        elapsed = (time.monotonic() - start) * 1000

        choice = resp.choices[0]

        # Normalize tool_calls to a provider-agnostic format.
        # Current code (activities/classifier.py lines 65-77) builds this inline;
        # we standardize it inside the provider so all consumers get the same shape.
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                "total_tokens": getattr(resp.usage, "total_tokens", 0),
            },
            provider="mistral",
            latency_ms=elapsed,
            raw_response=resp,
        )

    async def health_check(self) -> ProviderStatus:
        """Ping Mistral with a minimal request to verify connectivity."""
        try:
            await self._client.chat.complete_async(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return ProviderStatus.HEALTHY
        except Exception as e:
            logger.warning(f"[MistralLLM] Health check failed: {e}")
            return ProviderStatus.DOWN

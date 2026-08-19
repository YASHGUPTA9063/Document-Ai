"""
Provider Unit Tests
====================
Tests for the concrete provider implementations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from platform_core.providers.interfaces import LLMResponse, ProviderStatus


# ─── MistralLLM Tests ───────────────────────────────────────────────────────

class TestMistralLLM:
    """Tests for the MistralLLM provider."""

    @pytest.mark.asyncio
    async def test_chat_returns_llm_response(self):
        """Verify chat() returns a properly structured LLMResponse."""
        from platform_core.providers.llm.mistral import MistralLLM

        with patch("platform_core.providers.llm.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            MockMistral.return_value = mock_client

            # Mock the async response
            mock_choice = MagicMock()
            mock_choice.message.content = '{"result": "test"}'
            mock_choice.message.tool_calls = None
            mock_choice.finish_reason = "stop"

            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_resp.usage.prompt_tokens = 10
            mock_resp.usage.completion_tokens = 5
            mock_resp.usage.total_tokens = 15

            mock_client.chat.complete_async = AsyncMock(return_value=mock_resp)

            llm = MistralLLM(api_key="test-key", model="mistral-small-latest")
            result = await llm.chat(
                messages=[{"role": "user", "content": "test"}],
                system_prompt="You are a test agent.",
            )

            assert isinstance(result, LLMResponse)
            assert result.content == '{"result": "test"}'
            assert result.tool_calls is None
            assert result.provider == "mistral"
            assert result.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_chat_normalizes_tool_calls(self):
        """Verify tool_calls are normalized to provider-agnostic format."""
        from platform_core.providers.llm.mistral import MistralLLM

        with patch("platform_core.providers.llm.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            MockMistral.return_value = mock_client

            mock_tc = MagicMock()
            mock_tc.id = "call_123"
            mock_tc.function.name = "get_data"
            mock_tc.function.arguments = '{"key": "value"}'

            mock_choice = MagicMock()
            mock_choice.message.content = ""
            mock_choice.message.tool_calls = [mock_tc]
            mock_choice.finish_reason = "tool_calls"

            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_resp.usage.prompt_tokens = 10
            mock_resp.usage.completion_tokens = 5
            mock_resp.usage.total_tokens = 15

            mock_client.chat.complete_async = AsyncMock(return_value=mock_resp)

            llm = MistralLLM(api_key="test-key")
            result = await llm.chat(
                messages=[{"role": "user", "content": "test"}],
                tools=[{"type": "function", "function": {"name": "get_data"}}],
            )

            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0]["id"] == "call_123"
            assert result.tool_calls[0]["function"]["name"] == "get_data"
            assert result.tool_calls[0]["function"]["arguments"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Verify health_check returns HEALTHY when Mistral responds."""
        from platform_core.providers.llm.mistral import MistralLLM

        with patch("platform_core.providers.llm.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            MockMistral.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(return_value=MagicMock())

            llm = MistralLLM(api_key="test-key")
            status = await llm.health_check()
            assert status == ProviderStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_down(self):
        """Verify health_check returns DOWN when Mistral fails."""
        from platform_core.providers.llm.mistral import MistralLLM

        with patch("platform_core.providers.llm.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            MockMistral.return_value = mock_client
            mock_client.chat.complete_async = AsyncMock(side_effect=Exception("Connection refused"))

            llm = MistralLLM(api_key="test-key")
            status = await llm.health_check()
            assert status == ProviderStatus.DOWN

    def test_name_property(self):
        """Verify the provider name."""
        from platform_core.providers.llm.mistral import MistralLLM

        with patch("platform_core.providers.llm.mistral.Mistral"):
            llm = MistralLLM(api_key="test-key")
            assert llm.name == "mistral"

"""
Agent Loop Unit Tests
======================
Tests for the shared agent conversation loop utility.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from platform_core.agent_loop import (
    run_agent_loop,
    run_simple_completion,
    _parse_json_response,
    _extract_text,
    AgentLoopError,
)
from platform_core.providers.interfaces import LLMResponse


class TestExtractText:
    """Tests for the _extract_text helper."""

    def test_string_content(self):
        assert _extract_text("hello") == "hello"

    def test_list_of_strings(self):
        assert _extract_text(["hello", " world"]) == "hello world"

    def test_list_of_dicts_with_text(self):
        content = [{"text": "hello"}, {"text": " world"}]
        assert _extract_text(content) == "hello world"

    def test_none_returns_empty(self):
        assert _extract_text(None) == ""


class TestParseJsonResponse:
    """Tests for the _parse_json_response helper."""

    def test_clean_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"key": "value"} hope this helps!'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            _parse_json_response("this is not json at all")


class TestRunAgentLoop:
    """Tests for the run_agent_loop function."""

    @pytest.mark.asyncio
    async def test_no_tool_calls(self):
        """LLM responds immediately without tool calls."""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content='{"doc_type": "invoice", "confidence": 0.95}',
            tool_calls=None,
        ))

        result = await run_agent_loop(
            llm=mock_llm,
            system_prompt="You are a classifier.",
            user_message="Classify this document.",
            tools_schema=[],
            tool_executor=AsyncMock(),
        )

        assert result["doc_type"] == "invoice"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_with_tool_calls(self):
        """LLM calls a tool, gets result, then returns final JSON."""
        mock_llm = MagicMock()

        # First call: LLM requests a tool
        tool_response = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "get_data",
                    "arguments": '{"key": "test"}',
                },
            }],
        )

        # Second call: LLM returns final result
        final_response = LLMResponse(
            content='{"result": "success"}',
            tool_calls=None,
        )

        mock_llm.chat = AsyncMock(side_effect=[tool_response, final_response])

        # Tool executor
        async def mock_executor(name, args):
            assert name == "get_data"
            return {"data": "fetched"}

        result = await run_agent_loop(
            llm=mock_llm,
            system_prompt="Test prompt",
            user_message="Do something",
            tools_schema=[{"type": "function"}],
            tool_executor=mock_executor,
        )

        assert result["result"] == "success"
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_exceeded(self):
        """Raises AgentLoopError after exceeding max iterations."""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_1",
                "function": {"name": "loop_tool", "arguments": "{}"},
            }],
        ))

        with pytest.raises(AgentLoopError, match="exceeded"):
            await run_agent_loop(
                llm=mock_llm,
                system_prompt="Test",
                user_message="Test",
                tools_schema=[],
                tool_executor=AsyncMock(return_value={"data": "still going"}),
                max_iterations=2,
            )

    @pytest.mark.asyncio
    async def test_tool_executor_error_handled(self):
        """Tool executor errors are captured and sent back to LLM."""
        mock_llm = MagicMock()

        tool_response = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_1",
                "function": {"name": "bad_tool", "arguments": "{}"},
            }],
        )
        final_response = LLMResponse(
            content='{"status": "recovered"}',
            tool_calls=None,
        )

        mock_llm.chat = AsyncMock(side_effect=[tool_response, final_response])

        async def failing_executor(name, args):
            raise RuntimeError("Tool crashed!")

        result = await run_agent_loop(
            llm=mock_llm,
            system_prompt="Test",
            user_message="Test",
            tools_schema=[],
            tool_executor=failing_executor,
        )

        assert result["status"] == "recovered"


class TestRunSimpleCompletion:
    """Tests for the run_simple_completion function."""

    @pytest.mark.asyncio
    async def test_simple_completion(self):
        """Simple completion returns parsed JSON."""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content='{"overall_status": "APPROVE", "suggestion": "All checks passed."}',
            tool_calls=None,
        ))

        result = await run_simple_completion(
            llm=mock_llm,
            system_prompt="You are a report agent.",
            user_message="Generate the report.",
        )

        assert result["overall_status"] == "APPROVE"

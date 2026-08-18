"""
Agent Conversation Loop
========================
Shared utility that replaces the identical conversation loop pattern
found in all 16 activity files.

Every activity follows this same flow:
    1. Send user message + system_prompt + tools to LLM
    2. If LLM returns tool_calls, execute them locally
    3. Append tool results to conversation, call LLM again
    4. Repeat until LLM returns a final text response
    5. Parse the final JSON response

This module extracts that loop into a single reusable function.
Activities only need to provide:
    - The LLMProvider instance (from the registry)
    - The system prompt name (loaded via PromptManager)
    - The user message
    - The tools schema
    - A tool executor callback (maps tool name → result)

Usage:
    from platform_core.agent_loop import run_agent_loop
    from platform_core.registry import ProviderRegistry
    from platform_core.prompts.manager import PromptManager

    registry = ProviderRegistry.get()
    prompts = PromptManager()

    result = await run_agent_loop(
        llm=registry.get_llm(),
        system_prompt=prompts.get("classifier"),
        user_message="Classify the document at ...",
        tools_schema=CLASSIFIER_TOOLS,
        tool_executor=my_tool_executor,
    )
"""

import json
import re
import logging
from typing import Any, Callable, Awaitable

from platform_core.providers.interfaces import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AgentLoopError(Exception):
    """Raised when the agent loop fails after exhausting all iterations."""
    pass


def _extract_text(content) -> str:
    """Extract text from various LLM response content formats."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif hasattr(chunk, "text") and chunk.text:
                parts.append(chunk.text)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _parse_json_response(content: str) -> dict:
    """
    Parse a JSON response from the LLM, handling common issues like
    markdown code blocks wrapping the JSON and trailing text.
    """
    text = _extract_text(content).strip()

    # Try to parse the entire text first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from a markdown code block
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: extract substring from first { to last }
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Fallback for arrays
    start_idx = text.find('[')
    end_idx = text.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not parse JSON from LLM response. "
        f"Content (first 500 chars): {text[:500]}"
    )


async def run_agent_loop(
    llm: LLMProvider,
    system_prompt: str,
    user_message: str,
    tools_schema: list[dict],
    tool_executor: Callable[[str, dict], Awaitable[Any]],
    temperature: float = 0.2,
    max_tokens: int = 4096,
    max_iterations: int = 10,
    json_mode: bool = True,
    response_format: dict | None = None,
) -> dict:
    """
    Run a multi-turn agent conversation loop with tool calling.

    This replaces the boilerplate conversation loop found in every
    activity file. The flow:
        1. Send user_message to LLM with system_prompt and tools
        2. If LLM returns tool_calls → execute via tool_executor callback
        3. Append tool results to conversation → call LLM again
        4. Repeat until LLM returns a text-only response (no tool_calls)
        5. Parse and return the final JSON response

    Args:
        llm: The LLM provider (from ProviderRegistry).
        system_prompt: System prompt text (from PromptManager).
        user_message: The initial user message to send.
        tools_schema: OpenAI-compatible tool definitions list.
        tool_executor: Async callback: (tool_name, args_dict) -> result.
                       Result is JSON-serialized and sent back to the LLM.
        temperature: Sampling temperature.
        max_tokens: Max tokens for the LLM response.
        max_iterations: Max number of LLM round-trips (safety limit).
        json_mode: If True and the final response isn't JSON, sends a
                   follow-up request with response_format={"type":"json_object"}.
        response_format: Optional response format override.

    Returns:
        Parsed JSON dict from the LLM's final response.

    Raises:
        AgentLoopError: If max_iterations is exceeded.
        ValueError: If the final response cannot be parsed as JSON.
    """
    messages = [{"role": "user", "content": user_message}]

    for iteration in range(max_iterations):
        logger.debug(
            f"[AgentLoop] Iteration {iteration + 1}/{max_iterations}, "
            f"messages={len(messages)}"
        )

        response: LLMResponse = await llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools_schema,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        # If no tool calls, this is the final response
        if not response.tool_calls:
            content = _extract_text(response.content).strip()

            # Try parsing as JSON directly
            try:
                return _parse_json_response(content)
            except (ValueError, json.JSONDecodeError):
                if json_mode:
                    # Ask the LLM to reformat as JSON
                    logger.info(
                        "[AgentLoop] Final response not valid JSON, "
                        "requesting JSON reformatting"
                    )
                    messages.append({
                        "role": "assistant",
                        "content": content,
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "Please reformat your response as a valid JSON object. "
                            "Return ONLY the JSON, no markdown or extra text."
                        ),
                    })
                    retry_response = await llm.chat(
                        messages=messages,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format={"type": "json_object"},
                    )
                    return _parse_json_response(retry_response.content)
                else:
                    raise

        # LLM wants to call tools — build assistant message with tool_calls
        assistant_msg = {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in response.tool_calls
            ],
        }
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in response.tool_calls:
            tool_name = tc["function"]["name"]
            try:
                tool_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            logger.info(f"[AgentLoop] Executing tool: {tool_name}({tool_args})")

            try:
                tool_result = await tool_executor(tool_name, tool_args)
            except Exception as e:
                logger.error(f"[AgentLoop] Tool {tool_name} failed: {e}")
                tool_result = {"error": str(e)}

            # Append tool result to conversation
            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
                "tool_call_id": tc["id"],
            })

    raise AgentLoopError(
        f"Agent loop exceeded {max_iterations} iterations without "
        f"producing a final response."
    )


async def run_simple_completion(
    llm: LLMProvider,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    json_mode: bool = True,
) -> dict:
    """
    Simplified version for agents that don't use tools.
    Just sends a single message and parses the JSON response.

    Useful for: validator, claim_report, face_judge, signature_judge.
    """
    response = await llm.chat(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"} if json_mode else None,
    )

    return _parse_json_response(response.content)

"""
Claim Disability Activity
==========================
Validates disability documentation and diagnosis consistency.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
from tools.claim_tools import CLAIM_TOOLS, dispatch_claim_tool
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def claim_disability_activity(claim_id: str) -> dict:
    """Runs the Disability Agent."""
    try:
        logger.info(f"[Claim {claim_id}] Starting Disability Agent activity.")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("claim_disability")

        async def execute_tool(name: str, args: dict):
            logger.info(f"[Claim {claim_id}] Executing tool: {name}({args})")
            return await dispatch_claim_tool(name, args)

        user_message = (
            f"You are running disability checks on claim_id='{claim_id}'.\n"
            f"Use your tools to fetch the required data, then perform all checks as per your instructions.\n"
            f"Return ONLY the JSON result object."
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=CLAIM_TOOLS,
            tool_executor=execute_tool,
            temperature=0.2,
        )

        logger.info(f"[Claim {claim_id}] Disability result: status={result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"[Claim {claim_id}] Disability Agent failed: {str(e)}")
        raise

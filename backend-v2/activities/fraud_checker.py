"""
Fraud Checker Activity
=======================
Runs identity document proofing checks via the Fraud Examiner Agent.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.fraud_checker import FRAUD_CHECKER_TOOLS, run_identity_proofing
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def fraud_check_activity(document_id: str, file_path: str) -> dict:
    """
    Step 3.5 — Fraud Checker.
    Runs identity document proofing via Fraud Examiner Agent.
    """
    try:
        logger.info(f"[Document {document_id}] Starting fraud check activity for {file_path}")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("fraud_checker")

        async def execute_tool(name: str, args: dict):
            if name == "run_identity_proofing":
                t_file_path = args.get("file_path", file_path)
                logger.info(f"[Document {document_id}] Executing identity proofing for: {t_file_path}")
                return await run_identity_proofing(t_file_path)
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"Please analyze the identity document at path '{file_path}' for potential "
            f"security and verification indicators. "
            f"Call the `run_identity_proofing` tool with the file_path to run forensic checks."
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=FRAUD_CHECKER_TOOLS,
            tool_executor=execute_tool,
            temperature=0.7,
        )

        logger.info(f"[Document {document_id}] Fraud check result: passed={result.get('passed')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Fraud check failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "fraud_checker"})
        raise

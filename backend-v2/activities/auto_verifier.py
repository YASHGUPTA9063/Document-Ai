"""
Auto-Verifier Activity
=======================
Coordinates signature and face photo verification against reference records.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.auto_verifier import (
    AUTO_VERIFIER_TOOLS,
    find_customer_reference,
    verify_signature,
    verify_face,
)
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def auto_verifier_activity(document_id: str, customer_id: str) -> dict:
    """
    Step 7 — Auto Verification.
    Verifies signatures and face photos against reference records.
    """
    try:
        logger.info(f"[Document {document_id}] Starting auto-verifier activity for customer: {customer_id}")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("auto_verifier")

        async def execute_tool(name: str, args: dict):
            if name == "find_customer_reference":
                t_customer_id = args.get("customer_id", customer_id)
                logger.info(f"[Document {document_id}] Executing find_customer_reference for: {t_customer_id}")
                return await find_customer_reference(t_customer_id, document_id)

            elif name == "verify_signature":
                t_customer_id = args.get("customer_id", customer_id)
                logger.info(f"[Document {document_id}] Executing verify_signature for: {t_customer_id}")
                return await verify_signature(t_customer_id, document_id)

            elif name == "verify_face":
                t_customer_id = args.get("customer_id", customer_id)
                logger.info(f"[Document {document_id}] Executing verify_face for: {t_customer_id}")
                return await verify_face(t_customer_id, document_id)

            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"Please coordinate the verification of signatures and face photos for "
            f"document '{document_id}' belonging to customer '{customer_id}'.\n"
            f"First, call the `find_customer_reference` tool to check if reference records exist.\n"
            f"Then, based on the tool response, call `verify_signature` and/or `verify_face` as needed."
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=AUTO_VERIFIER_TOOLS,
            tool_executor=execute_tool,
            temperature=0.7,
        )

        logger.info(f"[Document {document_id}] Auto-verification result: status={result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Auto-verifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "auto_verifier"})
        raise

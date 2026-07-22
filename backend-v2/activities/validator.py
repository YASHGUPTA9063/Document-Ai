"""
Validator Activity
===================
Validates extracted data against business rules and corrects OCR errors.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.validator import VALIDATOR_TOOLS, get_template_fields
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def validator_activity(document_id: str, extracted_data: dict, doc_type: str) -> dict:
    """
    Step 5 — Validator.
    Validates extracted data against business rules.
    """
    try:
        logger.info(f"[Document {document_id}] Starting validator activity for type: {doc_type}")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("validator")

        async def execute_tool(name: str, args: dict):
            if name == "get_template_fields":
                t_doc_type = args.get("doc_type", doc_type)
                logger.info(f"[Document {document_id}] Executing get_template_fields for: {t_doc_type}")
                return get_template_fields(t_doc_type)
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"Please validate the following extracted data for a '{doc_type}' document.\n\n"
            f"Extracted data:\n{json.dumps(extracted_data, indent=2)}\n\n"
            f"You can call the `get_template_fields` tool with doc_type='{doc_type}' to get "
            f"the expected field schema for this document type.\n\n"
            f"Validate the data against business rules, correct any obvious OCR errors, "
            f"and return the validation result as JSON."
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=VALIDATOR_TOOLS,
            tool_executor=execute_tool,
            temperature=0.2,
        )

        logger.info(f"[Document {document_id}] Validation result: is_valid={result.get('is_valid')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Validator failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "validator"})
        raise

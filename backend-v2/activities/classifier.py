"""
Classifier Activity
====================
Classifies a document into one of the supported document types.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
The system prompt is loaded from platform_core/prompts/classifier.md.
The conversation loop uses the shared run_agent_loop() helper.
"""

import logging
import json
import db.operations as db
from tools.classifier import CLASSIFIER_TOOLS, get_supported_doc_types, get_document_text
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def classifier_activity(document_id: str, file_path: str) -> dict:
    """
    Classify a document into a supported category.

    Uses the 'classifier' system prompt and calls get_supported_document_types
    and get_document_text tools via the generic agent loop.
    """
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("classifier")

        types_map = get_supported_doc_types()

        # Define the tool executor callback
        async def execute_tool(name: str, args: dict):
            if name == "get_supported_document_types":
                allowed_types = list(types_map.values()) + ["Others"]
                logger.info(f"[Document {document_id}] Executing get_supported_document_types: {allowed_types}")
                return {"supported_types": allowed_types}

            elif name == "get_document_text":
                t_file_path = args.get("file_path", file_path)
                logger.info(f"[Document {document_id}] Executing get_document_text for: {t_file_path}")
                raw_text = await get_document_text(t_file_path, document_id)
                return {"raw_text": raw_text}

            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"We need to classify the document at path '{file_path}' "
            f"into a supported category. "
            f"First, call the `get_supported_document_types` tool to see the allowed options. "
            f"Then, call the `get_document_text` tool with the file_path to extract the text. "
            f"Based on the text content, return a JSON classification verdict matching the schema."
        )

        parsed = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=CLASSIFIER_TOOLS,
            tool_executor=execute_tool,
            temperature=0.2,
        )

        doc_type_returned = parsed.get("doc_type", "Others").strip()

        # Match returned type back to the formal display name or default to Others
        matched_doc_type = "others"
        for key, display_name in types_map.items():
            if doc_type_returned.lower() in [key.lower(), display_name.lower(), key.replace("_", " ").lower()]:
                matched_doc_type = key  # store snake_case key
                break

        return {
            "doc_type": matched_doc_type,
            "confidence": parsed.get("confidence", 0.0),
            "reasoning": parsed.get("reasoning", "")
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Classifier failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "classifier"})
        raise

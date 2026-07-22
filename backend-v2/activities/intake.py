"""
Intake Activity
================
Checks if a newly uploaded document is a duplicate.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.intake import INTAKE_TOOLS, check_document_duplicates
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def intake_activity(document_id: str, filename: str) -> dict:
    """
    Check if a document is a duplicate by hash and filename.
    Falls back to direct DB check if the LLM doesn't call the tool.
    """
    try:
        logger.info(f"[Document {document_id}] Starting intake activity")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("intake")

        async def execute_tool(name: str, args: dict):
            if name == "check_document_duplicates":
                doc_id = args.get("document_id") or document_id
                fname = args.get("filename") or filename
                logger.info(f"[Document {document_id}] Executing duplicate check for document_id={doc_id}, filename={fname}")
                return await check_document_duplicates(doc_id, fname)
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"We have received a new document upload. "
            f"Please check if this document is a duplicate by calling the `check_document_duplicates` tool with:\n"
            f"- document_id: '{document_id}'\n"
            f"- filename: '{filename}'\n\n"
            f"Based on the tool output, return a JSON response matching exactly this schema:\n"
            f'{{\n  "is_duplicate": bool,\n  "existing_document_id": str or null\n}}'
        )

        try:
            result = await run_agent_loop(
                llm=llm,
                system_prompt=system_prompt,
                user_message=user_message,
                tools_schema=INTAKE_TOOLS,
                tool_executor=execute_tool,
                temperature=0.7,
            )
            logger.info(f"[Document {document_id}] Intake decision: {result}")
            return result

        except Exception as loop_err:
            # Fallback: direct DB duplicate check without LLM
            logger.warning(f"[Document {document_id}] Agent loop failed ({loop_err}), performing fallback duplicate check.")
            doc = await db.get_document(document_id)
            if not doc:
                raise ValueError(f"Document {document_id} not found in database")

            existing_id = None
            if doc.file_hash:
                existing_id = await db.check_duplicate_hash(doc.file_hash, exclude_id=document_id)
            if not existing_id:
                existing_id = await db.check_duplicate_filename(filename, exclude_id=document_id)

            return {
                "is_duplicate": bool(existing_id),
                "existing_document_id": existing_id
            }

    except Exception as e:
        logger.error(f"[Document {document_id}] Intake failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "intake"})
        raise

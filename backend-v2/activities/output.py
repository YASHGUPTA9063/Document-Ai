"""
Output Activity
================
Persists the final validated and verified document data to the database.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import json
import db.operations as db
from tools.output import OUTPUT_TOOLS, persist_final_extraction
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def output_activity(document_id: str, pipeline_context: dict) -> dict:
    """
    Step 8 — Output.
    Finalizes the document processing pipeline by persisting the results to the database.
    """
    try:
        logger.info(f"[Document {document_id}] Starting output activity")

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("output")

        async def execute_tool(name: str, args: dict):
            if name == "persist_final_extraction":
                logger.info(f"[Document {document_id}] Executing persist_final_extraction")
                return await persist_final_extraction(
                    document_id=document_id,
                    doc_type=pipeline_context.get("doc_type", args.get("doc_type", "unknown")),
                    raw_extracted=pipeline_context.get("raw_extracted", args.get("raw_extracted", {})),
                    validated_data=pipeline_context.get("validated_data", args.get("validated_data", {})),
                    confidence_score=pipeline_context.get("confidence_score", args.get("confidence_score", 0.0)),
                    field_confidences=pipeline_context.get("field_confidences", args.get("field_confidences", {})),
                    fraud_check=pipeline_context.get("fraud_check", args.get("fraud_check", {})),
                    signature_verification=pipeline_context.get("signature_verification", args.get("signature_verification", {})),
                    photo_verification=pipeline_context.get("photo_verification", args.get("photo_verification", {})),
                    corrections=pipeline_context.get("corrections", args.get("corrections", {}))
                )
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"Please finalize the document processing pipeline for document '{document_id}'.\n"
            f"Call the `persist_final_extraction` tool to write the final results to the database.\n\n"
            f"Pipeline context summary:\n{json.dumps({k: type(v).__name__ for k, v in pipeline_context.items()}, indent=2)}"
        )

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message=user_message,
            tools_schema=OUTPUT_TOOLS,
            tool_executor=execute_tool,
            temperature=0.7,
        )

        logger.info(f"[Document {document_id}] Output result: success={result.get('success')}")
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Output failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "output"})
        raise

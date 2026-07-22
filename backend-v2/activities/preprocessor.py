"""
Preprocessor Activity
======================
Enhances document image quality to optimize downstream OCR extraction.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.
"""

import logging
import os
import json
from pathlib import Path
import db.operations as db
from config import settings
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)
prompts = PromptManager()


async def preprocessor_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2.5 — Preprocessing.

    Applies image enhancement steps via Preprocessing Agent:
      1. Resolution Normalization — upscale low-res images
      2. Brightness / CLAHE — adaptive histogram equalization
      3. Noise Removal — light Gaussian blur
      4. Skew Correction — Hough line angle detection and rotation

    On any error, falls back to the original file so the pipeline is never blocked.
    """
    try:
        logger.info(f"[Document {document_id}] Starting preprocessing activity for: {file_path}")

        # Build output path
        path = Path(file_path)
        ext = path.suffix.lower()
        output_ext = ".pdf" if ext == ".pdf" else ".png"
        output_filename = f"{path.stem}_preprocessed{output_ext}"
        output_dir = os.path.join(settings.STORAGE_DIR, "preprocessed", document_id)
        output_path = os.path.join(output_dir, output_filename)

        from tools.preprocessor import PREPROCESSOR_TOOLS, enhance_document_image

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("preprocessor")

        async def execute_tool(name: str, args: dict):
            if name == "enhance_document_image":
                t_file_path = args.get("file_path", file_path)
                t_output_path = args.get("output_path", output_path)
                logger.info(f"[Document {document_id}] Executing image enhancement for: {t_file_path}")
                return enhance_document_image(file_path=t_file_path, output_path=t_output_path)
            else:
                return {"error": f"Unknown tool: {name}"}

        user_message = (
            f"We need to enhance the document image quality "
            f"located at '{file_path}' to prepare it for OCR.\n"
            f"Please call the `enhance_document_image` tool with:\n"
            f"- file_path: '{file_path}'\n"
            f"- output_path: '{output_path}'\n\n"
            f"Based on the tool output, return a JSON response matching exactly this schema:\n"
            f'{{\n  "preprocessed_path": str,\n  "original_path": str,\n  "applied_steps": list of strings,\n  "skipped": bool\n}}'
        )

        try:
            result = await run_agent_loop(
                llm=llm,
                system_prompt=system_prompt,
                user_message=user_message,
                tools_schema=PREPROCESSOR_TOOLS,
                tool_executor=execute_tool,
                temperature=0.7,
            )

            # Anti-hallucination check
            preprocessed_path = result.get("preprocessed_path")
            if preprocessed_path and not os.path.exists(preprocessed_path):
                logger.warning(f"[Document {document_id}] Agent hallucinated non-existent path: {preprocessed_path}. Falling back to original.")
                result["preprocessed_path"] = file_path

            logger.info(f"[Document {document_id}] Preprocessing result: {result}")
            return result

        except Exception as loop_err:
            # Fallback: run tool directly without LLM
            logger.warning(f"[Document {document_id}] Agent loop failed ({loop_err}), performing fallback preprocessing.")
            result = enhance_document_image(file_path=file_path, output_path=output_path)
            return result

    except Exception as e:
        logger.error(
            f"[Document {document_id}] Preprocessing failed: {str(e)}. "
            f"Falling back to original file to avoid blocking the pipeline."
        )
        await db.update_error(document_id, {"error": str(e), "stage": "preprocessor"})
        return {
            "preprocessed_path": file_path,
            "original_path": file_path,
            "applied_steps": [],
            "skipped": True,
        }

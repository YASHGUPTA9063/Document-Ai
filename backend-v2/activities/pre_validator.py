"""
Pre-Validation Activity
========================
Checks document quality (blur, brightness, skew, readability, etc.).

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry + PromptManager.

Note: This activity has a special multi-turn flow — after calling get_file_metadata,
if the file is visual, it sends the base64 image to the LLM for visual quality checks.
This requires a custom loop instead of the generic run_agent_loop().
"""

import os
import json
import logging
import db.operations as db
from utils.file_handler import get_file_as_base64
from tools.pre_validator import PRE_VALIDATOR_TOOLS, get_file_metadata
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import _extract_text, _parse_json_response

logger = logging.getLogger(__name__)
prompts = PromptManager()

# DOCX files have no visual representation — auto-pass with a note
DOCX_AUTO_PASS = {
    "passed": True,
    "rejection_reason": None,
    "warnings": ["DOCX file — visual quality checks skipped (not applicable to text documents)"],
    "checks": {},
}


def _is_password_protected(file_path: str) -> bool:
    """Checks if a PDF file is password protected using pypdf."""
    ext = os.path.splitext(file_path.lower())[1]
    if ext != ".pdf":
        return False
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        if reader.is_encrypted:
            try:
                res = reader.decrypt("")
                if res == 0 or str(res) == "PasswordType.NOT_DECRYPTED":
                    return True
            except Exception:
                return True
        return False
    except (pypdf.errors.FileNotDecryptedError, pypdf.errors.WrongPasswordError):
        return True
    except pypdf.errors.PdfReadError as e:
        if "encrypted" in str(e).lower() or "password" in str(e).lower():
            return True
        return False
    except Exception:
        return False


async def pre_validator_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2 — Pre-Validation.

    Sends file check instructions to the Pre-Validation Agent.
    If the file is visual, sends base64 vision blocks for quality checks.

    Returns:
        {
            "passed": bool,
            "rejection_reason": str | None,
            "warnings": [str],
            "checks": { ... }
        }
    """
    try:
        logger.info(f"[Document {document_id}] Starting pre-validation activity")

        # Password-protected documents are rejected up front — the LLM cannot
        # read them and pypdf answers this deterministically.
        if _is_password_protected(file_path):
            logger.warning(f"[Document {document_id}] Pre-validation failed: Document is password protected.")
            return {
                "passed": False,
                "rejection_reason": "Document is password protected.",
                "warnings": [],
                "checks": {
                    "password_protection": {
                        "passed": False,
                        "severity": "high",
                        "message": "Document is password protected."
                    }
                }
            }

        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("pre_validator")

        tools = PRE_VALIDATOR_TOOLS

        user_prompt = (
            f"Please run the document quality checks for the file at path '{file_path}'. "
            f"You MUST call the `get_file_metadata` tool first to check the file details. "
            f"If the file is visual, a base64 version will be analyzed."
        )

        messages = [{"role": "user", "content": user_prompt}]

        logger.info(f"[Document {document_id}] Calling Pre-Validator Agent via registry LLM")
        response = await llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
            temperature=0.7,
        )

        if response.tool_calls:
            logger.info(f"[Document {document_id}] Pre-Validator requested tool calls")

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

            is_visual = False
            mime_type = None

            for tc in response.tool_calls:
                if tc["function"]["name"] == "get_file_metadata":
                    args = json.loads(tc["function"]["arguments"])
                    target_file_path = args.get("file_path", file_path)

                    tool_output = get_file_metadata(target_file_path)
                    mime_type = tool_output["mime_type"]
                    is_visual = tool_output["is_visual"]

                    messages.append({
                        "role": "tool",
                        "name": "get_file_metadata",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tc["id"],
                    })

            # If file is visual, send base64 image for visual analysis
            if is_visual and mime_type:
                logger.info(f"[Document {document_id}] Encoding file as base64 (mime: {mime_type})")
                b64 = get_file_as_base64(file_path)
                data_url = f"data:{mime_type};base64,{b64}"

                if mime_type == "application/pdf":
                    file_content_block = {
                        "type": "document_url",
                        "document_url": data_url,
                    }
                else:
                    file_content_block = {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    }

                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Here is the visual representation of the document. Please run the quality checks on it now.",
                        },
                        file_content_block,
                    ],
                })
            else:
                messages.append({
                    "role": "user",
                    "content": "The document has been identified as non-visual (e.g. DOCX) or unsupported. Please complete the validation accordingly.",
                })

            logger.info(f"[Document {document_id}] Resuming Pre-Validator with tool result")
            response = await llm.chat(
                messages=messages,
                system_prompt=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
            )

        # Parse final response
        raw_text = _extract_text(response.content).strip()
        if not raw_text:
            raise ValueError("Pre-Validator Agent returned an empty response")

        result = _parse_json_response(raw_text)
        logger.info(
            f"[Document {document_id}] Pre-validation result: "
            f"passed={result.get('passed')}, warnings={result.get('warnings', [])}"
        )
        return result

    except Exception as e:
        logger.error(f"[Document {document_id}] Pre-validation failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "pre_validator"})
        raise

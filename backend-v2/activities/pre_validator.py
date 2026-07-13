import os
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.file_handler import get_file_as_base64
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

def _extract_text(content) -> str:
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

from tools.pre_validator import PRE_VALIDATOR_TOOLS, get_file_metadata


# DOCX files have no visual representation — auto-pass with a note
DOCX_AUTO_PASS = {
    "passed": True,
    "rejection_reason": None,
    "warnings": ["DOCX file — visual quality checks skipped (not applicable to text documents)"],
    "checks": {},
}


def _parse_json_response(raw_text: str) -> dict:
    """Parse JSON from agent response, stripping markdown fences if present."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove opening fence (e.g. ```json or ```)
        cleaned = "\n".join(lines[1:])
    if cleaned.endswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[:-1])
    return json.loads(cleaned.strip())


@workflows.activity()
async def pre_validator_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2 — Pre-Validation.

    Sends the file check instructions to the Pre-Validation Agent.
    The agent calls the `get_file_metadata` tool. If the file is visual,
    the tool execution block reads the image/pdf and appends the base64 vision blocks
    to the conversation, allowing the Pre-Validation Vision Agent to perform quality checks.

    Returns:
        {
            "passed": bool,
            "rejection_reason": str | None,
            "warnings": [str],
            "checks": {
                "blur":        {"passed": bool, "severity": str, "message": str},
                "brightness":  {"passed": bool, "severity": str, "message": str},
                "skew":        {"passed": bool, "severity": str, "message": str},
                "readability": {"passed": bool, "severity": str, "message": str},
                "watermark":   {"passed": bool, "severity": str, "message": str},
                "orientation": {"passed": bool, "severity": str, "message": str},
            }
        }
    """
    try:
        logger.info(f"[Document {document_id}] Starting pre-validation activity")

        if not settings.PRE_VALIDATOR_AGENT_ID:
            raise ValueError("PRE_VALIDATOR_AGENT_ID is not configured in settings/environment.")

        # Use imported tools schema
        tools = PRE_VALIDATOR_TOOLS

        user_prompt = (
            f"Please run the document quality checks for the file at path '{file_path}'. "
            f"You MUST call the `get_file_metadata` tool first to check the file details. "
            f"If the file is visual, a base64 version will be analyzed."
        )

        messages = [
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        logger.info(f"[Document {document_id}] Calling Pre-Validator Agent ({settings.PRE_VALIDATOR_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.PRE_VALIDATOR_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        if message.tool_calls:
            logger.info(f"[Document {document_id}] Pre-Validator Agent requested tool calls: {message.tool_calls}")

            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            }
            messages.append(assistant_msg)

            is_visual = False
            mime_type = None

            for tool_call in message.tool_calls:
                if tool_call.function.name == "get_file_metadata":
                    args = json.loads(tool_call.function.arguments)
                    target_file_path = args.get("file_path", file_path)

                    tool_output = get_file_metadata(target_file_path)
                    mime_type = tool_output["mime_type"]
                    is_visual = tool_output["is_visual"]

                    messages.append({
                        "role": "tool",
                        "name": "get_file_metadata",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tool_call.id
                    })

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
                            "text": "Here is the visual representation of the document. Please run the quality checks on it now."
                        },
                        file_content_block
                    ]
                })
            else:
                messages.append({
                    "role": "user",
                    "content": "The document has been identified as non-visual (e.g. DOCX) or unsupported. Please complete the validation accordingly."
                })

            logger.info(f"[Document {document_id}] Resuming Pre-Validator Agent with tool result")
            response = client.agents.complete(
                agent_id=settings.PRE_VALIDATOR_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message

        # Parse final response
        raw_text = _extract_text(message.content).strip()
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

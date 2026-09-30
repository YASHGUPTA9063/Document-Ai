import os
import json
import logging
import mimetypes
import mistralai.workflows as workflows
from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings

logger = logging.getLogger(__name__)
client = get_mistral_client()

from tools.fraud_checker import FRAUD_CHECKER_TOOLS, run_identity_proofing

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




@workflows.activity()
async def fraud_check_activity(document_id: str, file_path: str) -> dict:
    """
    Step 3.5 — Fraud Checker.
    Runs Google Document AI 'Identity Document Proofing' processor via Fraud Examiner Agent.
    """
    try:
        logger.info(f"[Document {document_id}] Starting fraud check activity for {file_path}")

        if not settings.FRAUD_AGENT_ID:
            raise ValueError("FRAUD_AGENT_ID is not configured in settings/environment.")

        # Use imported tools schema
        tools = FRAUD_CHECKER_TOOLS

        prompt = (
            f"You are the Fraud Examiner Agent. We need to perform identity document proofing "
            f"on the file located at '{file_path}'.\n"
            f"Please call the `run_identity_proofing` tool with:\n"
            f"- file_path: '{file_path}'\n\n"
            f"Based on the tool output, return a JSON response matching exactly this schema:\n"
            f"{{\n"
            f"  \"passed\": bool,\n"
            f"  \"rejection_reason\": str or null,\n"
            f"  \"checks\": dict of check names to statuses,\n"
            f"  \"mocked\": bool\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Fraud Examiner Agent ({settings.FRAUD_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.FRAUD_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Fraud Examiner Agent requested tool calls: {message.tool_calls}")

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

            for tool_call in message.tool_calls:
                if tool_call.function.name == "run_identity_proofing":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)

                    logger.info(f"[Document {document_id}] Executing run_identity_proofing tool for file: {t_file_path}")

                    result = await run_identity_proofing(t_file_path, document_id)

                    messages.append({
                        "role": "tool",
                        "name": "run_identity_proofing",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Fraud Examiner Agent with tool result")
            response = await client.agents.complete_async(
                agent_id=settings.FRAUD_AGENT_ID,
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message

        # Parse final response
        content = _extract_text(message.content).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            logger.info(f"[Document {document_id}] Final message not JSON. Requesting JSON formatting.")
            messages.append({
                "role": "user",
                "content": (
                    "Based on the tool output, please output the final fraud check results "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"passed\": bool,\n"
                    "  \"rejection_reason\": str or null,\n"
                    "  \"checks\": {},\n"
                    "  \"mocked\": bool\n"
                    "}"
                )
            })
            response = await client.agents.complete_async(
                agent_id=settings.FRAUD_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        return parsed

    except Exception as e:
        logger.warning(
            f"[Document {document_id}] Fraud check agent call failed with error: {str(e)}. "
            f"Falling back to local execution to avoid blocking the pipeline."
        )
        # No db.update_error(): the run continues on the direct path, so the
        # document is not failed.
        return await run_identity_proofing(file_path, document_id)

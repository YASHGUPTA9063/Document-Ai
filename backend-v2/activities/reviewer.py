import json
import logging
import mistralai.workflows as workflows
from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
import db.operations as db
from tools.reviewer import REVIEWER_TOOLS, get_review_context

logger = logging.getLogger(__name__)
client = get_mistral_client()


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
async def reviewer_activity(document_id: str, validated_data: dict, confidence_score: float, validation_errors: list = None) -> dict:
    """
    Step 6 — Reviewer.
    Determines if human review is needed, generating a summary via the Reviewer Agent.
    """
    try:
        logger.info(f"[Document {document_id}] Starting reviewer activity. Confidence: {confidence_score}")

        if validation_errors:
            logger.info(f"[Document {document_id}] Forcing human review due to validation errors: {validation_errors}")
            unique_errs = []
            for err in validation_errors:
                if err and err not in unique_errs:
                    unique_errs.append(err)
            formatted_summary = "\n".join(f"• {err}" for err in unique_errs)
            return {
                "approved": None,
                "auto_approved": False,
                "needs_review": True,
                "summary": formatted_summary
            }

        # Remove massive base64 images from the validated data to avoid overwhelming the LLM
        prompt_data = validated_data.copy()
        prompt_data.pop("signature_image", None)
        prompt_data.pop("photo_image", None)

        # Use imported tools schema
        tools = REVIEWER_TOOLS

        prompt = (
            f"You are the Reviewer Agent. We need to evaluate document '{document_id}' to see if it requires human review.\n"
            f"First, call the `get_review_context` tool to retrieve the document confidence score and validated data.\n\n"
            f"Evaluation Rules:\n"
            f"- If the confidence_score is greater than or equal to 0.80, the document is auto-approved. Return approved=True and auto_approved=True.\n"
            f"- If the confidence_score is below 0.80, the document needs manual review. Generate a summary of the data and return needs_review=True.\n\n"
            f"Output a JSON object matching exactly this schema:\n"
            f"{{\n"
            f"  \"approved\": bool (or null if needs_review is true),\n"
            f"  \"auto_approved\": bool (or null if needs_review is true),\n"
            f"  \"needs_review\": bool (or null if approved is true),\n"
            f"  \"summary\": str or null\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Reviewer Agent ({settings.REVIEWER_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.REVIEWER_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Reviewer Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "get_review_context":
                    logger.info(f"[Document {document_id}] Executing get_review_context tool")
                    
                    tool_output = get_review_context(confidence_score, prompt_data)

                    messages.append({
                        "role": "tool",
                        "name": "get_review_context",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Reviewer Agent with tool result")
            response = await client.agents.complete_async(
                agent_id=settings.REVIEWER_AGENT_ID,
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
                    "Based on your evaluation, please output the final review decision "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"approved\": bool,\n"
                    "  \"auto_approved\": bool,\n"
                    "  \"needs_review\": bool,\n"
                    "  \"summary\": \"...\" or null\n"
                    "}"
                )
            })
            response = await client.agents.complete_async(
                agent_id=settings.REVIEWER_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        return parsed

    except Exception as e:
        logger.error(f"[Document {document_id}] Reviewer failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "reviewer"})
        raise

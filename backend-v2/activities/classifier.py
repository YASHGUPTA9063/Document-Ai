import os
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from tools.classifier import CLASSIFIER_TOOLS, get_supported_doc_types, get_document_text
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




@workflows.activity()
async def classifier_activity(document_id: str, file_path: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting classifier activity")

        if not settings.CLASSIFIER_AGENT_ID:
            raise ValueError("CLASSIFIER_AGENT_ID is not configured in settings/environment.")

        # Use imported tools schema
        tools = CLASSIFIER_TOOLS

        prompt = (
            f"You are the Classifier Agent. We need to classify the document at path '{file_path}' "
            f"into a supported category. "
            f"First, call the `get_supported_document_types` tool to see the allowed options. "
            f"Then, call the `get_document_text` tool with the file_path to extract the text. "
            f"Based on the text content, return a JSON classification verdict matching the schema."
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Classifier Agent ({settings.CLASSIFIER_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.CLASSIFIER_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message
        types_map = get_supported_doc_types()

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Classifier Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "get_supported_document_types":
                    allowed_types = list(types_map.values()) + ["Others"]
                    tool_output = {"supported_types": allowed_types}
                    logger.info(f"[Document {document_id}] Executing get_supported_document_types tool: {allowed_types}")

                    messages.append({
                        "role": "tool",
                        "name": "get_supported_document_types",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tool_call.id
                    })

                elif tool_call.function.name == "get_document_text":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)

                    logger.info(f"[Document {document_id}] Executing get_document_text tool for file: {t_file_path}")

                    raw_text = get_document_text(t_file_path, document_id)

                    messages.append({
                        "role": "tool",
                        "name": "get_document_text",
                        "content": json.dumps({"raw_text": raw_text}),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Classifier Agent with tool result")
            response = client.agents.complete(
                agent_id=settings.CLASSIFIER_AGENT_ID,
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
                    "Based on the tool output, please classify the document and output the final classification response "
                    "as a JSON object matching exactly this schema:\n"
                    "{\n"
                    "  \"doc_type\": \"...\",\n"
                    "  \"confidence\": 0.0,\n"
                    "  \"reasoning\": \"...\"\n"
                    "}"
                )
            })
            response = client.agents.complete(
                agent_id=settings.CLASSIFIER_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message
            content = _extract_text(message.content).strip()
            parsed = json.loads(content)

        doc_type_returned = parsed.get("doc_type", "Others").strip()

        # Match returned type back to the formal display name or default to Others
        matched_doc_type = "Others"
        for key, display_name in types_map.items():
            if doc_type_returned.lower() in [key.lower(), display_name.lower(), key.replace("_", " ").lower()]:
                matched_doc_type = display_name
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

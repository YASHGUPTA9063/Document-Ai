import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

# Maps classifier-emitted doc_type strings (lowercased) to their dedicated Mistral Agent ID.
DOC_TYPE_AGENT_MAP = {
    "invoice":        settings.INVOICE_EXTRACTOR_AGENT_ID,
    "contract":       settings.CONTRACT_EXTRACTOR_AGENT_ID,
    "kyc":            settings.KYC_EXTRACTOR_AGENT_ID,
    "medical record": settings.MEDICAL_EXTRACTOR_AGENT_ID,
    "bank record":    settings.BANK_EXTRACTOR_AGENT_ID,
    "others":         settings.OTHERS_EXTRACTOR_AGENT_ID,
}


async def _run_extraction_with_agent(
    agent_id: str,
    file_path: str,
    doc_type: str,
    document_id: str
) -> dict:
    """
    Shared OCR + function-calling extraction helper.

    1. Sends the agent a user message asking it to call `extract_text_from_document`.
    2. If the agent issues the tool call, runs OCR locally and returns the text as a tool result.
    3. Resumes the agent to get the final structured JSON extraction.
    4. Falls back to direct OCR if the agent skips the tool call.

    Returns: {"fields": dict, "raw_ocr": str, "confidence": float}
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_text_from_document",
                "description": (
                    "Extracts raw text and markdown from a document file path "
                    "using OCR or document parsing."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": (
                                "The absolute or relative file path of the document "
                                "(PDF, PNG, JPG, DOCX)."
                            )
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }
    ]

    messages = [
        {
            "role": "user",
            "content": (
                f"Please extract structured data from the document located at: '{file_path}'. "
                f"You MUST call the `extract_text_from_document` tool to get the document text first."
            )
        }
    ]

    logger.info(f"[Document {document_id}] Sending initial request to agent {agent_id} (type: {doc_type})")
    response = client.agents.complete(
        agent_id=agent_id,
        messages=messages,
        tools=tools
    )

    message = response.choices[0].message
    raw_text = ""
    ocr_confidence = 0.0

    if message.tool_calls:
        logger.info(f"[Document {document_id}] Agent requested tool calls: {message.tool_calls}")

        # Append the assistant turn (with tool_calls) back into the conversation
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

        # Execute each requested tool call
        for tool_call in message.tool_calls:
            if tool_call.function.name == "extract_text_from_document":
                args = json.loads(tool_call.function.arguments)
                target_file_path = args.get("file_path", file_path)
                # Strip surrounding quotes the agent sometimes wraps the path in
                target_file_path = target_file_path.strip("'\"").strip()

                logger.info(f"[Document {document_id}] Executing OCR tool for file: {target_file_path}")
                ocr_result = extract_with_ocr(target_file_path, doc_type)
                raw_text = ocr_result.get("raw_text", "")
                ocr_confidence = ocr_result.get("confidence", 0.0)

                messages.append({
                    "role": "tool",
                    "name": "extract_text_from_document",
                    "content": raw_text,
                    "tool_call_id": tool_call.id
                })

        logger.info(f"[Document {document_id}] Resuming agent with tool result")
        response = client.agents.complete(
            agent_id=agent_id,
            messages=messages,
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message
    else:
        # Fallback: agent skipped the tool — run OCR ourselves and send raw text
        logger.warning(
            f"[Document {document_id}] Agent did not request tool call. Performing fallback OCR."
        )
        ocr_result = extract_with_ocr(file_path, doc_type)
        raw_text = ocr_result.get("raw_text", "")
        ocr_confidence = ocr_result.get("confidence", 0.0)

        response = client.agents.complete(
            agent_id=agent_id,
            messages=[{"role": "user", "content": raw_text}],
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message

    content = message.content
    fields = json.loads(content)

    return {
        "fields": fields,
        "raw_ocr": raw_text,
        "confidence": ocr_confidence
    }


@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")

        agent_id = DOC_TYPE_AGENT_MAP.get(doc_type.lower())
        if agent_id:
            return await _run_extraction_with_agent(agent_id, file_path, doc_type, document_id)
        else:
            logger.warning(f"[Document {document_id}] Unknown doc type received: '{doc_type}'")
            return {
                "fields": {},
                "raw_ocr": "",
                "confidence": 0.0,
                "message": f"Unknown doc type: {doc_type}"
            }

    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

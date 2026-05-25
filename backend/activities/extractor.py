import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
import db.operations as db

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")
        
        if doc_type.lower() == "invoice":
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "extract_text_from_document",
                        "description": "Extracts raw text and markdown from a document file path using OCR or document parsing.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "The absolute or relative file path of the document (PDF, PNG, JPG, DOCX)."
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

            logger.info(f"[Document {document_id}] Sending initial request to agent with tool definition")
            response = client.agents.complete(
                agent_id=settings.EXTRACTOR_AGENT_ID,
                messages=messages,
                tools=tools
            )

            message = response.choices[0].message
            raw_text = ""
            ocr_confidence = 0.0

            if message.tool_calls:
                logger.info(f"[Document {document_id}] Agent requested tool calls: {message.tool_calls}")
                # Build the assistant's message dict to append to messages list
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
                    if tool_call.function.name == "extract_text_from_document":
                        args = json.loads(tool_call.function.arguments)
                        target_file_path = args.get("file_path", file_path)
                        
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
                    agent_id=settings.EXTRACTOR_AGENT_ID,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                message = response.choices[0].message
            else:
                logger.warning(f"[Document {document_id}] Agent did not request tool call. Performing fallback OCR.")
                ocr_result = extract_with_ocr(file_path, doc_type)
                raw_text = ocr_result.get("raw_text", "")
                ocr_confidence = ocr_result.get("confidence", 0.0)
                
                response = client.agents.complete(
                    agent_id=settings.EXTRACTOR_AGENT_ID,
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
        else:
            return {
                "message": "Extractor not yet implemented for this document type",
                "doc_type": doc_type,
                "fields": {},
                "confidence": 0.0,
                "raw_ocr": ""
            }
            
    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

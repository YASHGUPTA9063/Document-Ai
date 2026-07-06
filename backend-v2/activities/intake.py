import logging
import json
import mistralai.workflows as workflows
from mistralai.client import Mistral
import db.operations as db
from config import settings

from tools.intake import INTAKE_TOOLS, check_document_duplicates

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
async def intake_activity(document_id: str, filename: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting intake activity")

        if not settings.INTAKE_AGENT_ID:
            raise ValueError("INTAKE_AGENT_ID is not configured in settings/environment.")

        # Use imported tools schema
        tools = INTAKE_TOOLS

        prompt = (
            f"You are the Intake Agent. We have received a new document upload. "
            f"Please check if this document is a duplicate by calling the `check_document_duplicates` tool with:\n"
            f"- document_id: '{document_id}'\n"
            f"- filename: '{filename}'\n\n"
            f"Based on the tool output, return a JSON response matching exactly this schema:\n"
            f"{{\n"
            f"  \"is_duplicate\": bool,\n"
            f"  \"existing_document_id\": str or null\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]
        
        logger.info(f"[Document {document_id}] Calling Intake Agent ({settings.INTAKE_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.INTAKE_AGENT_ID,
            messages=messages,
            tools=tools
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            logger.info(f"[Document {document_id}] Intake Agent requested tool calls: {message.tool_calls}")
            
            # Add the assistant message (with tool calls) to messages
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
                if tool_call.function.name == "check_document_duplicates":
                    args = json.loads(tool_call.function.arguments)
                    doc_id = args.get("document_id") or document_id
                    fname = args.get("filename") or filename
                    
                    logger.info(f"[Document {document_id}] Executing duplicate check tool for document_id={doc_id}, filename={fname}")
                    
                    tool_result = await check_document_duplicates(doc_id, fname)
                    
                    messages.append({
                        "role": "tool",
                        "name": "check_document_duplicates",
                        "content": json.dumps(tool_result),
                        "tool_call_id": tool_call.id
                    })
            
            logger.info(f"[Document {document_id}] Resuming Intake Agent with tool result")
            
            messages.append({
                "role": "user",
                "content": "Based on the tool output above, output the final intake verdict in the requested JSON format."
            })
            
            response = client.agents.complete(
                agent_id=settings.INTAKE_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            message = response.choices[0].message

            content = _extract_text(message.content).strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:])
            if content.endswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[:-1])
                
            result = json.loads(content.strip())
            logger.info(f"[Document {document_id}] Intake Agent final decision: {result}")
            return result
        else:
            logger.warning(f"[Document {document_id}] Intake Agent did not request tool call. Performing fallback duplicate check.")
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

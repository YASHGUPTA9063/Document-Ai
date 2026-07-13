import logging
import os
import json
from pathlib import Path
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
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
async def preprocessor_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2.5 — Preprocessing.

    Applies the following image enhancement steps (in order) via Preprocessing Agent:
      1. Resolution Normalization — upscale low-res images (< 1000px short side)
      2. Brightness / CLAHE      — adaptive histogram equalization on L-channel
      3. Noise Removal           — light 3×3 Gaussian blur
      4. Skew Correction         — Hough line angle detection and rotation

    On any error, falls back to the original file so the pipeline is never blocked.
    """
    try:
        logger.info(f"[Document {document_id}] Starting preprocessing activity for: {file_path}")

        if not settings.PREPROCESSING_AGENT_ID:
            raise ValueError("PREPROCESSING_AGENT_ID is not configured in settings/environment.")

        # Build output path: {STORAGE_DIR}/preprocessed/{document_id}/{basename}_preprocessed.{ext}
        path = Path(file_path)
        ext = path.suffix.lower()

        # For images we always output PNG; for PDFs we keep PDF
        output_ext = ".pdf" if ext == ".pdf" else ".png"
        output_filename = f"{path.stem}_preprocessed{output_ext}"
        output_dir = os.path.join(settings.STORAGE_DIR, "preprocessed", document_id)
        output_path = os.path.join(output_dir, output_filename)

        from tools.preprocessor import PREPROCESSOR_TOOLS, enhance_document_image
        tools = PREPROCESSOR_TOOLS

        prompt = (
            f"You are the Preprocessing Agent. We need to enhance the document image quality "
            f"located at '{file_path}' to prepare it for OCR.\n"
            f"Please call the `enhance_document_image` tool with:\n"
            f"- file_path: '{file_path}'\n"
            f"- output_path: '{output_path}'\n\n"
            f"Based on the tool output, return a JSON response matching exactly this schema:\n"
            f"{{\n"
            f"  \"preprocessed_path\": str,\n"
            f"  \"original_path\": str,\n"
            f"  \"applied_steps\": list of strings,\n"
            f"  \"skipped\": bool\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Preprocessing Agent ({settings.PREPROCESSING_AGENT_ID})")
        response = client.agents.complete(
            agent_id=settings.PREPROCESSING_AGENT_ID,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        if message.tool_calls:
            logger.info(f"[Document {document_id}] Preprocessing Agent requested tool calls: {message.tool_calls}")

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
                if tool_call.function.name == "enhance_document_image":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)
                    t_output_path = args.get("output_path", output_path)

                    logger.info(f"[Document {document_id}] Executing image enhancement tool for file_path={t_file_path}")

                    result = enhance_document_image(
                        file_path=t_file_path,
                        output_path=t_output_path
                    )

                    messages.append({
                        "role": "tool",
                        "name": "enhance_document_image",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Preprocessing Agent with tool result")
            messages.append({
                "role": "user",
                "content": "Based on the tool output above, output the final preprocessing response in the requested JSON format."
            })

            response = client.agents.complete(
                agent_id=settings.PREPROCESSING_AGENT_ID,
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
            
            # Anti-hallucination check: if the agent hallucinates the output path when the tool skipped it
            preprocessed_path = result.get("preprocessed_path")
            if preprocessed_path and not os.path.exists(preprocessed_path):
                logger.warning(f"[Document {document_id}] Agent hallucinated non-existent path: {preprocessed_path}. Falling back to original.")
                result["preprocessed_path"] = file_path
                
            logger.info(f"[Document {document_id}] Preprocessing Agent final decision: {result}")
            return result
        else:
            logger.warning(f"[Document {document_id}] Preprocessing Agent did not request tool call. Performing fallback preprocessing.")
            result = enhance_document_image(
                file_path=file_path,
                output_path=output_path
            )
            return result

    except Exception as e:
        logger.error(
            f"[Document {document_id}] Preprocessing failed with error: {str(e)}. "
            f"Falling back to original file path to avoid blocking the pipeline."
        )
        # Record the error but do NOT re-raise — preprocessing failure must never kill the workflow
        await db.update_error(document_id, {"error": str(e), "stage": "preprocessor"})
        return {
            "preprocessed_path": file_path,
            "original_path": file_path,
            "applied_steps": [],
            "skipped": True,
        }

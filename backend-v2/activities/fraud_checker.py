import os
import json
import logging
import mimetypes
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)

# Core 4 check names expected from Identity Document Proofing processor
CORE_CHECKS = {
    "fraud_signals_is_identity_document",
    "fraud_signals_suspicious_words",
    "fraud_signals_image_manipulation",
    "fraud_signals_online_duplicate"
}


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


def _process_checks_dict(document_id: str, checks_results: dict, mocked: bool) -> dict:
    # Ensure all 4 core checks have a status, default to missing if not provided
    checks_final = {}
    failed_checks = []

    for check in CORE_CHECKS:
        status = checks_results.get(check, "MISSING")
        checks_final[check] = status
        if status != "PASS":
            failed_checks.append(f"{check}: {status}")

    passed = len(failed_checks) == 0
    rejection_reason = None
    if not passed:
        rejection_reason = f"Document failed fraud check verification: {', '.join(failed_checks)}"

    logger.info(
        f"[Document {document_id}] Fraud check completed (mocked={mocked}). "
        f"Passed: {passed}. Checks: {checks_final}"
    )

    return {
        "passed": passed,
        "checks": checks_final,
        "rejection_reason": rejection_reason,
        "mocked": mocked
    }


async def _run_identity_proofing_local(document_id: str, file_path: str) -> dict:
    """Original local code to run Google Document AI or fallback to output.json mock."""
    # Set GOOGLE_APPLICATION_CREDENTIALS if configured in settings
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai

        project_id = settings.DOCUMENTAI_PROJECT_ID
        location = settings.DOCUMENTAI_LOCATION
        processor_id = settings.DOCUMENTAI_PROCESSOR_ID

        if not project_id or not processor_id:
            raise ValueError("Google Document AI Project ID or Processor ID is not set.")

        logger.info(
            f"[Document {document_id}] Calling Document AI. "
            f"Project: {project_id}, Location: {location}, Processor: {processor_id}"
        )

        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        doc_client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = doc_client.processor_path(project_id, location, processor_id)

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            ext = os.path.splitext(file_path.lower())[1]
            if ext in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            elif ext == ".png":
                mime_type = "image/png"
            else:
                mime_type = "application/pdf"

        with open(file_path, "rb") as f:
            image_content = f.read()

        raw_document = documentai.RawDocument(content=image_content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        
        result = doc_client.process_document(request=request)
        document = result.document

        checks_results = {}
        for entity in getattr(document, "entities", []):
            ent_type = entity.type_
            if ent_type in CORE_CHECKS:
                value = entity.mention_text
                if entity.normalized_value and entity.normalized_value.text:
                    value = entity.normalized_value.text
                checks_results[ent_type] = value.strip().upper()

        return _process_checks_dict(document_id, checks_results, mocked=False)

    except Exception as e:
        logger.warning(
            f"[Document {document_id}] Google Document AI API execution failed: {str(e)}. "
            "Attempting fallback to local output.json mock file."
        )

        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_file_path = os.path.join(workspace_root, "output.json")

        if not os.path.exists(mock_file_path):
            logger.error(f"[Document {document_id}] Fallback mock file not found at {mock_file_path}")
            raise RuntimeError(
                f"Fraud check failed: Google credentials or processor not set up, "
                f"and mock file 'output.json' is missing at {mock_file_path}."
            ) from e

        logger.info(f"[Document {document_id}] Loading mock fraud check output from {mock_file_path}")
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            checks_results = {}
            for entity in data.get("entities", []):
                ent_type = entity.get("type")
                if ent_type in CORE_CHECKS:
                    value = entity.get("mentionText", "")
                    if entity.get("normalizedValue") and entity.get("normalizedValue").get("text"):
                        value = entity.get("normalizedValue").get("text")
                    checks_results[ent_type] = value.strip().upper()

            return _process_checks_dict(document_id, checks_results, mocked=True)
        except Exception as mock_err:
            logger.error(f"[Document {document_id}] Failed to parse mock output.json: {str(mock_err)}")
            raise RuntimeError(f"Fraud check failed to process fallback: {str(mock_err)}") from e


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

        # Define quality validation tool schema
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_identity_proofing",
                    "description": "Performs identity document proofing checks on the file. Runs Google Document AI processor or loads mock checks on failure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "The file path of the document to run proofing on."
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            }
        ]

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
        response = client.agents.complete(
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

                    result = await _run_identity_proofing_local(document_id, t_file_path)

                    messages.append({
                        "role": "tool",
                        "name": "run_identity_proofing",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Fraud Examiner Agent with tool result")
            response = client.agents.complete(
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
            response = client.agents.complete(
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
        # Record error and return direct execution
        import db.operations as db
        await db.update_error(document_id, {"error": str(e), "stage": "fraud_checker"})
        return await _run_identity_proofing_local(document_id, file_path)

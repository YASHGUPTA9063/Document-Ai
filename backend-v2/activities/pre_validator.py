import os
import json
import logging
import mistralai.workflows as workflows
from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
from utils.file_handler import get_file_as_base64

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

from tools.pre_validator import PRE_VALIDATOR_TOOLS, get_file_metadata


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


def _check_pdf_blank_and_protection(file_path: str) -> dict:
    """Checks password protection and blank status for PDF files using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF (fitz) not available, falling back to pypdf for protection check")
        if _is_password_protected(file_path):
            return {
                "passed": False,
                "rejection_reason": "Document is password protected.",
                "warnings": [],
                "checks": {
                    "password_protection": {"passed": False, "severity": "high", "message": "Document is password protected."}
                }
            }
        return {
            "passed": True,
            "rejection_reason": None,
            "warnings": [],
            "checks": {
                "password_protection": {"passed": True, "severity": "none", "message": "Document is not password protected."},
                "blank": {"passed": True, "severity": "none", "message": "Document contains content."}
            }
        }

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        if "encrypted" in str(e).lower() or "password" in str(e).lower():
            return {
                "passed": False,
                "rejection_reason": "Document is password protected.",
                "warnings": [],
                "checks": {
                    "password_protection": {"passed": False, "severity": "high", "message": "Document is password protected."}
                }
            }
        raise

    if doc.is_encrypted:
        if not doc.authenticate(""):
            doc.close()
            return {
                "passed": False,
                "rejection_reason": "Document is password protected.",
                "warnings": [],
                "checks": {
                    "password_protection": {"passed": False, "severity": "high", "message": "Document is password protected."}
                }
            }

    if len(doc) == 0:
        doc.close()
        return {
            "passed": False,
            "rejection_reason": "Document is blank or contains no content.",
            "warnings": [],
            "checks": {
                "password_protection": {"passed": True, "severity": "none", "message": "Document is not password protected."},
                "blank": {"passed": False, "severity": "high", "message": "Document has no pages."}
            }
        }

    has_content = False
    # ponytail: checks text, embedded images, and vector drawings on every page. Fast O(pages) scan.
    for page in doc:
        text = page.get_text().strip()
        images = page.get_images()
        drawings = page.get_drawings()
        if text or len(images) > 0 or len(drawings) > 0:
            has_content = True
            break

    doc.close()

    if not has_content:
        return {
            "passed": False,
            "rejection_reason": "Document is blank or contains no content.",
            "warnings": [],
            "checks": {
                "password_protection": {"passed": True, "severity": "none", "message": "Document is not password protected."},
                "blank": {"passed": False, "severity": "high", "message": "Document is blank or contains no text/images/drawings."}
            }
        }

    return {
        "passed": True,
        "rejection_reason": None,
        "warnings": [],
        "checks": {
            "password_protection": {"passed": True, "severity": "none", "message": "Document is not password protected."},
            "blank": {"passed": True, "severity": "none", "message": "Document contains readable content."}
        }
    }


def _check_docx_blank_and_protection(file_path: str) -> dict:
    """Checks blank status for DOC/DOCX files using python-docx if available."""
    try:
        import docx
        doc = docx.Document(file_path)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        if not full_text:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text += cell.text.strip()
        if not full_text.strip():
            return {
                "passed": False,
                "rejection_reason": "Document is blank or contains no content.",
                "warnings": ["DOCX file visual quality checks skipped"],
                "checks": {
                    "blank": {"passed": False, "severity": "high", "message": "DOCX document contains no text content."}
                }
            }
    except Exception as e:
        logger.warning(f"Error checking DOCX content with python-docx: {e}")

    return {
        "passed": True,
        "rejection_reason": None,
        "warnings": ["DOCX file — visual quality checks skipped (not applicable to text documents)"],
        "checks": {
            "blank": {"passed": True, "severity": "none", "message": "DOCX document contains text content."}
        }
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

    For PDFs and DOC/DOCX files, password protection and blank status are checked locally
    via PyMuPDF and python-docx without calling the Pre-Validation Agent.
    Only image files (JPEG, PNG, WEBP) are sent to the Pre-Validation Agent for quality checks.
    """
    try:
        logger.info(f"[Document {document_id}] Starting pre-validation activity for file: {file_path}")
        ext = os.path.splitext(file_path.lower())[1]

        # 1. PDF Documents: checked natively via PyMuPDF (protection + blank check)
        if ext == ".pdf":
            result = _check_pdf_blank_and_protection(file_path)
            logger.info(
                f"[Document {document_id}] PDF local pre-validation result: "
                f"passed={result.get('passed')}, reason={result.get('rejection_reason')}"
            )
            return result

        # 2. DOC / DOCX Documents: checked natively via python-docx / local inspection
        if ext in (".docx", ".doc"):
            result = _check_docx_blank_and_protection(file_path)
            logger.info(
                f"[Document {document_id}] DOCX local pre-validation result: "
                f"passed={result.get('passed')}, reason={result.get('rejection_reason')}"
            )
            return result

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
        response = await client.agents.complete_async(
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
            response = await client.agents.complete_async(
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
        # No db.update_error() here: the engine retries this activity, and the
        # workflow marks the document failed once the retries are exhausted.
        logger.error(f"[Document {document_id}] Pre-validation failed: {str(e)}")
        raise

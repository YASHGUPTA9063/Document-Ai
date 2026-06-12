import os
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

def get_template_fields(doc_type: str) -> list:
    normalized = doc_type.lower().replace(" ", "_")
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if os.path.exists(templates_path):
        try:
            with open(templates_path, "r") as f:
                templates = json.load(f)
                return templates.get(normalized)
        except Exception as e:
            logger.error(f"Failed to read templates from {templates_path}: {e}")
    return None


import re

def _calculate_field_confidence(field_value, word_confidence_scores: list) -> float:
    if not isinstance(field_value, str):
        field_str = str(field_value).strip() if field_value is not None else ""
    else:
        field_str = field_value.strip()
        
    if not field_str:
        return 1.0

    # Normalize and split field value into word tokens
    field_words = re.findall(r'\b\w+\b', field_str.lower())
    if not field_words:
        return 1.0
    
    confidences = []
    for f_word in field_words:
        # Search for this word in word_confidence_scores
        word_matches = [
            w["confidence"] for w in word_confidence_scores
            if w["text"].strip().lower() == f_word or f_word in w["text"].strip().lower()
        ]
        if word_matches:
            # Take average of matching word confidences
            confidences.append(sum(word_matches) / len(word_matches))
            
    if confidences:
        return sum(confidences) / len(confidences)
    
    return 1.0

def _compute_confidences_recursive(data, word_confidence_scores):
    if isinstance(data, dict):
        conf_dict = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                conf_dict[k] = _compute_confidences_recursive(v, word_confidence_scores)
            else:
                conf_dict[k] = _calculate_field_confidence(v, word_confidence_scores)
        return conf_dict
    elif isinstance(data, list):
        return [_compute_confidences_recursive(item, word_confidence_scores) for item in data]
    else:
        return _calculate_field_confidence(data, word_confidence_scores)


async def _run_extraction_with_agent(
    agent_id: str,
    file_path: str,
    doc_type: str,
    document_id: str,
    fields_list: list = None
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

    fields_instruction = ""
    if fields_list:
        fields_desc = []
        for f in fields_list:
            req_str = "Required" if f.get("required") else "Optional"
            fields_desc.append(f"- '{f['key']}' ({f['type']}, {req_str}): {f.get('description', '')}")
        fields_instruction = "\n".join(fields_desc)

    user_prompt = (
        f"Please extract structured data from the document located at: '{file_path}'. "
        f"You MUST call the `extract_text_from_document` tool to get the document text first."
    )
    if fields_instruction:
        user_prompt += (
            f"\n\nWe need to extract exactly the following target schema fields. Once you get the text, "
            f"your final response must be a JSON object containing ONLY these keys:\n{fields_instruction}"
        )

    messages = [
        {
            "role": "user",
            "content": user_prompt
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
    word_confidence_scores = []

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
                word_confidence_scores = ocr_result.get("word_confidence_scores", [])

                messages.append({
                    "role": "tool",
                    "name": "extract_text_from_document",
                    "content": raw_text,
                    "tool_call_id": tool_call.id
                })

        logger.info(f"[Document {document_id}] Resuming agent with tool result")
        
        # Inject custom fields schema instruction reminder
        if fields_instruction:
            messages.append({
                "role": "user",
                "content": f"Based on the tool output above, extract exactly the target schema fields. Your response MUST be a JSON object containing ONLY these keys:\n{fields_instruction}"
            })

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
        word_confidence_scores = ocr_result.get("word_confidence_scores", [])

        fallback_prompt = f"Here is the document text:\n{raw_text}\n\n"
        if fields_instruction:
            fallback_prompt += (
                f"Please extract exactly the following target schema fields. "
                f"Your response MUST be a JSON object containing ONLY these keys:\n{fields_instruction}"
            )
        else:
            fallback_prompt += "Please extract structured data in JSON format."

        response = client.agents.complete(
            agent_id=agent_id,
            messages=[{"role": "user", "content": fallback_prompt}],
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message

    content = message.content
    fields = json.loads(content)
    field_confidences = _compute_confidences_recursive(fields, word_confidence_scores)

    return {
        "fields": fields,
        "raw_ocr": raw_text,
        "confidence": ocr_confidence,
        "field_confidences": field_confidences
    }


@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")

        # Fetch custom fields template schema if configured
        fields_list = get_template_fields(doc_type)

        agent_id = DOC_TYPE_AGENT_MAP.get(doc_type.lower())
        if agent_id:
            return await _run_extraction_with_agent(agent_id, file_path, doc_type, document_id, fields_list=fields_list)
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

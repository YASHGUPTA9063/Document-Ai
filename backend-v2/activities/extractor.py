import os
import json
import logging
import re
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
from utils.norm_config import build_normalization_rules_prompt
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


def _load_template_raw(doc_type: str):
    """Load the raw template entry (could be a list or {fields, is_kyc} dict)."""
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


def get_template_fields(doc_type: str) -> list:
    """Get the fields list, handling both old (list) and new ({fields, is_kyc}) formats."""
    raw = _load_template_raw(doc_type)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("fields", [])
    return raw  # old format: bare list


def get_template_metadata(doc_type: str) -> dict:
    """Get template metadata including is_kyc flag and kyc_boxes."""
    raw = _load_template_raw(doc_type)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {
            "is_kyc": raw.get("is_kyc", False),
            "kyc_boxes": raw.get("kyc_boxes", None)
        }
    return {"is_kyc": False, "kyc_boxes": None}  # old format has no KYC flag


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


def build_json_schema_from_fields(fields_list: list) -> dict:
    properties = {}
    required = []
    
    if not fields_list:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "generic_document_extraction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "document_title": {"type": "string", "description": "Title or main heading of the document"},
                        "document_date": {"type": "string", "description": "Date associated with the document"},
                        "summary": {"type": "string", "description": "Brief summary of the document contents"},
                        "full_ocr_text": {"type": "string", "description": "The complete raw OCR text content of the document"}
                    },
                    "required": ["document_title", "summary", "full_ocr_text"]
                }
            }
        }

    for f in fields_list:
        key = f["key"]
        f_type = f.get("type", "Text").lower()
        desc = f.get("description", "")
        
        if "array" in f_type or f_type == "list":
            properties[key] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "Item description or label"},
                        "quantity": {"type": "string", "description": "Quantity or count of items"},
                        "unit_price": {"type": "string", "description": "Price per unit"},
                        "amount": {"type": "string", "description": "Total amount for the item line"}
                    }
                },
                "description": desc
            }
        else:
            properties[key] = {
                "type": "string",
                "description": desc
            }
            
        if f.get("required"):
            required.append(key)
            
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "document_fields_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


def build_ocr_prompt_from_fields(fields_list: list) -> str:
    if not fields_list:
        return "Extract structured data: document_title, document_date, summary, and copy the full OCR text into the full_ocr_text field."
    
    desc_lines = []
    for f in fields_list:
        req_str = "Required" if f.get("required") else "Optional"
        desc_lines.append(f"- '{f['key']}' ({f.get('type', 'Text')}, {req_str}): {f.get('description', '')}")
        
    fields_instruction = "\n".join(desc_lines)
    return (
        f"Extract key fields from the document following this schema:\n{fields_instruction}\n\n"
        f"Return the exact text as written in the document without normalization or cleaning."
    )


@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    """
    Step 4 — Extractor.
    Extracts fields from the document using the Extractor Agent via tools.
    """
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")

        # Determine agent routing
        agent_id = settings.GENERAL_EXTRACTOR_AGENT_ID
        if not agent_id:
            raise ValueError("GENERAL_EXTRACTOR_AGENT_ID is not configured in settings/environment.")
        logger.info(f"[Document {document_id}] Routing to general extractor agent: {agent_id}")

        # Define tools schema for Extractor Agent
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "extract_text_from_document",
                    "description": "Extracts raw text and structured data from a document using OCR and schema annotations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "The file path of the document."
                            },
                            "doc_type": {
                                "type": "string",
                                "description": "The classified document type (e.g. Invoice, PAN Card)."
                            }
                        },
                        "required": ["file_path", "doc_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "crop_kyc_images",
                    "description": "Extracts and crops signature and photo images from a KYC identity document.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "The file path of the identity document."
                            },
                            "doc_type": {
                                "type": "string",
                                "description": "The document type."
                            }
                        },
                        "required": ["file_path", "doc_type"]
                    }
                }
            }
        ]

        normalization_rules = build_normalization_rules_prompt()

        prompt = (
            f"You are the Extractor Agent. We need to extract structured data from the document "
            f"at path '{file_path}' which has been classified as '{doc_type}'.\n"
            f"First, call the `extract_text_from_document` tool to get the text content and structured OCR extraction.\n"
            f"If the document type is a KYC or identity document, you must also call the `crop_kyc_images` tool to extract the signature and photo crops.\n\n"
            f"Apply these standard normalization rules to the extracted fields:\n"
            f"{normalization_rules}\n\n"
            f"Based on the results, output a JSON response matching exactly this schema:\n"
            f"{{\n"
            f"  \"raw_extracted\": dict,\n"
            f"  \"normalized_extracted\": dict\n"
            f"}}"
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Document {document_id}] Calling Extractor Agent ({agent_id})")
        response = client.agents.complete(
            agent_id=agent_id,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        # Saved state from tool execution to merge later
        ocr_confidence = 0.0
        word_confidence_scores = []
        raw_text = ""
        kyc_image_result = None

        while message.tool_calls:
            logger.info(f"[Document {document_id}] Extractor Agent requested tool calls: {message.tool_calls}")

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
                    t_file_path = args.get("file_path", file_path)
                    t_doc_type = args.get("doc_type", doc_type)

                    logger.info(f"[Document {document_id}] Executing extract_text_from_document tool for file: {t_file_path}")

                    # Load fields for target annotations
                    fields_list = get_template_fields(t_doc_type)
                    annotation_format = build_json_schema_from_fields(fields_list)
                    annotation_prompt = build_ocr_prompt_from_fields(fields_list)

                    ocr_result = extract_with_ocr(
                        file_path=t_file_path, 
                        doc_type=t_doc_type,
                        document_annotation_format=annotation_format,
                        document_annotation_prompt=annotation_prompt
                    )

                    raw_text = ocr_result.get("raw_text", "")
                    ocr_confidence = ocr_result.get("confidence", 0.0)
                    word_confidence_scores = ocr_result.get("word_confidence_scores", [])
                    doc_annotation = ocr_result.get("document_annotation") or {}

                    tool_output = {
                        "raw_ocr_text": raw_text,
                        "structured_ocr_extraction": doc_annotation
                    }

                    messages.append({
                        "role": "tool",
                        "name": "extract_text_from_document",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tool_call.id
                    })

                elif tool_call.function.name == "crop_kyc_images":
                    args = json.loads(tool_call.function.arguments)
                    t_file_path = args.get("file_path", file_path)
                    t_doc_type = args.get("doc_type", doc_type)

                    logger.info(f"[Document {document_id}] Executing crop_kyc_images tool for file: {t_file_path}")

                    template_meta = get_template_metadata(t_doc_type)
                    kyc_boxes = template_meta.get("kyc_boxes")

                    try:
                        from utils.signature_extractor import extract_signature_and_photo
                        kyc_image_result = extract_signature_and_photo(
                            file_path=t_file_path,
                            document_id=document_id,
                            output_dir=os.path.join(settings.STORAGE_DIR, "crops", document_id),
                            kyc_boxes=kyc_boxes
                        )
                        logger.info(f"[Document {document_id}] KYC crops complete. signature={kyc_image_result.get('has_signature')}, photo={kyc_image_result.get('has_photo')}")
                        tool_output = {
                            "has_signature": kyc_image_result.get("has_signature", False),
                            "has_photo": kyc_image_result.get("has_photo", False),
                            "signer_name": kyc_image_result.get("signer_name", "")
                        }
                    except Exception as e:
                        logger.error(f"[Document {document_id}] KYC image cropping failed: {e}")
                        tool_output = {
                            "has_signature": False,
                            "has_photo": False,
                            "error": str(e)
                        }

                    messages.append({
                        "role": "tool",
                        "name": "crop_kyc_images",
                        "content": json.dumps(tool_output),
                        "tool_call_id": tool_call.id
                    })

            logger.info(f"[Document {document_id}] Resuming Extractor Agent with tool result")
            response = client.agents.complete(
                agent_id=agent_id,
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message

        # Parse final response
        content = _extract_text(message.content).strip()
        try:
            parsed_response = json.loads(content)
        except Exception as e:
            logger.error(f"[Document {document_id}] Failed to parse agent JSON output: {content}")
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed_response = json.loads(match.group(0))
            else:
                raise

        raw_extracted = parsed_response.get("raw_extracted", {})
        normalized_extracted = parsed_response.get("normalized_extracted", {})

        # Fallback if the agent returned a flat structure instead of nesting
        if not raw_extracted and not normalized_extracted:
            raw_extracted = parsed_response
            normalized_extracted = parsed_response

        # Calculate field confidences
        field_confidences = _compute_confidences_recursive(normalized_extracted, word_confidence_scores)

        # Merge KYC image data into the extracted fields if cropped
        if kyc_image_result:
            for f_dict in [normalized_extracted, raw_extracted]:
                if kyc_image_result.get("signature_base64"):
                    f_dict["signature_image"] = kyc_image_result["signature_base64"]
                f_dict["signature_detected"] = kyc_image_result.get("has_signature", False)
                if kyc_image_result.get("photo_base64"):
                    f_dict["photo_image"] = kyc_image_result["photo_base64"]
                f_dict["photo_detected"] = kyc_image_result.get("has_photo", False)
                if kyc_image_result.get("signer_name"):
                    f_dict["signer_name"] = kyc_image_result["signer_name"]

        logger.info(f"[Document {document_id}] Normalized fields from extractor: {normalized_extracted}")
        return {
            "fields": normalized_extracted,
            "raw_extracted": raw_extracted,
            "raw_ocr": raw_text,
            "confidence": ocr_confidence,
            "field_confidences": field_confidences
        }

    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

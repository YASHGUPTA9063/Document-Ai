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
        return 0.0

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
        # Default simple schema if fields_list is empty
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
                        "summary": {"type": "string", "description": "Brief summary of the document contents"}
                    },
                    "required": ["document_title"]
                }
            }
        }

    for f in fields_list:
        key = f["key"]
        f_type = f.get("type", "Text").lower()
        desc = f.get("description", "")
        
        # Build property definition
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
        return "Extract structured data from the document."
    
    desc_lines = []
    for f in fields_list:
        req_str = "Required" if f.get("required") else "Optional"
        desc_lines.append(f"- '{f['key']}' ({f.get('type', 'Text')}, {req_str}): {f.get('description', '')}")
        
    fields_instruction = "\n".join(desc_lines)
    return (
        f"Extract key fields from the document following this schema:\n{fields_instruction}\n\n"
        f"Return the exact text as written in the document without normalization or cleaning."
    )


async def _run_extraction_with_agent(
    agent_id: str,
    file_path: str,
    doc_type: str,
    document_id: str,
    fields_list: list = None,
    is_kyc: bool = False,
    kyc_boxes: dict = None
) -> dict:
    """
    Consolidated agent extraction logic using dynamic Mistral OCR structured annotation parameters.
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_text_from_document",
                "description": (
                    "Extracts structured data from a document file path "
                    "using advanced OCR and dynamic schema mapping."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The file path of the document (PDF, PNG, JPG, DOCX)."
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }
    ]

    # Build schema and prompts for Mistral OCR
    annotation_format = build_json_schema_from_fields(fields_list)
    annotation_prompt = build_ocr_prompt_from_fields(fields_list)

    fields_instruction = ""
    if fields_list:
        fields_desc = []
        for f in fields_list:
            req_str = "Required" if f.get("required") else "Optional"
            fields_desc.append(f"- '{f['key']}' ({f['type']}, {req_str}): {f.get('description', '')}")
        fields_instruction = "\n".join(fields_desc)

    normalization_rules = build_normalization_rules_prompt()
    prompt_format = (
        "Your final response MUST be a JSON object containing EXACTLY these two keys:\n"
        "1. 'raw_extracted': A JSON object containing the raw field values exactly as returned by the OCR tool (without formatting/cleaning).\n"
        "2. 'normalized_extracted': A JSON object containing the normalized/cleaned field values. Apply standard formatting rules:\n"
        f"{normalization_rules}\n\n"
        f"Target fields to extract under both 'raw_extracted' and 'normalized_extracted':\n{fields_instruction}"
    )

    user_prompt = (
        f"Please extract structured data from the document located at: '{file_path}'. "
        f"You MUST call the `extract_text_from_document` tool to get the document text first.\n\n"
        f"{prompt_format}"
    )

    messages = [
        {
            "role": "user",
            "content": user_prompt
        }
    ]

    logger.info(f"[Document {document_id}] Sending initial request to general extractor agent {agent_id} (is_kyc={is_kyc})")
    response = client.agents.complete(
        agent_id=agent_id,
        messages=messages,
        tools=tools
    )

    message = response.choices[0].message
    raw_text = ""
    ocr_confidence = 0.0
    word_confidence_scores = []
    kyc_image_result = None
    doc_annotation = {}

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
                target_file_path = target_file_path.strip("'\"").strip()

                logger.info(f"[Document {document_id}] Executing OCR tool with annotation parameters for file: {target_file_path}")
                ocr_result = extract_with_ocr(
                    file_path=target_file_path, 
                    doc_type=doc_type,
                    document_annotation_format=annotation_format,
                    document_annotation_prompt=annotation_prompt
                )
                raw_text = ocr_result.get("raw_text", "")
                ocr_confidence = ocr_result.get("confidence", 0.0)
                word_confidence_scores = ocr_result.get("word_confidence_scores", [])
                doc_annotation = ocr_result.get("document_annotation") or {}

                tool_output = json.dumps({
                    "raw_ocr_text": raw_text,
                    "structured_ocr_extraction": doc_annotation
                })

                messages.append({
                    "role": "tool",
                    "name": "extract_text_from_document",
                    "content": tool_output,
                    "tool_call_id": tool_call.id
                })

        logger.info(f"[Document {document_id}] Resuming agent with tool result")
        
        # Inject custom fields schema instruction reminder
        messages.append({
            "role": "user",
            "content": f"Based on the tool output above, extract the target schema fields. {prompt_format}"
        })

        response = client.agents.complete(
            agent_id=agent_id,
            messages=messages,
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message
    else:
        # Fallback: agent skipped the tool — run OCR ourselves
        logger.warning(f"[Document {document_id}] Agent did not request tool call. Performing fallback OCR.")
        ocr_result = extract_with_ocr(
            file_path=file_path, 
            doc_type=doc_type,
            document_annotation_format=annotation_format,
            document_annotation_prompt=annotation_prompt
        )
        raw_text = ocr_result.get("raw_text", "")
        ocr_confidence = ocr_result.get("confidence", 0.0)
        word_confidence_scores = ocr_result.get("word_confidence_scores", [])
        doc_annotation = ocr_result.get("document_annotation") or {}

        fallback_prompt = (
            f"Here is the document OCR output:\n"
            f"Structured OCR Extraction: {json.dumps(doc_annotation)}\n"
            f"Raw text: {raw_text}\n\n"
            f"Please extract the target schema fields. {prompt_format}"
        )

        response = client.agents.complete(
            agent_id=agent_id,
            messages=[{"role": "user", "content": fallback_prompt}],
            response_format={"type": "json_object"}
        )
        message = response.choices[0].message

    content = message.content
    try:
        parsed_response = json.loads(content)
    except Exception as e:
        logger.error(f"[Document {document_id}] Failed to parse agent JSON output: {content}")
        # Robust fallback regex parser if JSON format is wrapped
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

    field_confidences = _compute_confidences_recursive(normalized_extracted, word_confidence_scores)

    # For KYC docs: ALWAYS run signature+photo extraction directly
    if is_kyc:
        if kyc_boxes:
            logger.info(f"[Document {document_id}] Using template manual coordinates for KYC extraction")
        else:
            logger.info(f"[Document {document_id}] No manual coordinates — falling back to Pixtral vision")
        logger.info(f"[Document {document_id}] Running KYC image extraction (signature + photo)...")
        try:
            from utils.signature_extractor import extract_signature_and_photo
            kyc_image_result = extract_signature_and_photo(
                file_path=file_path,
                document_id=document_id,
                output_dir=os.path.join(settings.STORAGE_DIR, "crops", document_id),
                kyc_boxes=kyc_boxes
            )
            logger.info(f"[Document {document_id}] KYC extraction result: sig={kyc_image_result.get('has_signature')}, photo={kyc_image_result.get('has_photo')}")
        except Exception as e:
            logger.error(f"[Document {document_id}] KYC image extraction failed: {e}")
            kyc_image_result = None

    # Merge KYC image data into the extracted fields
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


@workflows.activity()
async def extractor_activity(document_id: str, file_path: str, doc_type: str) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting extractor activity for type: {doc_type}")

        # Fetch custom fields template schema if configured
        fields_list = get_template_fields(doc_type)
        template_meta = get_template_metadata(doc_type)
        is_kyc = template_meta.get("is_kyc", False)

        if doc_type.lower() == "kyc":
            is_kyc = True

        if is_kyc:
            logger.info(f"[Document {document_id}] KYC document detected — will extract signature + photo")

        # Route extraction to the new general extractor agent settings
        agent_id = settings.GENERAL_EXTRACTOR_AGENT_ID
        if not agent_id:
            # Fall back to others extractor if general agent not yet configured
            agent_id = settings.OTHERS_EXTRACTOR_AGENT_ID
            logger.info(f"[Document {document_id}] GENERAL_EXTRACTOR_AGENT_ID not configured. Falling back to OTHERS: {agent_id}")
        else:
            logger.info(f"[Document {document_id}] Routing to general extractor agent: {agent_id}")

        if agent_id:
            return await _run_extraction_with_agent(
                agent_id=agent_id, 
                file_path=file_path, 
                doc_type=doc_type, 
                document_id=document_id, 
                fields_list=fields_list, 
                is_kyc=is_kyc, 
                kyc_boxes=template_meta.get("kyc_boxes")
            )
        else:
            logger.warning(f"[Document {document_id}] No extractor agent configuration found.")
            return {
                "fields": {},
                "raw_extracted": {},
                "raw_ocr": "",
                "confidence": 0.0,
                "message": "No extractor agent ID configured."
            }

    except Exception as e:
        logger.error(f"[Document {document_id}] Extractor failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "extractor"})
        raise

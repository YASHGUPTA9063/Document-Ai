import os
import json
import logging
import base64
import fitz  # PyMuPDF
from mistralai.client import Mistral
from config import settings
from utils.ocr import extract_with_ocr
from utils.file_handler import get_file_as_base64

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
EXTRACTOR_TOOLS = [
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


# ─── TEMPLATE & PROMPT HELPERS ───
def _load_template_raw(doc_type: str):
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
    raw = _load_template_raw(doc_type)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("fields", [])
    return raw


def get_template_metadata(doc_type: str) -> dict:
    raw = _load_template_raw(doc_type)
    if raw is None:
        return {"is_kyc": False, "kyc_boxes": None, "use_vlm": False, "vlm_fields": []}
    if isinstance(raw, dict):
        use_vlm = raw.get("use_vlm", False)
        fields = raw.get("fields", [])
        vlm_fields = [f for f in fields if f.get("use_vlm")] if use_vlm else []
        # Fallback: if template.use_vlm is True but no fields explicitly have use_vlm: true,
        # include fields of type 'Array of Text', 'Boolean', or those describing checkboxes/ticks
        if use_vlm and not vlm_fields:
            vlm_fields = [
                f for f in fields 
                if f.get("use_vlm") 
                or f.get("type") in ["Array of Text", "Boolean"] 
                or "checkbox" in f.get("description", "").lower() 
                or "tick" in f.get("description", "").lower()
                or "check" in f.get("description", "").lower()
            ]
        return {
            "is_kyc": raw.get("is_kyc", False),
            "kyc_boxes": raw.get("kyc_boxes", None),
            "use_vlm": use_vlm,
            "vlm_fields": vlm_fields
        }
    return {"is_kyc": False, "kyc_boxes": None, "use_vlm": False, "vlm_fields": []}


def _pdf_pages_to_images(file_path: str) -> list[str]:
    """Convert each page of a PDF into high-resolution base64 JPEG data using PyMuPDF (fitz)."""
    doc = fitz.open(file_path)
    pages_b64 = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("jpeg")
        pages_b64.append(base64.b64encode(img_bytes).decode("utf-8"))
    doc.close()
    return pages_b64


def _vlm_verify_fields(file_path: str, vlm_fields: list, ocr_raw_text: str) -> dict:
    """
    Use mistral-large-latest VLM to visually inspect check boxes/tick marks for designated fields.
    Returns dict mapping field_key -> {"value": val, "confidence": conf}.
    """
    if not vlm_fields:
        return {}

    _, ext = os.path.splitext(file_path.lower())
    page_images_b64 = []

    if ext == ".pdf":
        try:
            page_images_b64 = _pdf_pages_to_images(file_path)
        except Exception as e:
            logger.error(f"Failed to rasterize PDF for VLM: {e}")
            return {}
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        try:
            page_images_b64 = [get_file_as_base64(file_path)]
        except Exception as e:
            logger.error(f"Failed to load image for VLM: {e}")
            return {}
    else:
        logger.warning(f"Unsupported file format for VLM visual verification: {ext}")
        return {}

    field_instructions = []
    for f in vlm_fields:
        field_instructions.append(f"- key: '{f['key']}' ({f.get('type', 'Text')}): {f.get('description', '')}")

    fields_text = "\n".join(field_instructions)

    prompt = (
        f"You are a visual document inspection expert.\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Carefully inspect the provided document IMAGE(S).\n"
        f"2. For each field listed below, locate the relevant section on the document and examine the checkboxes, tick marks (✓, ✗), radio buttons, or filled boxes visually.\n"
        f"3. STRIKETHROUGH / CROSSED-OUT vs ACTIVE SELECTION RULES:\n"
        f"   - STRIKETHROUGH / CROSSED OUT: Look closely for any horizontal or diagonal line drawn through an option word, text, or its checkbox. A line crossing through an option means it has been DE-SELECTED or CANCELLED. Do NOT extract struck-through options.\n"
        f"   - ACTIVE TICK MARK: Look for a checkmark (✓), tick mark, cross (✗), or filled box. The option that has a checkmark and is NOT struck through is the ACTIVE SELECTED option.\n"
        f"   - MULTIPLE OPTIONS IN A ROW: When multiple choices appear horizontally or vertically, carefully distinguish options that are struck through vs options that have a checkmark/tick.\n\n"
        f"Fields to visually inspect:\n{fields_text}\n\n"
        f"Return ONLY a valid JSON object mapping each field key to an object containing 'value' and 'confidence' (0.0 to 1.0).\n"
        f"Example output format:\n"
        f"{{\n"
        f'  "payment_method": {{"value": "Debit/Credit Card", "confidence": 0.99}}\n'
        f"}}\n"
    )

    content = []
    for b64 in page_images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
    content.append({"type": "text", "text": prompt})

    try:
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        logger.info(f"Calling Mistral VLM (mistral-large-latest) for {len(vlm_fields)} visual fields")
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content
        result_json = json.loads(response_text)
        return result_json
    except Exception as e:
        logger.error(f"VLM verification failed: {e}")
        return {}


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


# ─── OCR BLOCK STORAGE ───
def _save_ocr_blocks(document_id: str, blocks: list):
    """
    Write OCR bounding box blocks to a sidecar JSON file.
    Used by the frontend for field citation highlighting on image documents.
    Non-fatal — a warning is logged if saving fails; the workflow continues.
    """
    blocks_dir = os.path.join(settings.STORAGE_DIR, "ocr_blocks")
    os.makedirs(blocks_dir, exist_ok=True)
    blocks_path = os.path.join(blocks_dir, f"{document_id}_blocks.json")
    try:
        with open(blocks_path, "w") as f:
            json.dump(blocks, f)
        logger.info(f"Saved {len(blocks)} OCR blocks to {blocks_path}")
    except Exception as e:
        logger.warning(f"Failed to save OCR blocks for document {document_id}: {e}")


# ─── TOOL FUNCTIONS ───
def extract_text_from_document(file_path: str, doc_type: str, document_id: str = None) -> dict:
    fields_list = get_template_fields(doc_type)
    annotation_format = build_json_schema_from_fields(fields_list)
    annotation_prompt = build_ocr_prompt_from_fields(fields_list)

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
    blocks = ocr_result.get("blocks", [])

    # Persist blocks sidecar file for field citation highlighting (image documents only)
    if document_id and blocks:
        _save_ocr_blocks(document_id, blocks)

    # Perform VLM verification for visual fields if configured in template metadata
    template_meta = get_template_metadata(doc_type)
    vlm_confidences = {}

    if template_meta.get("use_vlm") and template_meta.get("vlm_fields"):
        try:
            vlm_result = _vlm_verify_fields(
                file_path=file_path,
                vlm_fields=template_meta["vlm_fields"],
                ocr_raw_text=raw_text
            )
            for key, res in vlm_result.items():
                if isinstance(res, dict) and "value" in res:
                    val = res["value"]
                    conf = res.get("confidence", 0.95)
                    doc_annotation[key] = val
                    vlm_confidences[key] = conf
                    logger.info(f"[VLM] Field '{key}' updated to '{val}' (confidence: {conf})")
        except Exception as e:
            logger.error(f"Failed to merge VLM visual verification results: {e}")

    tool_output = {
        "raw_ocr_text": raw_text,
        "structured_ocr_extraction": doc_annotation,
        "vlm_field_confidences": vlm_confidences
    }

    return {
        "tool_output": tool_output,
        "raw_text": raw_text,
        "confidence": ocr_confidence,
        "word_confidence_scores": word_confidence_scores
    }


def crop_kyc_images(file_path: str, doc_type: str, document_id: str) -> dict:
    template_meta = get_template_metadata(doc_type)
    kyc_boxes = template_meta.get("kyc_boxes")

    try:
        from utils.signature_extractor import extract_signature_and_photo
        kyc_image_result = extract_signature_and_photo(
            file_path=file_path,
            document_id=document_id,
            output_dir=os.path.join(settings.STORAGE_DIR, "crops", document_id),
            kyc_boxes=kyc_boxes
        )
        tool_output = {
            "has_signature": kyc_image_result.get("has_signature", False),
            "has_photo": kyc_image_result.get("has_photo", False),
            "signer_name": kyc_image_result.get("signer_name", "")
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] KYC image cropping failed: {e}")
        kyc_image_result = None
        tool_output = {
            "has_signature": False,
            "has_photo": False,
            "error": str(e)
        }

    return {
        "tool_output": tool_output,
        "kyc_image_result": kyc_image_result
    }

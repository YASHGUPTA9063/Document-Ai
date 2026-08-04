import os
import json
import logging
from config import settings
from utils.ocr import extract_with_ocr

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
def _normalize_template_key(name: str) -> str:
    """Collapse a template name or doc_type to a comparable key.

    Templates are saved under whatever name the user typed ("Pan", "Utility
    Bill") while the classifier emits snake_case keys ("pan_card",
    "utility_bill"), so both sides have to be normalized before comparison.
    """
    return "_".join(str(name).strip().lower().replace("-", " ").replace("_", " ").split())


def _load_template_raw(doc_type: str):
    normalized = _normalize_template_key(doc_type)
    templates_path = os.path.join(settings.STORAGE_DIR, "templates.json")
    if not os.path.exists(templates_path):
        return None

    try:
        with open(templates_path, "r") as f:
            templates = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read templates from {templates_path}: {e}")
        return None

    # Exact key first, then a normalized sweep so casing/spacing differences
    # between the saved name and the classified doc_type still resolve.
    if doc_type in templates:
        return templates[doc_type]

    for key, value in templates.items():
        if _normalize_template_key(key) == normalized:
            return value

    # A template may declare the doc types it applies to, which is the only way
    # to bind e.g. a "Pan" template to the classifier's "pan_card" output.
    for key, value in templates.items():
        if not isinstance(value, dict):
            continue
        bound = value.get("doc_types") or []
        if any(_normalize_template_key(d) == normalized for d in bound):
            return value

    logger.warning(
        f"No extraction template found for doc_type '{doc_type}' "
        f"(available: {list(templates.keys())})"
    )
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
        return {}
    if isinstance(raw, dict):
        return {
            "is_kyc": raw.get("is_kyc", False),
            "kyc_boxes": raw.get("kyc_boxes", None)
        }
    return {"is_kyc": False, "kyc_boxes": None}


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
async def extract_text_from_document(file_path: str, doc_type: str, document_id: str = None) -> dict:
    fields_list = get_template_fields(doc_type)
    annotation_format = build_json_schema_from_fields(fields_list)
    annotation_prompt = build_ocr_prompt_from_fields(fields_list)

    ocr_result = await extract_with_ocr(
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

    tool_output = {
        "raw_ocr_text": raw_text,
        "structured_ocr_extraction": doc_annotation
    }

    return {
        "tool_output": tool_output,
        "raw_text": raw_text,
        "confidence": ocr_confidence,
        "word_confidence_scores": word_confidence_scores
    }


async def crop_kyc_images(file_path: str, doc_type: str, document_id: str) -> dict:
    template_meta = get_template_metadata(doc_type)
    kyc_boxes = template_meta.get("kyc_boxes")

    try:
        from utils.signature_extractor import extract_signature_and_photo
        kyc_image_result = await extract_signature_and_photo(
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

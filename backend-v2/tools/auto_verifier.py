import os
import json
import base64 as b64mod
import tempfile
import logging
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Document, CustomerReference

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
AUTO_VERIFIER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_customer_reference",
            "description": "Searches the database for a matching customer reference and links it to the document.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_signature",
            "description": "Compares extracted document signature against the customer reference signature using DINOv2 verification pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer reference ID."
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_face",
            "description": "Compares extracted document photo against the customer reference photo using parallel face verification pipelines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer reference ID."
                    }
                },
                "required": ["customer_id"]
            }
        }
    }
]

# ─── HELPERS ───
def save_base64_to_temp_file(base64_str: str, prefix: str, ext: str = ".png") -> str:
    """Decodes base64 string and writes it to a temporary file, returning its path."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b64mod.b64decode(base64_str))
        return path
    except Exception as e:
        logger.error(f"Failed to write temp file for {prefix}: {e}")
        try:
            os.remove(path)
        except OSError:
            pass
        raise e


# ─── TOOL FUNCTIONS ───
async def find_customer_reference(document_id: str, validated_data: dict) -> dict:
    """Searches db and matches references, returning tool output and image bytes for backend caching."""
    async with AsyncSessionLocal() as session:
        doc_result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if not doc:
            return {
                "tool_output": {"matched": False, "reason": "document_not_found"},
                "reference_signature": None,
                "reference_photo": None
            }

        customer_ref = None
        if doc.customer_id:
            ref_result = await session.execute(
                select(CustomerReference).where(CustomerReference.customer_id == doc.customer_id)
            )
            customer_ref = ref_result.scalar_one_or_none()

        if not customer_ref:
            id_val = (
                validated_data.get("id_number") or 
                validated_data.get("passport_number") or 
                validated_data.get("document_number")
            )
            if id_val:
                ref_result = await session.execute(
                    select(CustomerReference).where(
                        (CustomerReference.national_id == str(id_val)) |
                        (CustomerReference.customer_id == str(id_val))
                    )
                )
                customer_ref = ref_result.scalar_one_or_none()

            if not customer_ref:
                name_val = validated_data.get("full_name") or validated_data.get("name")
                if name_val:
                    ref_result = await session.execute(
                        select(CustomerReference).where(
                            CustomerReference.full_name.ilike(str(name_val).strip())
                        )
                    )
                    customer_ref = ref_result.scalars().first()

        if not customer_ref:
            return {
                "tool_output": {"matched": False, "reason": "no_customer_reference_found"},
                "reference_signature": None,
                "reference_photo": None
            }

        # Link customer reference if not already linked
        if not doc.customer_id:
            doc.customer_id = customer_ref.customer_id
            await session.commit()

        tool_output = {
            "matched": True,
            "customer_id": customer_ref.customer_id,
            "has_doc_signature": bool(validated_data.get("signature_image")),
            "has_ref_signature": bool(customer_ref.reference_signature),
            "has_doc_photo": bool(validated_data.get("photo_image")),
            "has_ref_photo": bool(customer_ref.reference_photo)
        }

        return {
            "tool_output": tool_output,
            "reference_signature": customer_ref.reference_signature,
            "reference_photo": customer_ref.reference_photo
        }


async def verify_signature(customer_id: str, doc_sig_b64: str, ref_sig_b64: str) -> dict:
    if not ref_sig_b64:
        # Fallback reload just in case
        async with AsyncSessionLocal() as session:
            ref_res = await session.execute(
                select(CustomerReference).where(CustomerReference.customer_id == customer_id)
            )
            c_ref = ref_res.scalar_one_or_none()
            if c_ref:
                ref_sig_b64 = c_ref.reference_signature

    if not doc_sig_b64 or not ref_sig_b64:
        return {"status": "skipped", "reason": "missing_images"}

    doc_sig_path = None
    ref_sig_path = None
    try:
        doc_sig_path = save_base64_to_temp_file(doc_sig_b64, "auto_doc_sig_", ".png")
        ref_sig_path = save_base64_to_temp_file(ref_sig_b64, "auto_ref_sig_", ".png")

        from utils.signature_verifier import run_verification_pipeline
        sig_pipeline_result = await run_verification_pipeline(doc_sig_path, ref_sig_path)
        return sig_pipeline_result
    finally:
        for p in (doc_sig_path, ref_sig_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


async def verify_face(customer_id: str, doc_photo_b64: str, ref_photo_b64: str) -> dict:
    if not ref_photo_b64:
        # Fallback reload just in case
        async with AsyncSessionLocal() as session:
            ref_res = await session.execute(
                select(CustomerReference).where(CustomerReference.customer_id == customer_id)
            )
            c_ref = ref_res.scalar_one_or_none()
            if c_ref:
                ref_photo_b64 = c_ref.reference_photo

    if not doc_photo_b64 or not ref_photo_b64:
        return {"status": "skipped", "reason": "missing_images"}

    doc_photo_path = None
    ref_photo_path = None
    try:
        doc_photo_path = save_base64_to_temp_file(doc_photo_b64, "auto_doc_photo_", ".png")
        ref_photo_path = save_base64_to_temp_file(ref_photo_b64, "auto_ref_photo_", ".png")

        from utils.face_verifier import run_face_verification_pipeline
        face_pipeline_result = await run_face_verification_pipeline(doc_photo_path, ref_photo_path)
        return face_pipeline_result
    finally:
        for p in (doc_photo_path, ref_photo_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

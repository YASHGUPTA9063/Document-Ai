import os
import base64 as b64mod
import tempfile
import logging
import shutil
import mistralai.workflows as workflows
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Document, CustomerReference
from config import settings

logger = logging.getLogger(__name__)

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

@workflows.activity()
async def auto_verify_activity(document_id: str, validated_data: dict) -> dict:
    """
    Step 3.6 — Auto Verifier.
    Checks if customer reference images are available in the database and 
    automatically runs DINOv2 + Mistral signature/face verification.
    If no reference is found or credentials aren't set, it skips gracefully 
    to fallback to manual verification.
    """
    logger.info(f"[AutoVerifier] Starting auto verification for document {document_id}")
    
    if not validated_data:
        logger.warning(f"[AutoVerifier] No validated data provided for document {document_id}.")
        return {"status": "skipped", "reason": "empty_validated_data"}

    async with AsyncSessionLocal() as session:
        # 1. Fetch document
        doc_result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            logger.warning(f"[AutoVerifier] Document {document_id} not found in DB.")
            return {"status": "skipped", "reason": "document_not_found"}

        # 2. Identify the customer reference
        customer_ref = None
        
        # Try finding by document's customer_id first
        if doc.customer_id:
            ref_result = await session.execute(
                select(CustomerReference).where(CustomerReference.customer_id == doc.customer_id)
            )
            customer_ref = ref_result.scalar_one_or_none()
            
        # Try dynamic lookup using extracted National ID / Passport / Name if customer_id not matched
        if not customer_ref:
            # Try matching by ID number or passport number
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
                
            # If still not found, try matching by name (case-insensitive)
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
            logger.info(f"[AutoVerifier] No CustomerReference match found in DB for document {document_id}. Skipping auto-verification.")
            return {"status": "skipped", "reason": "no_customer_reference_found"}

        logger.info(f"[AutoVerifier] Associated document {document_id} with customer reference {customer_ref.customer_id}")
        
        # Link document's customer_id in DB if not already set
        if not doc.customer_id:
            doc.customer_id = customer_ref.customer_id
            await session.commit()

        results = {"signature": None, "photo": None}
        temp_files = []

        try:
            # 3. Auto-verify Signature if both crops exist
            doc_sig_b64 = validated_data.get("signature_image")
            ref_sig_b64 = customer_ref.reference_signature
            
            if doc_sig_b64 and ref_sig_b64:
                logger.info(f"[AutoVerifier] Reference and extracted signatures found. Running signature verification...")
                try:
                    doc_sig_path = save_base64_to_temp_file(doc_sig_b64, "auto_doc_sig_", ".png")
                    ref_sig_path = save_base64_to_temp_file(ref_sig_b64, "auto_ref_sig_", ".png")
                    temp_files.extend([doc_sig_path, ref_sig_path])
                    
                    from utils.signature_verifier import run_verification_pipeline
                    sig_pipeline_result = await run_verification_pipeline(doc_sig_path, ref_sig_path)
                    results["signature"] = sig_pipeline_result
                    logger.info(f"[AutoVerifier] Signature verification finished with verdict: {sig_pipeline_result.get('verdict')}")
                except Exception as sig_err:
                    logger.error(f"[AutoVerifier] Auto signature verification failed: {sig_err}", exc_info=True)
            else:
                logger.info(f"[AutoVerifier] Signature images not available for auto-verification (extracted={bool(doc_sig_b64)}, reference={bool(ref_sig_b64)}).")

            # 4. Auto-verify Photo if both crops exist
            doc_photo_b64 = validated_data.get("photo_image")
            ref_photo_b64 = customer_ref.reference_photo
            
            if doc_photo_b64 and ref_photo_b64:
                logger.info(f"[AutoVerifier] Reference and extracted photos found. Running face verification...")
                try:
                    doc_photo_path = save_base64_to_temp_file(doc_photo_b64, "auto_doc_photo_", ".png")
                    ref_photo_path = save_base64_to_temp_file(ref_photo_b64, "auto_ref_photo_", ".png")
                    temp_files.extend([doc_photo_path, ref_photo_path])
                    
                    from utils.face_verifier import run_face_verification_pipeline
                    face_pipeline_result = await run_face_verification_pipeline(doc_photo_path, ref_photo_path)
                    results["photo"] = face_pipeline_result
                    logger.info(f"[AutoVerifier] Face verification finished with verdict: {face_pipeline_result.get('verdict')}")
                except Exception as face_err:
                    logger.error(f"[AutoVerifier] Auto face verification failed: {face_err}", exc_info=True)
            else:
                logger.info(f"[AutoVerifier] Face images not available for auto-verification (extracted={bool(doc_photo_b64)}, reference={bool(ref_photo_b64)}).")

            return {
                "status": "success",
                "signature": results["signature"],
                "photo": results["photo"]
            }

        finally:
            # 5. Clean up all temporary files created for ML pipelines
            for path in temp_files:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError as e:
                    logger.warning(f"[AutoVerifier] Error deleting temp file {path}: {e}")

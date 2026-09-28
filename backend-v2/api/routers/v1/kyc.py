"""
KYC Router
==========
KYC application creation, listing, document upload, verification, and results.

Mirrors the claims router pattern: the upload endpoint reuses the existing
document OCR pipeline — documents are uploaded via /documents/upload with a
kyc_id query param, then linked to the KYC application.
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks

import db.kyc_operations as kyc_db
from schemas.kyc import CreateKycApplicationRequest, UpdateKycFormRequest, KycDecisionRequest
from activities.kyc_verifier import verify_kyc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["KYC"])


@router.post("/kyc")
async def create_kyc_application(request: CreateKycApplicationRequest):
    """
    Create a new KYC application with applicant form data.
    The form data can come from manual entry or from OCR extraction of an uploaded form.
    """
    app = await kyc_db.create_kyc_application(
        applicant_name=request.applicant_name,
        fathers_name=request.fathers_name,
        date_of_birth=request.date_of_birth,
        address=request.address,
        form_source=request.form_source or "manual",
        form_document_id=request.form_document_id,
    )
    return {
        "kyc_id": app.kyc_id,
        "applicant_name": app.applicant_name,
        "fathers_name": app.fathers_name,
        "date_of_birth": app.date_of_birth,
        "address": app.address,
        "form_source": app.form_source,
        "status": app.status,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


@router.get("/kyc")
async def list_kyc_applications():
    """Return all KYC applications ordered by newest first."""
    apps = await kyc_db.get_all_kyc_applications()
    result = []
    for a in apps:
        result.append({
            "kyc_id": a.kyc_id,
            "applicant_name": a.applicant_name,
            "fathers_name": a.fathers_name,
            "date_of_birth": a.date_of_birth,
            "address": a.address,
            "form_source": a.form_source,
            "status": a.status,
            "photo_url": f"/api/v1/kyc/{a.kyc_id}/attachment/photo" if a.photo_path else None,
            "signature_url": f"/api/v1/kyc/{a.kyc_id}/attachment/signature" if a.signature_path else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return result


@router.get("/kyc/{kyc_id}")
async def get_kyc_application(kyc_id: str):
    """Get a single KYC application by ID."""
    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")
    return {
        "kyc_id": app.kyc_id,
        "applicant_name": app.applicant_name,
        "fathers_name": app.fathers_name,
        "date_of_birth": app.date_of_birth,
        "address": app.address,
        "form_source": app.form_source,
        "form_document_id": app.form_document_id,
        "photo_url": f"/api/v1/kyc/{app.kyc_id}/attachment/photo" if app.photo_path else None,
        "signature_url": f"/api/v1/kyc/{app.kyc_id}/attachment/signature" if app.signature_path else None,
        "status": app.status,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


@router.put("/kyc/{kyc_id}")
async def update_kyc_form(kyc_id: str, request: UpdateKycFormRequest):
    """Update the applicant's form data (corrections or edits)."""
    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    updated = await kyc_db.update_kyc_form_data(
        kyc_id=kyc_id,
        applicant_name=request.applicant_name,
        fathers_name=request.fathers_name,
        date_of_birth=request.date_of_birth,
        address=request.address,
    )
    return {
        "kyc_id": updated.kyc_id,
        "applicant_name": updated.applicant_name,
        "fathers_name": updated.fathers_name,
        "date_of_birth": updated.date_of_birth,
        "address": updated.address,
        "status": updated.status,
    }


@router.get("/kyc/{kyc_id}/status")
async def get_kyc_status(kyc_id: str):
    """Get the extraction status of linked KYC documents."""
    status = await kyc_db.get_kyc_doc_status(kyc_id)
    if not status.get("found"):
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")
    return status


@router.post("/kyc/{kyc_id}/upload-doc")
async def upload_kyc_document(
    kyc_id: str,
    file: UploadFile = File(...),
    doc_type: str = Query(..., description="Document type: 'passport' or 'driving_license'"),
):
    """
    Upload an identity document for KYC verification.
    Reuses the existing document upload + OCR pipeline.
    Links the uploaded document to this KYC application.
    """
    import uuid
    import os
    from db.database import AsyncSessionLocal
    from db.models import Document
    from config import settings
    from api.queue import submit_document_run

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    if doc_type not in ("passport", "driving_license"):
        raise HTTPException(status_code=400, detail="doc_type must be 'passport' or 'driving_license'")

    ALLOWED_TYPES = {
        "application/pdf", "image/png", "image/jpeg", "image/jpg",
        "image/tiff", "image/bmp", "image/webp",
    }
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Save file using the existing utility
    from utils.file_handler import save_file
    from config import settings
    import uuid as _uuid

    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
    batch_id = f"kyc-{_uuid.uuid4().hex[:12]}"

    # Create Document record and start OCR
    from db.database import AsyncSessionLocal
    from db.models import Document
    from api.queue import submit_document_run

    async with AsyncSessionLocal() as session:
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            batch_id=batch_id,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        # Start OCR pipeline
        run_id = await submit_document_run(
            doc.id, doc.filename, doc.file_path, auto_split=False,
        )
        if run_id:
            doc.workflow_run_id = run_id
            await session.commit()

    # Link document to KYC application
    await kyc_db.link_document_to_kyc(kyc_id, doc.id, doc_type)

    return {
        "kyc_id": kyc_id,
        "document_id": doc.id,
        "doc_type": doc_type,
        "filename": doc.filename,
        "status": "extracting",
        "message": f"{doc_type.replace('_', ' ').title()} uploaded. OCR extraction started.",
    }


@router.post("/kyc/{kyc_id}/upload-form")
async def upload_kyc_form(
    kyc_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a pre-filled application form for OCR extraction.
    The form goes through the document processing pipeline. Once extraction
    completes, the extracted fields (name, father's name, DOB, address) are
    synced back into the KYC application.
    """
    from utils.file_handler import save_file
    from config import settings
    import uuid as _uuid
    from db.database import AsyncSessionLocal
    from db.models import Document, KycApplication
    from api.queue import submit_document_run
    from sqlalchemy.future import select

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    ALLOWED_TYPES = {
        "application/pdf", "image/png", "image/jpeg", "image/jpg",
        "image/tiff", "image/bmp", "image/webp",
    }
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
    batch_id = f"kyc-form-{_uuid.uuid4().hex[:12]}"

    async with AsyncSessionLocal() as session:
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            batch_id=batch_id,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        # Start OCR pipeline
        run_id = await submit_document_run(
            doc.id, doc.filename, doc.file_path, auto_split=False,
        )
        if run_id:
            doc.workflow_run_id = run_id
            await session.commit()

        # Link the form document to the KYC application
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        kyc_app = result.scalar_one_or_none()
        if kyc_app:
            kyc_app.form_document_id = doc.id
            kyc_app.form_source = "uploaded"
            await session.commit()

    # Define a background task to extract signature/photo from the form
    def _extract_and_save_attachments(kid: str, f_path: str, d_id: str):
        import base64
        import os
        import uuid as _uuid
        from utils.signature_extractor import extract_signature_and_photo
        from config import settings
        from db.database import SessionLocal
        from db.models import KycApplication
        
        try:
            logger.info(f"[KYC {kid}] Background extraction of photo/signature from form started.")
            # Run the extraction (this uses Mistral/Pixtral)
            ext_result = extract_signature_and_photo(
                file_path=f_path,
                document_id=d_id
            )
            
            with SessionLocal() as sync_session:
                app_obj = sync_session.query(KycApplication).filter_by(kyc_id=kid).first()
                if not app_obj:
                    return

                kyc_dir = os.path.join(settings.STORAGE_DIR, "kyc_attachments", kid)
                os.makedirs(kyc_dir, exist_ok=True)

                if ext_result.get("has_photo") and ext_result.get("photo_base64"):
                    p_data = base64.b64decode(ext_result["photo_base64"])
                    p_path = os.path.join(kyc_dir, f"photo_{_uuid.uuid4().hex[:8]}.png")
                    with open(p_path, "wb") as pf:
                        pf.write(p_data)
                    app_obj.photo_path = p_path
                    logger.info(f"[KYC {kid}] Form photo extracted and saved.")

                if ext_result.get("has_signature") and ext_result.get("signature_base64"):
                    s_data = base64.b64decode(ext_result["signature_base64"])
                    s_path = os.path.join(kyc_dir, f"signature_{_uuid.uuid4().hex[:8]}.png")
                    with open(s_path, "wb") as sf:
                        sf.write(s_data)
                    app_obj.signature_path = s_path
                    logger.info(f"[KYC {kid}] Form signature extracted and saved.")
                    
                sync_session.commit()
        except Exception as e:
            logger.error(f"[KYC {kid}] Background extraction failed: {e}")

    background_tasks.add_task(_extract_and_save_attachments, kyc_id, file_path, doc.id)

    logger.info(f"[KYC {kyc_id}] Form uploaded as document {doc.id}, OCR started.")
    return {
        "kyc_id": kyc_id,
        "document_id": doc.id,
        "filename": doc.filename,
        "status": "processing",
        "message": "Form uploaded. OCR extraction started — poll /kyc/{kyc_id}/form-status for results.",
    }


@router.get("/kyc/{kyc_id}/form-status")
async def get_kyc_form_status(kyc_id: str):
    """
    Poll the OCR extraction status of the uploaded form.
    When complete, returns the extracted fields so the frontend can populate the form.
    """
    from db.database import AsyncSessionLocal
    from db.models import Document, ExtractedData, KycApplication
    from sqlalchemy.future import select

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")
    if not app.form_document_id:
        return {"kyc_id": kyc_id, "status": "no_form", "extracted_fields": None}

    async with AsyncSessionLocal() as session:
        doc_result = await session.execute(
            select(Document).where(Document.id == app.form_document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if not doc:
            return {"kyc_id": kyc_id, "status": "not_found", "extracted_fields": None}

        if doc.status not in ("completed", "failed", "rejected"):
            return {"kyc_id": kyc_id, "status": doc.status, "extracted_fields": None}

        if doc.status in ("failed", "rejected"):
            return {"kyc_id": kyc_id, "status": "failed", "extracted_fields": None}

        # Fetch extracted data
        ed_result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == app.form_document_id)
        )
        extracted = ed_result.scalar_one_or_none()
        fields = extracted.validated_data if extracted else {}

        # Auto-populate the KYC application with extracted fields
        kyc_result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        kyc_app = kyc_result.scalar_one_or_none()
        if kyc_app and fields:
            # Try common field names from different form types
            name = fields.get("name") or fields.get("applicant_name") or fields.get("full_name") or fields.get("claimant_name")
            father = fields.get("fathers_name") or fields.get("father_name") or fields.get("father's_name") or fields.get("s/o") or fields.get("son_of")
            dob = fields.get("date_of_birth") or fields.get("dob") or fields.get("DOB") or fields.get("birth_date")
            addr = fields.get("address") or fields.get("residential_address") or fields.get("permanent_address")

            if name and not kyc_app.applicant_name:
                kyc_app.applicant_name = str(name)
            if father and not kyc_app.fathers_name:
                kyc_app.fathers_name = str(father)
            if dob and not kyc_app.date_of_birth:
                kyc_app.date_of_birth = str(dob)
            if addr and not kyc_app.address:
                kyc_app.address = str(addr)
            await session.commit()

        return {
            "kyc_id": kyc_id,
            "status": "completed",
            "extracted_fields": fields,
            "populated": {
                "applicant_name": kyc_app.applicant_name if kyc_app else None,
                "fathers_name": kyc_app.fathers_name if kyc_app else None,
                "date_of_birth": kyc_app.date_of_birth if kyc_app else None,
                "address": kyc_app.address if kyc_app else None,
                "photo_url": f"/api/v1/kyc/{kyc_id}/attachment/photo" if kyc_app and kyc_app.photo_path else None,
                "signature_url": f"/api/v1/kyc/{kyc_id}/attachment/signature" if kyc_app and kyc_app.signature_path else None,
            },
        }


@router.post("/kyc/{kyc_id}/upload-attachment")
async def upload_kyc_attachment(
    kyc_id: str,
    file: UploadFile = File(...),
    attachment_type: str = Query(..., description="'photo' or 'signature'"),
):
    """
    Upload the applicant's photo or signature image.
    Stored as a simple file — no OCR pipeline needed.
    """
    import os
    import uuid as _uuid
    from config import settings
    from db.database import AsyncSessionLocal
    from db.models import KycApplication
    from sqlalchemy.future import select

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    if attachment_type not in ("photo", "signature"):
        raise HTTPException(status_code=400, detail="attachment_type must be 'photo' or 'signature'")

    ALLOWED = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"}
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only image files are allowed for photo/signature")

    # Save to a kyc-specific subfolder
    kyc_dir = os.path.join(settings.STORAGE_DIR, "kyc_attachments", kyc_id)
    os.makedirs(kyc_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    file_name = f"{attachment_type}_{_uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(kyc_dir, file_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update the KYC application
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        kyc_app = result.scalar_one_or_none()
        if kyc_app:
            if attachment_type == "photo":
                kyc_app.photo_path = file_path
            else:
                kyc_app.signature_path = file_path
            await session.commit()

    logger.info(f"[KYC {kyc_id}] {attachment_type} uploaded to {file_path}")
    return {
        "kyc_id": kyc_id,
        "attachment_type": attachment_type,
        "filename": file.filename,
        "url": f"/api/v1/kyc/{kyc_id}/attachment/{attachment_type}",
    }


@router.get("/kyc/{kyc_id}/attachment/{attachment_type}")
async def get_kyc_attachment(kyc_id: str, attachment_type: str):
    """Serve the applicant's photo or signature image."""
    import os
    import mimetypes
    from fastapi.responses import FileResponse

    if attachment_type not in ("photo", "signature"):
        raise HTTPException(status_code=400, detail="attachment_type must be 'photo' or 'signature'")

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    file_path = app.photo_path if attachment_type == "photo" else app.signature_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"No {attachment_type} uploaded for this application")

    mime_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(
        file_path,
        media_type=mime_type or "image/jpeg",
        content_disposition_type="inline",
        headers={"Cache-Control": "no-cache"},
    )

@router.post("/kyc/{kyc_id}/verify")
async def run_kyc_verification(kyc_id: str):
    """
    Trigger KYC verification: cross-validates form data against extracted document data.
    Runs synchronously (no workflow needed — single-step verification).
    """
    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    # Sync any pending OCR extractions
    await kyc_db.sync_kyc_document_fields(kyc_id)

    # Check we have at least one extracted doc
    status = await kyc_db.get_kyc_doc_status(kyc_id)
    if status["completed_docs"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents have been extracted yet. Upload and wait for OCR to complete."
        )

    # Gather form data
    import base64
    def _read_b64(path):
        import os
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        return None

    form_data = {
        "applicant_name": app.applicant_name or "",
        "fathers_name": app.fathers_name or "",
        "date_of_birth": app.date_of_birth or "",
        "address": app.address or "",
        "photo_image": _read_b64(app.photo_path),
        "signature_image": _read_b64(app.signature_path),
    }

    # Gather doc data (merge all extracted fields from linked KYC docs)
    doc_data = {}
    for ds in status.get("doc_statuses", []):
        if ds["synced"] == "synced":
            from db.database import AsyncSessionLocal
            from db.models import KycDocument
            from sqlalchemy.future import select
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(KycDocument).where(
                        KycDocument.kyc_id == kyc_id,
                        KycDocument.document_id == ds["document_id"]
                    )
                )
                kyc_doc = result.scalar_one_or_none()
                if kyc_doc and kyc_doc.extracted_fields:
                    doc_data.update(kyc_doc.extracted_fields)

    if not doc_data:
        raise HTTPException(
            status_code=400,
            detail="Document extraction completed but no fields were extracted. The document may not contain readable text."
        )

    # Update status
    await kyc_db.update_kyc_status(kyc_id, "verifying")

    # Run verification
    try:
        result = await verify_kyc(form_data, doc_data)

        # Save result
        await kyc_db.save_kyc_result(
            kyc_id=kyc_id,
            form_data=form_data,
            doc_data=doc_data,
            field_checks=result["field_checks"],
            overall_status=result["overall_status"],
            confidence=result["confidence"],
            summary=result["summary"],
        )

        # Update application status
        final_status = "completed"
        await kyc_db.update_kyc_status(kyc_id, final_status)

        return {
            "kyc_id": kyc_id,
            "status": final_status,
            **result,
        }
    except Exception as e:
        logger.error(f"[KYC {kyc_id}] Verification failed: {e}")
        await kyc_db.update_kyc_status(kyc_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kyc/{kyc_id}/result")
async def get_kyc_result(kyc_id: str):
    """Get the final KYC verification result."""
    result = await kyc_db.get_kyc_result(kyc_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No verification result found for KYC {kyc_id}. Run /kyc/{kyc_id}/verify first."
        )
    return {
        "kyc_id": result.kyc_id,
        "form_data": result.form_data,
        "doc_data": result.doc_data,
        "field_checks": result.field_checks,
        "overall_status": result.overall_status,
        "confidence": result.confidence,
        "summary": result.summary,
        "processed_at": result.processed_at.isoformat() if result.processed_at else None,
    }


@router.post("/kyc/{kyc_id}/decision")
async def submit_kyc_decision(kyc_id: str, request: KycDecisionRequest):
    """Records the reviewer's final KYC decision (approve/reject)."""
    if request.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    new_status = "verified" if request.decision == "approve" else "failed"
    await kyc_db.update_kyc_status(kyc_id, new_status)

    logger.info(f"[KYC {kyc_id}] Decision: {new_status}. Notes: {request.notes}")
    return {"kyc_id": kyc_id, "decision": new_status, "notes": request.notes}


@router.delete("/kyc/{kyc_id}")
async def delete_kyc_application(kyc_id: str):
    """Permanently deletes a KYC application and all its linked records."""
    deleted = await kyc_db.delete_kyc_application(kyc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")
    return {"kyc_id": kyc_id, "deleted": True}

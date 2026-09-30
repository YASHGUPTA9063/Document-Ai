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
from typing import Optional

from schemas.kyc import (
    CreateKycApplicationRequest, UpdateKycFormRequest, KycDecisionRequest, KycVerifyRequest,
)
from activities.kyc_verifier import verify_kyc, extract_identity_fields, extract_utility_address
from activities.kyc_images import (
    extract_form_images, extract_doc_images, ensure_images_ready, adopt_pipeline_images,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["KYC"])

# Pipeline classification of a utility bill — the preferred proof of address.
UTILITY_BILL_TYPE = "utility_bill"


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
        **{k: getattr(request, k) for k in kyc_db.APPLICANT_DETAIL_FIELDS},
    )
    return {
        "kyc_id": app.kyc_id,
        "applicant_name": app.applicant_name,
        "fathers_name": app.fathers_name,
        "date_of_birth": app.date_of_birth,
        "address": app.address,
        **kyc_db.applicant_details(app),
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
            **kyc_db.applicant_details(a),
            "form_source": a.form_source,
            "form_document_id": a.form_document_id,
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
        **kyc_db.applicant_details(app),
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
        **{k: getattr(request, k) for k in kyc_db.APPLICANT_DETAIL_FIELDS},
    )
    return {
        "kyc_id": updated.kyc_id,
        "applicant_name": updated.applicant_name,
        "fathers_name": updated.fathers_name,
        "date_of_birth": updated.date_of_birth,
        "address": updated.address,
        **kyc_db.applicant_details(updated),
        "status": updated.status,
    }


@router.get("/kyc/{kyc_id}/status")
async def get_kyc_status(kyc_id: str):
    """Get the extraction status of linked KYC documents."""
    status = await kyc_db.get_kyc_doc_status(kyc_id)
    if not status.get("found"):
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")
    if status["ready_to_verify"]:
        # Only now is every pipeline run finished, so its crops are final —
        # adopt them before the UI shows the ID's photo/signature.
        await adopt_pipeline_images(kyc_id)
        status = await kyc_db.get_kyc_doc_status(kyc_id)
    return status


@router.post("/kyc/{kyc_id}/upload-doc")
async def upload_kyc_document(
    kyc_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    upload_batch: Optional[str] = Query(
        None, description="Batch id returned by a previous upload — pass it to group files added together",
    ),
):
    """
    Upload an identity document for KYC verification.
    Reuses the existing document upload + OCR pipeline for the text fields, and
    crops the holder's photo and signature in the background so they can be
    compared against the ones from the application form.
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
    upload_batch = upload_batch or f"kycb-{_uuid.uuid4().hex[:12]}"
    # Files uploaded together form one checklist batch, so the Step 3.2
    # checklist judges them as a set instead of one document at a time.
    batch_id = upload_batch

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
    await kyc_db.link_document_to_kyc(kyc_id, doc.id, upload_batch=upload_batch)

    # Mark as running before responding so /status never reports ready_to_verify
    # in the gap before the background task starts.
    await kyc_db.set_doc_images(kyc_id, doc.id, "running")
    background_tasks.add_task(extract_doc_images, kyc_id, file_path, doc.id)

    return {
        "kyc_id": kyc_id,
        "document_id": doc.id,
        "upload_batch": upload_batch,
        "filename": doc.filename,
        "status": "extracting",
        "message": "Identity document uploaded. OCR extraction started.",
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

    # Crop the applicant's photo + signature from the form in the background.
    # Marked running up front so /form-status keeps the frontend polling until
    # the crops are ready, not just the OCR text.
    await kyc_db.set_form_images(kyc_id, "running")
    background_tasks.add_task(extract_form_images, kyc_id, file_path, doc.id)

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
    from db.models import Document
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

        # awaiting_review = the pipeline parked the form for a human reviewer. The
        # KYC flow has its own review step and its own form extraction, so it
        # doesn't wait on that gate.
        if doc.status not in ("completed", "awaiting_review", "failed", "rejected"):
            return {"kyc_id": kyc_id, "status": doc.status, "extracted_fields": None}

        if doc.status in ("failed", "rejected"):
            return {"kyc_id": kyc_id, "status": "failed", "extracted_fields": None}

        # Text is done — hold the frontend until the photo/signature crops are too,
        # so the review step shows them.
        if app.form_images_status == "running":
            return {"kyc_id": kyc_id, "status": "extracting_images", "extracted_fields": None}

    # The dedicated form pass (extract_form_images) has already filled what it
    # found; the pipeline's template fields cover anything it missed, and its
    # photo/signature crops fill any image our crop missed.
    fields = await kyc_db.get_validated_data(app.form_document_id)
    # Images are served via /attachment URLs, not inline base64.
    for k in ("photo_image", "signature_image"):
        fields.pop(k, None)
    if fields:
        await kyc_db.fill_empty_form_fields(kyc_id, **extract_identity_fields(fields))
    await adopt_pipeline_images(kyc_id)
    kyc_app = await kyc_db.get_kyc_application(kyc_id)

    return {
        "kyc_id": kyc_id,
        "status": "completed",
        "extracted_fields": fields,
        "images_status": kyc_app.form_images_status if kyc_app else None,
        "populated": {
            "applicant_name": kyc_app.applicant_name if kyc_app else None,
            "fathers_name": kyc_app.fathers_name if kyc_app else None,
            "date_of_birth": kyc_app.date_of_birth if kyc_app else None,
            "address": kyc_app.address if kyc_app else None,
            **(kyc_db.applicant_details(kyc_app) if kyc_app else {}),
            "photo_url": kyc_db.kyc_form_image_url(kyc_id, "photo") if kyc_app and kyc_app.photo_path else None,
            "signature_url": kyc_db.kyc_form_image_url(kyc_id, "signature") if kyc_app and kyc_app.signature_path else None,
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

@router.get("/kyc/{kyc_id}/documents/{document_id}/attachment/{attachment_type}")
async def get_kyc_doc_attachment(kyc_id: str, document_id: str, attachment_type: str):
    """Serve the photo or signature cropped from an uploaded ID document."""
    import os
    from fastapi.responses import FileResponse

    if attachment_type not in ("photo", "signature"):
        raise HTTPException(status_code=400, detail="attachment_type must be 'photo' or 'signature'")

    kyc_doc = await kyc_db.get_kyc_document(kyc_id, document_id)
    if not kyc_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} is not linked to KYC {kyc_id}")

    file_path = kyc_doc.photo_path if attachment_type == "photo" else kyc_doc.signature_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"No {attachment_type} extracted from this document")

    return FileResponse(
        file_path,
        media_type="image/png",
        content_disposition_type="inline",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/kyc/{kyc_id}/verify")
async def run_kyc_verification(kyc_id: str, request: Optional[KycVerifyRequest] = None):
    """
    Trigger KYC verification: cross-validates form data against extracted document data.
    Runs synchronously (no workflow needed — single-step verification).
    `document_ids` limits the check to the ID documents the user selected.
    """
    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"KYC application {kyc_id} not found")

    selected_ids = set(request.document_ids) if request and request.document_ids else None

    # Sync any pending OCR extractions
    await kyc_db.sync_kyc_document_fields(kyc_id)

    # Check we have at least one extracted doc among the selected ones
    status = await kyc_db.get_kyc_doc_status(kyc_id)
    completed_ids = {
        ds["document_id"] for ds in status["doc_statuses"] if ds["status"] == "completed"
    }
    if selected_ids is not None:
        unknown = selected_ids - {ds["document_id"] for ds in status["doc_statuses"]}
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Documents not linked to KYC {kyc_id}: {', '.join(sorted(unknown))}",
            )
        completed_ids &= selected_ids
    if not completed_ids:
        raise HTTPException(
            status_code=400,
            detail="No selected documents have been extracted yet. Upload and wait for OCR to complete."
        )

    # Make sure the photo/signature crops (form + ID) are finished, then re-read
    # the application since the form crop may have just filled photo/signature.
    await ensure_images_ready(kyc_id)
    await adopt_pipeline_images(kyc_id)
    app = await kyc_db.get_kyc_application(kyc_id)

    import base64
    import os

    def _read_b64(path):
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        return None

    form_data = {
        "applicant_name": app.applicant_name or "",
        "date_of_birth": app.date_of_birth or "",
        "fathers_name": app.fathers_name or "",
        "address": app.address or "",
        "photo_image": _read_b64(app.photo_path),
        "signature_image": _read_b64(app.signature_path),
    }

    # Gather doc data: merge text fields from all synced ID docs; take the
    # photo/signature from the first doc that yielded each crop.
    doc_data = {}
    doc_image_urls = {"photo": None, "signature": None}
    kyc_docs = await kyc_db.get_kyc_documents(kyc_id)
    for kyc_doc in kyc_docs:
        if kyc_doc.synced != "synced":
            continue
        if selected_ids is not None and kyc_doc.document_id not in selected_ids:
            continue
        fields = dict(kyc_doc.extracted_fields or {})
        # The generic pipeline only inlines crops for is_kyc templates — keep
        # them as a fallback, but prefer the dedicated KYC crop.
        inline = {k: fields.pop(k, None) for k in ("photo_image", "signature_image")}
        doc_data.update({k: v for k, v in fields.items() if k not in doc_data or not doc_data[k]})

        for kind, path in (("photo", kyc_doc.photo_path), ("signature", kyc_doc.signature_path)):
            key = f"{kind}_image"
            if doc_data.get(key):
                continue
            img = _read_b64(path)
            if img:
                doc_data[key] = img
                doc_image_urls[kind] = kyc_db.kyc_doc_image_url(kyc_id, kyc_doc.document_id, kind)
            elif inline.get(key):
                doc_data[key] = inline[key]

    if not any(k not in ("photo_image", "signature_image") for k in doc_data):
        raise HTTPException(
            status_code=400,
            detail="Document extraction completed but no fields were extracted. The document may not contain readable text."
        )

    # Address: prefer a utility bill uploaded together with the chosen document —
    # it's the usual proof of address, and many IDs don't print one. Falls back
    # to whatever address the chosen document itself carries.
    address_source = None
    chosen_batches = {
        ds["upload_batch"] for ds in status["doc_statuses"] if ds["document_id"] in completed_ids
    }
    utility_bills = [
        ds for ds in status["doc_statuses"]
        if ds["classified_type"] == UTILITY_BILL_TYPE
        and ds["status"] == "completed"
        and ds["upload_batch"] in chosen_batches
    ]
    docs_by_id = {d.document_id: d for d in kyc_docs}
    for ds in reversed(utility_bills):  # newest first
        bill = docs_by_id.get(ds["document_id"])
        address = extract_utility_address(bill.extracted_fields) if bill and bill.synced == "synced" else None
        if address:
            doc_data["address"] = address
            address_source = f"Utility bill · {ds['filename']}"
            break

    # Update status
    await kyc_db.update_kyc_status(kyc_id, "verifying")

    # Run verification
    try:
        result = await verify_kyc(form_data, doc_data)

        # Attach image links so the UI can show both sides of each comparison.
        form_image_urls = {
            "photo": kyc_db.kyc_form_image_url(kyc_id, "photo") if app.photo_path else None,
            "signature": kyc_db.kyc_form_image_url(kyc_id, "signature") if app.signature_path else None,
        }
        for check in result["field_checks"]:
            if check["field"] == "Address" and address_source:
                check["doc_source"] = address_source
            kind = {"Applicant Photo": "photo", "Applicant Signature": "signature"}.get(check["field"])
            if kind:
                check["form_image_url"] = form_image_urls[kind]
                check["doc_image_url"] = doc_image_urls[kind]

        # Snapshots keep text only — images stay on disk, referenced by URL.
        def _strip_images(d):
            return {k: v for k, v in d.items() if k not in ("photo_image", "signature_image")}

        await kyc_db.save_kyc_result(
            kyc_id=kyc_id,
            form_data={**_strip_images(form_data), **{f"{k}_url": v for k, v in form_image_urls.items()}},
            doc_data={**_strip_images(doc_data), **{f"{k}_url": v for k, v in doc_image_urls.items()}},
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

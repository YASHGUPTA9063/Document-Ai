"""
Documents Router
================
Document upload, status, retrieval, extracted-data editing, KYC crops,
signature/photo verification, customer references, and cross-document
validation.

Paths are resource-prefixed (`/documents/...`, `/batches/...`) and served under
`/api/v1` by main.py. Three of them were flat in an earlier build — `/upload`,
`/upload/batch`, `/status/{id}` — and api/routers/v1/__init__.py re-registers
those same handler functions at their old addresses while
ENABLE_LEGACY_ROOT_ROUTES is on.

Uploads never talk to Mistral from here. They go through
api.queue.submit_document_run, which enqueues for the arq dispatcher under
EXECUTION_MODE=queue and starts the run in-request under `inline`. That is why
`workflow_run_id` can come back empty from an upload: under `queue` the
dispatcher assigns it moments later and writes it to the row.
"""

import os
import json
import re as _re
import uuid
import logging
import mimetypes
import tempfile
import asyncio
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import delete, desc as _desc
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from config import settings
from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData, CustomerReference
from utils.file_handler import save_file, delete_file
from schemas.documents import (
    DocumentUploadResponse,
    WorkflowStatusResponse,
    UpdateExtractedDataRequest,
    SplitDecisionRequest,
    ChecklistDecisionRequest,
)
import db.claim_operations as claim_db
import db.checklist_operations as checklist_db
from api.deps import ALLOWED_TYPES, get_mistral_client
from api.queue import submit_document_run, submit_library_push
from utils.rag_library import detach_document

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])

# Rendering DPI for /documents/{id}/page/{n}. High enough to stay legible when
# the viewer is zoomed in, low enough to keep the PNG small — alignment of the
# citation boxes does not depend on it either way.
PAGE_RENDER_DPI = 150

_RENDERABLE_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


async def _get_document_or_404(document_id: str) -> Document:
    """Load a document row, or raise 404 if it is missing or has no file."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")
    return doc


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    customer_id: str = Query(None, description="Optional customer ID to associate with the document"),
    claim_id: str = Query(None, description="Optional claim ID — links this document to a claim and triggers field sync after OCR"),
    doc_type: str = Query(None, description="Document type label for claim (e.g. medical_report, claim_form)"),
    auto_split: bool = Query(True, description="Detect multi-document packets and split them into one document per contained file"),
    batch_id: str = Query(None, description="Group this upload with others under one batch — the scope the Step 3.2 checklist is evaluated over. Minted per-upload when omitted."),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)

    # A lone upload is a batch of one unless the caller says it belongs with
    # others — passing the same batch_id is how a reviewer adds the documents
    # the checklist reported missing to the batch that is waiting on them.
    batch_id = batch_id or f"batch-{uuid.uuid4().hex[:12]}"

    async with AsyncSessionLocal() as session:
        # Create Document record
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            customer_id=customer_id,
            batch_id=batch_id
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        # Hand the document off for processing. Under EXECUTION_MODE=queue this
        # enqueues and returns None — the dispatcher starts the Studio run and
        # writes workflow_run_id to the row itself, so the id is not yet known
        # here. Under `inline` the run starts now and the id comes back.
        run_id = await submit_document_run(
            doc.id, doc.filename, doc.file_path, auto_split=auto_split,
        )
        if run_id:
            doc.workflow_run_id = run_id
            await session.commit()

        await submit_library_push(doc.id)

        # If this upload is part of a claim, create the link
        if claim_id:
            try:
                actual_doc_type = doc_type or "classification_pending"
                await claim_db.link_document_to_claim(
                    claim_id=claim_id,
                    document_id=doc.id,
                    doc_type=actual_doc_type
                )
                logger.info(f"Document {doc.id} linked to claim {claim_id} as '{actual_doc_type}'")
            except Exception as link_err:
                logger.warning(f"Failed to link document to claim: {link_err}")

        return DocumentUploadResponse(
            document_id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message="Upload successful, processing started.",
            workflow_run_id=run_id or "",
            batch_id=batch_id
        )


@router.post("/documents/upload/batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    customer_id: str = Query(None, description="Optional customer ID to associate with all documents in batch"),
    auto_split: bool = Query(True, description="Detect multi-document packets and split them into one document per contained file"),
    batch_id: str = Query(None, description="Reuse an existing batch instead of starting a new one — used when uploading the documents a checklist reported missing.")
):
    """
    Batch upload endpoint — accepts multiple files in a single multipart request.
    Each file gets its own DB record and Mistral workflow run.
    All files are saved and workflow-triggered concurrently via asyncio.gather.
    Returns per-file results plus a summary (total, succeeded, failed).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    MAX_BATCH_SIZE = 20
    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large. Maximum {MAX_BATCH_SIZE} files per request, got {len(files)}."
        )

    # One batch id for the whole request. It is the set the Step 3.2 checklist
    # reconciles against the configured classification types, so "uploaded
    # together" is what "did we upload everything?" means.
    batch_id = batch_id or f"batch-{uuid.uuid4().hex[:12]}"

    # Validate all file types upfront — fail fast before any IO
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for '{file.filename}': {file.content_type}"
            )

    async def _process_single(file: UploadFile) -> dict:
        """Save one file, create a DB record, and kick off a Mistral workflow."""
        try:
            file_path, file_hash = await save_file(file, settings.STORAGE_DIR)

            async with AsyncSessionLocal() as session:
                doc = Document(
                    filename=file.filename,
                    file_path=file_path,
                    file_hash=file_hash,
                    status="pending",
                    customer_id=customer_id,
                    batch_id=batch_id
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)

                run_id = await submit_document_run(
                    doc.id, doc.filename, doc.file_path, auto_split=auto_split,
                )
                if run_id:
                    doc.workflow_run_id = run_id
                    await session.commit()

                await submit_library_push(doc.id)

                return {
                    "document_id": doc.id,
                    "filename":    file.filename,
                    "status":      doc.status,
                    "workflow_run_id": run_id,
                    "batch_id":    batch_id,
                    "success":     True,
                    "error":       None,
                }

        except Exception as e:
            logger.error(f"Batch upload failed for '{file.filename}': {e}")
            return {
                "document_id":    None,
                "filename":       file.filename,
                "status":         "error",
                "workflow_run_id": None,
                "success":        False,
                "error":          str(e),
            }

    # Run all file uploads concurrently
    results = list(await asyncio.gather(*[_process_single(f) for f in files]))

    succeeded = sum(1 for r in results if r["success"])
    failed    = len(results) - succeeded

    logger.info(
        f"Batch upload done — {succeeded} succeeded, {failed} failed "
        f"out of {len(files)} files."
    )

    return {
        "total":     len(files),
        "succeeded": succeeded,
        "failed":    failed,
        "batch_id":  batch_id,
        "results":   results,
    }


# ─── Status & listing ────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/status", response_model=WorkflowStatusResponse)
async def get_status(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).options(selectinload(Document.extracted_data)).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # Treat soft-deleted documents as gone (fix #4)
        if doc.status == "deleted":
            raise HTTPException(status_code=404, detail="Document not found")

        child_count = 0
        if doc.is_split_parent:
            count_result = await session.execute(
                select(Document)
                .where(Document.parent_document_id == doc.id)
                .where(Document.status != "deleted")
            )
            child_count = len(count_result.scalars().all())

        return WorkflowStatusResponse(
            document_id=doc.id,
            workflow_run_id=doc.workflow_run_id,
            status=doc.status,
            doc_type=doc.doc_type,
            confidence_score=doc.extracted_data.confidence_score if doc.extracted_data else None,
            extracted_data=doc.extracted_data.validated_data if doc.extracted_data else None,
            message=doc.error_details.get("error", "") if doc.error_details else "",
            parent_document_id=doc.parent_document_id,
            is_split_parent=bool(doc.is_split_parent),
            page_range=doc.page_range,
            child_count=child_count,
            batch_id=doc.batch_id,
            updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
        )


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_children: bool = Query(True, description="Include documents produced by splitting a packet"),
):
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * limit
        # Exclude soft-deleted documents so they don't pollute the list (fix #4)
        query = select(Document).where(Document.status != "deleted")
        if not include_children:
            query = query.where(Document.parent_document_id.is_(None))

        result = await session.execute(
            query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        )
        docs = list(result.scalars().all())

        # One extra query for the child counts, so the UI can nest a packet and its
        # contents without an N+1 round trip per row.
        parent_ids = [d.id for d in docs if d.is_split_parent]
        child_counts: dict[str, int] = {}
        if parent_ids:
            child_rows = await session.execute(
                select(Document.parent_document_id)
                .where(Document.parent_document_id.in_(parent_ids))
                .where(Document.status != "deleted")
            )
            for (parent_id,) in child_rows.all():
                child_counts[parent_id] = child_counts.get(parent_id, 0) + 1

        return [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "doc_type": d.doc_type or d.split_doc_type_hint,
                "workflow_run_id": d.workflow_run_id,
                "message": d.error_details.get("error", "") if d.error_details else "",
                "parent_document_id": d.parent_document_id,
                "is_split_parent": bool(d.is_split_parent),
                "page_range": d.page_range,
                "child_count": child_counts.get(d.id, 0),
                "batch_id": d.batch_id,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ]


# ─── Extracted data ──────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/extracted")
async def get_extracted_data(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        if not data:
            raise HTTPException(status_code=404, detail="Extracted data not found")

        return {
            "document_id": data.document_id,
            "raw_extracted": data.raw_extracted,
            "validated_data": data.validated_data,
            "confidence_score": data.confidence_score,
            "reviewer_corrections": data.reviewer_corrections,
            "signature_verification": data.signature_verification,
            "photo_verification": data.photo_verification,
            "fraud_check": data.fraud_check,
        }


@router.put("/documents/{document_id}/extracted")
async def update_extracted_data(document_id: str, payload: UpdateExtractedDataRequest):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        if not data:
            raise HTTPException(status_code=404, detail="Extracted data not found")

        new_raw_fields = payload.raw_fields

        # Patch raw_extracted.raw_fields in-place, preserving field_confidences etc.
        raw_extracted = dict(data.raw_extracted) if data.raw_extracted else {}
        old_raw_fields = raw_extracted.get("raw_fields", {})
        raw_extracted["raw_fields"] = new_raw_fields

        # Track reviewer corrections (delta vs previous raw_fields)
        corrections = dict(data.reviewer_corrections) if data.reviewer_corrections else {}
        for k, v in new_raw_fields.items():
            if str(old_raw_fields.get(k)) != str(v):
                corrections[k] = v

        data.raw_extracted = raw_extracted
        data.reviewer_corrections = corrections

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(data, "raw_extracted")
        flag_modified(data, "reviewer_corrections")

        await session.commit()
        return {
            "success": True,
            "document_id": document_id,
            "raw_extracted": data.raw_extracted,
            "reviewer_corrections": data.reviewer_corrections,
        }


# ─── Files, OCR blocks & crops ───────────────────────────────────────────────

@router.get("/documents/{document_id}/file")
async def get_document_file(document_id: str):
    doc = await _get_document_or_404(document_id)

    mime_type, _ = mimetypes.guess_type(doc.file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Use inline disposition so the browser renders PDFs/images directly
    # instead of triggering a file download.
    # Sanitize filename for HTTP headers: replace non-ASCII chars (e.g. em
    # dash \u2014) with underscores — HTTP headers are restricted to Latin-1.
    safe_filename = doc.filename.encode('ascii', 'replace').decode('ascii').replace('?', '_')
    return FileResponse(
        doc.file_path,
        media_type=mime_type,
        filename=safe_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/documents/{document_id}/ocr-blocks")
async def get_ocr_blocks(document_id: str):
    """
    Return saved OCR bounding box blocks for field citation highlighting.
    Available for any document OCR produced spatial blocks for (images and
    PDFs alike); DOCX has no layout, and documents processed before the
    feature existed have no sidecar file.
    Returns { blocks: [...], available: false } gracefully in those cases.
    """
    blocks_path = os.path.join(
        settings.STORAGE_DIR, "ocr_blocks", f"{document_id}_blocks.json"
    )
    if not os.path.exists(blocks_path):
        return {"blocks": [], "available": False}
    try:
        with open(blocks_path, "r") as f:
            blocks = json.load(f)
        return {"blocks": blocks, "available": True}
    except Exception as e:
        logger.warning(f"Failed to read OCR blocks for document {document_id}: {e}")
        return {"blocks": [], "available": False}


@router.get("/documents/{document_id}/page-count")
async def get_document_page_count(document_id: str):
    """
    Number of pages the document can be rendered as images (see /page/{n}).
    PDFs report their real page count; anything else reports 1 so callers can
    treat every document the same way.
    """
    doc = await _get_document_or_404(document_id)
    _, ext = os.path.splitext((doc.file_path or "").lower())
    if ext != ".pdf":
        return {"page_count": 1, "renderable": ext in _RENDERABLE_IMAGE_EXTS}
    try:
        import fitz  # PyMuPDF

        with fitz.open(doc.file_path) as pdf:
            return {"page_count": pdf.page_count, "renderable": True}
    except Exception as e:
        logger.warning(f"Failed to read page count for document {document_id}: {e}")
        return {"page_count": 1, "renderable": False}


@router.get("/documents/{document_id}/page/{page_index}")
async def get_document_page_image(
    document_id: str,
    page_index: int,
    dpi: int = Query(PAGE_RENDER_DPI, ge=72, le=300),
):
    """
    Render one page of a PDF to a PNG.

    Citation highlighting draws OCR bounding boxes over the page, which the
    browser's built-in PDF embed gives no way to do — so the viewer asks for
    the page as an image and overlays the boxes on that instead. Boxes are
    scaled by the page dimensions stored alongside them, so the render DPI
    here only affects sharpness, never alignment.
    """
    doc = await _get_document_or_404(document_id)
    _, ext = os.path.splitext((doc.file_path or "").lower())
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Page rendering is only supported for PDFs")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF rendering requires PyMuPDF")

    def _render() -> bytes:
        with fitz.open(doc.file_path) as pdf:
            if page_index < 0 or page_index >= pdf.page_count:
                raise IndexError(page_index)
            return pdf[page_index].get_pixmap(dpi=dpi).tobytes("png")

    try:
        png_bytes = await asyncio.to_thread(_render)
    except IndexError:
        raise HTTPException(status_code=404, detail="Page out of range")
    except Exception as e:
        logger.error(f"Failed to render page {page_index} of document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to render page")

    return Response(
        content=png_bytes,
        media_type="image/png",
        # The rendered page is a pure function of the file and the DPI, and the
        # file never changes once uploaded.
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/documents/{document_id}/crops/{filename}")
async def get_document_crop(document_id: str, filename: str):
    """Serve cropped signature/photo images from storage/crops/{document_id}/."""
    # Sanitize filename to prevent directory traversal
    if not _re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    crop_path = os.path.join(settings.STORAGE_DIR, "crops", document_id, filename)
    if not os.path.exists(crop_path):
        raise HTTPException(status_code=404, detail="Crop file not found")

    return FileResponse(
        crop_path,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
        }
    )


# ─── Multi-document packet splitting ─────────────────────────────────────────

@router.get("/documents/{document_id}/split")
async def get_split_manifest(document_id: str):
    """
    The split outcome for a packet: the detected segments, the per-page audit
    trail, and the live state of each child document.

    404s for a document that was never split, so the caller can treat that as
    "ordinary single document".
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if not doc.is_split_parent and doc.status != "awaiting_split_review":
            raise HTTPException(status_code=404, detail="This document was not split")

        child_result = await session.execute(
            select(Document)
            .where(Document.parent_document_id == document_id)
            .where(Document.status != "deleted")
            .order_by(Document.created_at)
        )
        children = child_result.scalars().all()

        manifest = doc.split_manifest or {}
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "segments": manifest.get("segments", []),
            "pages": manifest.get("pages", []),
            "children": [
                {
                    "document_id": c.id,
                    "filename": c.filename,
                    "status": c.status,
                    "doc_type": c.doc_type or c.split_doc_type_hint,
                    "split_doc_type_hint": c.split_doc_type_hint,
                    "page_range": c.page_range,
                    "split_confidence": c.split_confidence,
                    "workflow_run_id": c.workflow_run_id,
                }
                for c in children
            ],
        }


@router.post("/documents/{document_id}/split-decision")
async def submit_split_decision(document_id: str, decision: SplitDecisionRequest):
    """
    Resume a packet paused at the split review gate.

    approved=false processes the file whole; approved=true with no segments
    accepts the detected boundaries; approved=true with segments applies the
    reviewer boundaries instead. Uses the same two-step Temporal update protocol
    as the duplicate and review resumes — see api/routers/v1/workflow.py.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.status != "awaiting_split_review":
            raise HTTPException(
                status_code=409,
                detail=f"Document is not awaiting split review (status: {doc.status})."
            )
        run_id = doc.workflow_run_id

    if not run_id or run_id == "unknown_run_id":
        raise HTTPException(status_code=409, detail="No workflow run to resume for this document.")

    try:
        client = get_mistral_client()
        query_result = await client.workflows.executions.query_workflow_execution_async(
            execution_id=run_id,
            name="__get_pending_inputs",
        )
        pending_inputs = (query_result.result or {}).get("pending_inputs", [])
        if not pending_inputs:
            raise HTTPException(status_code=409, detail="No pending inputs found. Workflow may not be paused yet.")

        await client.workflows.executions.update_workflow_execution_async(
            execution_id=run_id,
            name="__submit_input",
            input={"task_id": pending_inputs[0]["task_id"], "input": decision.model_dump()},
        )
        return {"message": "Split decision submitted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting split decision for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Batch checklist (Step 3.2) ──────────────────────────────────────────────

@router.get("/batches/{batch_id}/checklist")
async def get_batch_checklist(batch_id: str):
    """
    The checklist for one upload batch: which configured document types are
    present, which are missing, and which document supplied each.

    The lines are always reconciled **live**, against the classification types as
    they are configured right now. The stored row only supplies the things that
    cannot be recomputed — the agent's summary, the gate holder, the reviewer's
    decision. That is deliberate: an admin can add or remove a type in Settings
    while a batch sits at the gate, and replaying the snapshot taken at
    evaluation time would show the reviewer a requirement list that no longer
    exists. `stale` marks the case where the live verdict has drifted from the
    stored one, so the UI can say the batch needs re-evaluating.
    """
    from tools.checklist import build_required_types, pending_documents, reconcile

    documents = await checklist_db.get_batch_documents(batch_id)
    if not documents:
        raise HTTPException(status_code=404, detail="Batch not found")

    live = reconcile(documents, build_required_types())
    pending = pending_documents(documents)
    row = await checklist_db.get_checklist(batch_id)
    stored = checklist_db.serialize(row)

    if stored:
        status = stored["status"]
        # The stored summary describes the verdict as it stood at evaluation
        # time. Once the live verdict disagrees, that prose is actively
        # misleading, so it is dropped rather than shown next to fresh numbers.
        stale = stored["complete"] != live["complete"] or _types_of(stored["missing"]) != _types_of(live["missing"])
        summary = None if stale else stored["summary"]
        source = "live" if stale else stored["source"]
    else:
        status = "pending" if pending else "unevaluated"
        stale = False
        summary = None
        source = "live"

    return {
        "batch_id": batch_id,
        "status": status,
        "complete": live["complete"],
        "overridden": bool(stored and stored["status"] == "overridden"),
        "stale": stale,
        "required": live["required"],
        "present": live["present"],
        "missing": live["missing"],
        "extra": live["extra"],
        "unclassified": live["unclassified"],
        "summary": summary,
        "source": source,
        "gate_document_id": stored["gate_document_id"] if stored else None,
        "decision_note": stored["decision_note"] if stored else None,
        "updated_at": stored["updated_at"] if stored else None,
        "documents": _batch_document_rows(documents),
        "pending_count": len(pending),
    }


def _types_of(entries) -> set:
    """The doc_type keys of a required/missing list, for comparing two verdicts."""
    return {entry.get("doc_type") for entry in (entries or [])}


def _batch_document_rows(documents) -> list[dict]:
    """The batch's contents, as the checklist UI needs to list them (the KYC form is never one)."""
    from tools.checklist import is_kyc_form

    return [
        {
            "document_id": d.id,
            "filename": d.filename,
            "status": d.status,
            "doc_type": d.doc_type or d.split_doc_type_hint,
            "is_split_parent": bool(d.is_split_parent),
        }
        for d in documents
        if not is_kyc_form(d)
    ]


@router.post("/batches/{batch_id}/checklist/evaluate")
async def evaluate_batch_checklist(batch_id: str):
    """
    Re-run the checklist for a batch and act on the result.

    This is what the reviewer's "Re-check" does. It is not cosmetic: if the batch
    now holds everything, it releases every document waiting behind the gate. It
    is also the recovery path for a batch whose last document died before ever
    reaching Step 3.2 — without it those siblings would sit on their 24h timeout.
    """
    from activities.checklist import evaluate_batch

    documents = await checklist_db.get_batch_documents(batch_id)
    if not documents:
        raise HTTPException(status_code=404, detail="Batch not found")

    if await checklist_db.is_released(batch_id):
        return {"batch_id": batch_id, "action": "already_released"}

    verdict = await evaluate_batch(batch_id)
    return {
        "batch_id": batch_id,
        "action": verdict["action"],
        "complete": verdict.get("complete", False),
        "missing": [entry["doc_type"] for entry in verdict.get("missing", [])],
        "pending": verdict.get("pending", 0),
    }


@router.post("/batches/{batch_id}/checklist-decision")
async def submit_checklist_decision(batch_id: str, decision: ChecklistDecisionRequest):
    """
    Answer for a whole batch held at the checklist gate, and resume all of it.

    The decision is batch-scoped by design: every document in the upload is
    parked behind this one gate, so releasing one and not the others would leave
    the batch half-processed against a decision that was meant to cover it.
    Idempotent — a second call on a released batch is a no-op, which also makes
    it the manual backstop if a document missed the first fan-out.
    """
    from activities.checklist import release_batch

    documents = await checklist_db.get_batch_documents(batch_id)
    if not documents:
        raise HTTPException(status_code=404, detail="Batch not found")

    held = await checklist_db.get_gate_documents(batch_id)
    if not held and not await checklist_db.get_checklist(batch_id):
        raise HTTPException(
            status_code=409,
            detail="This batch is not waiting at the checklist gate.",
        )

    try:
        result = await release_batch(
            batch_id,
            proceed=decision.proceed,
            note=decision.note or decision.rejection_reason or "",
            mode="human",
        )
    except Exception as e:
        logger.error(f"Error releasing batch {batch_id} from the checklist gate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("already_released"):
        return {"message": "Batch was already released", "resumed": 0, "batch_id": batch_id}

    return {
        "message": (
            f"Batch released — {result['resumed']} document(s) resumed."
            if decision.proceed
            else f"Batch rejected — {result['resumed']} document(s) stopped."
        ),
        "resumed": result["resumed"],
        "missed": result.get("missed", []),
        "batch_id": batch_id,
    }


# ─── Retry ───────────────────────────────────────────────────────────────────

@router.post("/documents/{document_id}/retry")
async def retry_document(document_id: str):
    """
    Start a fresh processing run for a document that failed or stalled.

    This starts a *new* Studio execution rather than resuming the old one — a
    failed run has no pending input to submit to, and Studio will not restart a
    terminated execution. The previous workflow_run_id is therefore replaced,
    which is also why the arq job key has to be unique per attempt: the default
    key is the document id, and arq would treat a second retry within
    keep_result as a duplicate and drop it.

    Rejected and split-parent documents are refused: the first is a decision,
    not a failure, and the second has children that own the work now.
    """
    doc = await _get_document_or_404(document_id)

    if doc.is_split_parent:
        raise HTTPException(
            status_code=409,
            detail="This document was split — retry the child documents instead.",
        )
    if doc.status in ("completed", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Document is not in a retryable state (status: {doc.status}).",
        )
    if doc.status in ("checklist_hold", "awaiting_checklist_review"):
        # Parked at the batch checklist on purpose, not stalled. A retry would
        # send it back to the start and out of step with its batch; it moves on
        # when the batch is released (or becomes `expired`, which is retryable).
        raise HTTPException(
            status_code=409,
            detail="Document is held at the batch checklist — add the missing documents or decide on the checklist instead.",
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        fresh = result.scalar_one_or_none()
        if fresh is None:
            raise HTTPException(status_code=404, detail="Document not found")
        fresh.status = "pending"
        fresh.error_details = None
        fresh.workflow_run_id = None
        await session.commit()
        filename, file_path = fresh.filename, fresh.file_path

    run_id = await submit_document_run(
        document_id,
        filename,
        file_path,
        auto_split=False,  # a retry re-runs this document, it does not re-split it
        job_key=f"doc-{document_id}-retry-{uuid.uuid4().hex[:8]}",
    )

    return {
        "document_id": document_id,
        "status": "pending",
        "workflow_run_id": run_id or "",
        "message": "Retry started.",
    }


# ─── Deletion ────────────────────────────────────────────────────────────────

async def _teardown_document(session, doc: Document) -> None:
    """Soft-delete one document: drop its extraction, cancel its run, remove its file."""
    doc.status = "deleted"
    await session.execute(
        delete(ExtractedData).where(ExtractedData.document_id == doc.id)
    )

    if doc.workflow_run_id and doc.workflow_run_id != "unknown_run_id":
        try:
            await get_mistral_client().workflows.executions.cancel_workflow_execution_async(
                execution_id=doc.workflow_run_id
            )
            logger.info(f"Canceled workflow run {doc.workflow_run_id} for deleted document {doc.id}")
        except Exception as e:
            logger.warning(f"Failed to cancel workflow run {doc.workflow_run_id} for deleted document {doc.id}: {e}")

    # A deleted document must stop showing up in chat answers.
    await detach_document(session, doc.id)

    if doc.file_path:
        delete_file(doc.file_path)


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Deleting a packet takes the documents found inside it with it — they have
        # no meaning on their own. Deleting one child leaves the packet alone.
        # Walked level by level, so a child that was itself split goes down too.
        children: list[Document] = []
        frontier = [document_id]
        seen = {document_id}
        while frontier:
            level_result = await session.execute(
                select(Document)
                .where(Document.parent_document_id.in_(frontier))
                .where(Document.status != "deleted")
            )
            level = [d for d in level_result.scalars().all() if d.id not in seen]
            if not level:
                break
            seen.update(d.id for d in level)
            children.extend(level)
            frontier = [d.id for d in level]

        for child in children:
            await _teardown_document(session, child)
        await _teardown_document(session, doc)

        await session.commit()

        if children:
            import shutil
            for packet_id in seen:
                split_dir = os.path.join(settings.STORAGE_DIR, "splits", packet_id)
                if os.path.isdir(split_dir):
                    shutil.rmtree(split_dir, ignore_errors=True)

        return {
            "success": True,
            "deleted_children": len(children),
            "deleted_ids": [c.id for c in children],
        }


# ─── Signature / photo verification ──────────────────────────────────────────

@router.post("/documents/{document_id}/verify-signature")
async def verify_signature(
    document_id: str,
    file: UploadFile = File(...),
    verification_type: str = Query("signature", description="'signature' or 'photo'"),
):
    """
    Compare an extracted signature/photo against a user-uploaded reference image.

    Runs the full verification pipeline:
      DINO embeddings (thread) ∥ Mistral Vision Agent (async) → Judge Agent → final verdict

    The result is persisted on the ExtractedData row for future retrieval.
    """
    if verification_type not in ("signature", "photo"):
        raise HTTPException(status_code=400, detail="verification_type must be 'signature' or 'photo'")

    # 1. Load extracted data to get the base64 crop
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        if not data:
            raise HTTPException(status_code=404, detail="Extracted data not found for this document")

        image_key = "signature_image" if verification_type == "signature" else "photo_image"

        if not data.validated_data or not data.validated_data.get(image_key):
            raise HTTPException(
                status_code=400,
                detail=f"No {verification_type} image found in extracted data. Ensure the document has been processed as a KYC document."
            )

    base64_data = data.validated_data[image_key]

    # 2. Save both images to temp files
    tmp_dir = tempfile.mkdtemp(prefix="sig_verify_")
    try:
        # Save extracted image (from base64)
        import base64 as b64mod
        doc_img_path = os.path.join(tmp_dir, f"extracted_{verification_type}.png")
        with open(doc_img_path, "wb") as f:
            f.write(b64mod.b64decode(base64_data))

        # Save uploaded reference image
        ref_img_path = os.path.join(tmp_dir, f"reference_{verification_type}.png")
        ref_content = await file.read()
        with open(ref_img_path, "wb") as f:
            f.write(ref_content)

        # 3. Run the appropriate verification pipeline
        if verification_type == "photo":
            from utils.face_verifier import run_face_verification_pipeline
            pipeline_result = await run_face_verification_pipeline(
                doc_path=doc_img_path,
                ref_path=ref_img_path,
                debug_dir=None,
            )
        else:
            from utils.signature_verifier import run_verification_pipeline
            pipeline_result = await run_verification_pipeline(
                doc_path=doc_img_path,
                ref_path=ref_img_path,
                debug_dir=None,
            )

        # 4. Persist result to database
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ExtractedData).where(ExtractedData.document_id == document_id)
            )
            data = result.scalar_one_or_none()
            if data:
                if verification_type == "signature":
                    data.signature_verification = pipeline_result
                else:
                    data.photo_verification = pipeline_result

                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(data, f"{verification_type}_verification")
                await session.commit()

        return pipeline_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signature verification failed for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─── Customer reference records ──────────────────────────────────────────────

class CustomerReferenceCreate(BaseModel):
    customer_id: str
    full_name: str | None = None
    national_id: str | None = None
    reference_signature: str | None = None  # Base64 encoded signature image
    reference_photo: str | None = None      # Base64 encoded photo image


@router.post("/customers/references")
async def register_customer_reference(ref: CustomerReferenceCreate):
    async with AsyncSessionLocal() as session:
        # Check if already exists
        existing = await session.execute(
            select(CustomerReference).where(CustomerReference.customer_id == ref.customer_id)
        )
        existing_ref = existing.scalar_one_or_none()
        if existing_ref:
            existing_ref.full_name = ref.full_name
            existing_ref.national_id = ref.national_id
            existing_ref.reference_signature = ref.reference_signature
            existing_ref.reference_photo = ref.reference_photo
            await session.commit()
            return {"status": "updated", "customer_id": ref.customer_id}
        else:
            new_ref = CustomerReference(
                customer_id=ref.customer_id,
                full_name=ref.full_name,
                national_id=ref.national_id,
                reference_signature=ref.reference_signature,
                reference_photo=ref.reference_photo
            )
            session.add(new_ref)
            await session.commit()
            return {"status": "created", "customer_id": ref.customer_id}


# ─── Cross-Document Validation ───────────────────────────────────────────────
#
# Name matching is EXACT token matching, not fuzzy: every token of the shorter
# name must have an exact (or single-initial) counterpart in the longer name.
# This replaced difflib-based fuzzy matching on branch-vm3 — typos are not
# tolerated for official IDs. Do not reintroduce a similarity ratio here.

_NAME_THRESHOLD = 0.85


def _norm_name(s: str) -> str:
    return _re.sub(r'[^a-z ]', '', (s or '').lower().strip())


def _norm_dob(s: str) -> str:
    return _re.sub(r'[^0-9]', '', s or '')


def _fuzzy_name(a: str, b: str) -> dict:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return {"result": "NOT_FOUND", "score": None, "threshold": 1.0}

    words_a = na.split()
    words_b = nb.split()

    # Identify shorter and longer word lists
    if len(words_a) <= len(words_b):
        shorter, longer = words_a, words_b
    else:
        shorter, longer = words_b, words_a

    if not shorter:
        return {"result": "MISMATCH", "score": 0.0, "threshold": 1.0}

    available_longer = list(longer)
    matched_count = 0

    for ws in shorter:
        matched_idx = -1
        for idx, wl in enumerate(available_longer):
            if ws == wl:
                matched_idx = idx
                break
            elif len(ws) == 1 and wl.startswith(ws):
                matched_idx = idx
                break
            elif len(wl) == 1 and ws.startswith(wl):
                matched_idx = idx
                break

        if matched_idx != -1:
            matched_count += 1
            available_longer.pop(matched_idx)

    all_words_matched = (matched_count == len(shorter))

    # Safeguard: if shorter name is 1 word and longer name has multiple, mismatch to prevent false positives
    # ponytail: exact token subset verification for official IDs. Typos not allowed.
    if len(shorter) == 1 and len(longer) > 1:
        is_match = False
    else:
        is_match = all_words_matched

    score = round(matched_count / len(shorter), 3)

    return {
        "result": "MATCH" if is_match else "MISMATCH",
        "score": score,
        "threshold": 1.0
    }


def _exact_dob(a: str, b: str) -> dict:
    da, db = _norm_dob(a), _norm_dob(b)
    if not da or not db:
        return {"result": "NOT_FOUND"}
    return {"result": "MATCH" if da == db else "MISMATCH"}


def _norm_address(s: str) -> str:
    # lowercase, remove punctuation except spaces, strip
    return _re.sub(r'[^a-z0-9 ]', '', (s or '').lower().strip())


def _fuzzy_address(a: str, b: str) -> dict:
    na, nb = _norm_address(a), _norm_address(b)
    if not na or not nb:
        return {"result": "NOT_FOUND", "score": None, "threshold": 0.5}

    words_a = set(na.split())
    words_b = set(nb.split())

    if not words_a or not words_b:
        return {"result": "MISMATCH", "score": 0.0, "threshold": 0.5}

    intersection = words_a.intersection(words_b)
    
    shorter = words_a if len(words_a) < len(words_b) else words_b
    score = len(intersection) / len(shorter)
    
    threshold = 0.5 # 50% overlap of words
    is_match = score >= threshold
    
    return {
        "result": "MATCH" if is_match else "MISMATCH",
        "score": round(score, 3),
        "threshold": threshold
    }


@router.get("/cross-validate/passport-dl")
async def cross_validate_passport_dl():
    """
    Cross-validates Name and DOB between the most recently completed
    Passport and Driving License documents in the system.
    """
    async with AsyncSessionLocal() as session:
        passport_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type == "passport")
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        passport_doc = passport_result.scalar_one_or_none()

        dl_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type == "driving_license")
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        dl_doc = dl_result.scalar_one_or_none()

    missing = []
    if not passport_doc:
        missing.append("passport")
    if not dl_doc:
        missing.append("driving_license")

    if missing:
        return {
            "overall": "INCOMPLETE",
            "missing": missing,
            "passport": None,
            "dl": None,
            "checks": None,
        }

    pass_data = (passport_doc.extracted_data.validated_data or {}) if passport_doc.extracted_data else {}
    dl_data = (dl_doc.extracted_data.validated_data or {}) if dl_doc.extracted_data else {}

    pass_name = (
        pass_data.get("full_name") or
        pass_data.get("full_name_english") or
        pass_data.get("name") or
        f"{pass_data.get('given_names', '')} {pass_data.get('surname', '')}".strip()
    )
    pass_dob  = pass_data.get("date_of_birth", "")
    dl_name = (
        dl_data.get("full_name_english") or
        dl_data.get("full_name") or
        dl_data.get("name") or
        f"{dl_data.get('given_names', '')} {dl_data.get('surname', '')}".strip()
    )
    dl_dob  = dl_data.get("date_of_birth", "")

    name_check = _fuzzy_name(pass_name, dl_name)
    dob_check  = _exact_dob(pass_dob, dl_dob)

    overall = (
        "PASS"
        if name_check["result"] == "MATCH" and dob_check["result"] == "MATCH"
        else "FAIL"
    )

    return {
        "overall": overall,
        "missing": [],
        "passport": {
            "document_id": passport_doc.id,
            "filename": passport_doc.filename,
            "name": pass_name,
            "dob": pass_dob,
            "uploaded_at": passport_doc.updated_at.isoformat() if passport_doc.updated_at else None,
        },
        "dl": {
            "document_id": dl_doc.id,
            "filename": dl_doc.filename,
            "name": dl_name,
            "dob": dl_dob,
            "uploaded_at": dl_doc.updated_at.isoformat() if dl_doc.updated_at else None,
        },
        "checks": {
            "name": name_check,
            "dob": dob_check,
        }
    }


@router.get("/cross-validate/address")
async def cross_validate_address():
    """
    Cross-validates Address between the most recently completed
    Utility Bill and Bank Statement documents in the system.
    """
    async with AsyncSessionLocal() as session:
        utility_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type == "utility_bill")
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        utility_doc = utility_result.scalar_one_or_none()

        bank_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type.in_(["bank_statement", "Bank_Statement"]))
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        bank_doc = bank_result.scalar_one_or_none()

    missing = []
    if not utility_doc:
        missing.append("utility_bill")
    if not bank_doc:
        missing.append("Bank_Statement")

    if missing:
        return {
            "overall": "INCOMPLETE",
            "missing": missing,
            "utility": None,
            "bank": None,
            "checks": None,
        }

    util_data = (utility_doc.extracted_data.validated_data or {}) if utility_doc.extracted_data else {}
    bank_data = (bank_doc.extracted_data.validated_data or {}) if bank_doc.extracted_data else {}

    util_addr = (
        util_data.get("billing_address") or
        util_data.get("address") or
        util_data.get("customer_address") or
        util_data.get("service_address") or
        ""
    )
    bank_addr = (
        bank_data.get("account_holder_address") or
        bank_data.get("address") or
        bank_data.get("customer_address") or
        ""
    )
    
    if type(util_addr) is dict:
        util_addr = " ".join([str(v) for v in util_addr.values() if v])
    if type(bank_addr) is dict:
        bank_addr = " ".join([str(v) for v in bank_addr.values() if v])

    addr_check = _fuzzy_address(str(util_addr), str(bank_addr))

    overall = "PASS" if addr_check["result"] == "MATCH" else "FAIL"

    return {
        "overall": overall,
        "missing": [],
        "utility": {
            "document_id": utility_doc.id,
            "filename": utility_doc.filename,
            "address": util_addr,
            "uploaded_at": utility_doc.updated_at.isoformat() if utility_doc.updated_at else None,
        },
        "bank": {
            "document_id": bank_doc.id,
            "filename": bank_doc.filename,
            "address": bank_addr,
            "uploaded_at": bank_doc.updated_at.isoformat() if bank_doc.updated_at else None,
        },
        "checks": {
            "address": addr_check,
        }
    }


@router.get("/cross-validate/latest")
async def cross_validate_latest():
    """
    Cross-validates Name and DOB between the most recently completed
    PAN Card and Aadhaar Card documents in the system.

    No customer_id required — always picks the latest of each doc type.
    Uses exact token matching for name, normalised exact match for DOB.
    """
    async with AsyncSessionLocal() as session:
        pan_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type == "pan_card")
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        pan_doc = pan_result.scalar_one_or_none()

        aad_result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.doc_type == "aadhar_card")
            .where(Document.status == "completed")
            .order_by(_desc(Document.updated_at))
            .limit(1)
        )
        aadhaar_doc = aad_result.scalar_one_or_none()

    missing = []
    if not pan_doc:
        missing.append("pan_card")
    if not aadhaar_doc:
        missing.append("aadhar_card")

    if missing:
        return {
            "overall": "INCOMPLETE",
            "missing": missing,
            "pan": None,
            "aadhaar": None,
            "checks": None,
        }

    pan_data = (pan_doc.extracted_data.validated_data or {}) if pan_doc.extracted_data else {}
    aad_data = (aadhaar_doc.extracted_data.validated_data or {}) if aadhaar_doc.extracted_data else {}

    pan_name = (
        pan_data.get("full_name") or
        pan_data.get("full_name_english") or
        pan_data.get("name") or
        ""
    )
    pan_dob  = pan_data.get("date_of_birth", "")
    aad_name = (
        aad_data.get("full_name_english") or
        aad_data.get("full_name") or
        aad_data.get("name") or
        ""
    )
    aad_dob  = aad_data.get("date_of_birth", "")

    name_check = _fuzzy_name(pan_name, aad_name)
    dob_check  = _exact_dob(pan_dob, aad_dob)

    overall = (
        "PASS"
        if name_check["result"] == "MATCH" and dob_check["result"] == "MATCH"
        else "FAIL"
    )

    return {
        "overall": overall,
        "missing": [],
        "pan": {
            "document_id": pan_doc.id,
            "filename": pan_doc.filename,
            "name": pan_name,
            "dob": pan_dob,
            "uploaded_at": pan_doc.updated_at.isoformat() if pan_doc.updated_at else None,
        },
        "aadhaar": {
            "document_id": aadhaar_doc.id,
            "filename": aadhaar_doc.filename,
            "name": aad_name,
            "dob": aad_dob,
            "uploaded_at": aadhaar_doc.updated_at.isoformat() if aadhaar_doc.updated_at else None,
        },
        "checks": {
            "name": name_check,
            "dob":  dob_check,
        },
    }


# ─── KYC Verdict ─────────────────────────────────────────────────────────────

KYC_DOC_TYPES = ["passport", "driving_license", "utility_bill", "bank_statement", "Bank_Statement"]


@router.get("/kyc-verdict")
async def kyc_verdict():
    """
    Aggregate KYC verification data and produce an LLM-powered verdict.

    Collects:
      1. Passport ↔ DL cross-validation (name + DOB)
      2. Utility ↔ Bank address cross-validation
      3. Signature verification result (from any KYC doc that has one)
      4. Photo/face verification result (from any KYC doc that has one)

    Then sends all results to Mistral LLM to produce a final KYC verdict
    with reasoning.
    """
    # ── 1. Cross-validations ────────────────────────────────────────────────
    passport_dl_result = await cross_validate_passport_dl()
    address_result = await cross_validate_address()

    # ── 2. Signature & photo verification from any KYC doc ──────────────────
    sig_verification = None
    photo_verification = None

    async with AsyncSessionLocal() as session:
        # Find the latest KYC docs that have verification results
        for doc_type in KYC_DOC_TYPES:
            if sig_verification and photo_verification:
                break

            result = await session.execute(
                select(Document)
                .options(selectinload(Document.extracted_data))
                .where(Document.doc_type == doc_type)
                .where(Document.status == "completed")
                .order_by(_desc(Document.updated_at))
                .limit(5)
            )
            docs = result.scalars().all()

            for doc in docs:
                if not doc.extracted_data:
                    continue
                if not sig_verification and doc.extracted_data.signature_verification:
                    sv = doc.extracted_data.signature_verification
                    if sv.get("verdict"):
                        sig_verification = {
                            "document_id": doc.id,
                            "filename": doc.filename,
                            "doc_type": doc.doc_type,
                            **sv,
                        }
                if not photo_verification and doc.extracted_data.photo_verification:
                    pv = doc.extracted_data.photo_verification
                    if pv.get("verdict"):
                        photo_verification = {
                            "document_id": doc.id,
                            "filename": doc.filename,
                            "doc_type": doc.doc_type,
                            **pv,
                        }

    # ── 3. Build LLM prompt ─────────────────────────────────────────────────
    checks_summary = []

    # Passport ↔ DL
    if passport_dl_result.get("overall") == "PASS":
        checks_summary.append("Passport ↔ Driving License cross-validation: PASS (Name and DOB match)")
    elif passport_dl_result.get("overall") == "FAIL":
        details = []
        checks = passport_dl_result.get("checks", {})
        if checks.get("name", {}).get("result") == "MISMATCH":
            details.append(f"Name mismatch: Passport='{passport_dl_result.get('passport', {}).get('name', 'N/A')}' vs DL='{passport_dl_result.get('dl', {}).get('name', 'N/A')}'")
        if checks.get("dob", {}).get("result") == "MISMATCH":
            details.append(f"DOB mismatch: Passport='{passport_dl_result.get('passport', {}).get('dob', 'N/A')}' vs DL='{passport_dl_result.get('dl', {}).get('dob', 'N/A')}'")
        checks_summary.append(f"Passport ↔ Driving License cross-validation: FAIL ({'; '.join(details)})")
    else:
        missing = passport_dl_result.get("missing", [])
        checks_summary.append(f"Passport ↔ Driving License cross-validation: INCOMPLETE (missing: {', '.join(missing)})")

    # Address
    if address_result.get("overall") == "PASS":
        checks_summary.append("Utility Bill ↔ Bank Statement address cross-validation: PASS (Addresses match)")
    elif address_result.get("overall") == "FAIL":
        addr_score = address_result.get("checks", {}).get("address", {}).get("score")
        checks_summary.append(f"Utility Bill ↔ Bank Statement address cross-validation: FAIL (similarity score: {addr_score})")
    else:
        missing = address_result.get("missing", [])
        checks_summary.append(f"Utility Bill ↔ Bank Statement address cross-validation: INCOMPLETE (missing: {', '.join(missing)})")

    # Signature
    if sig_verification:
        verdict = sig_verification.get("verdict", "unknown")
        confidence = sig_verification.get("judge", {}).get("confidence") or sig_verification.get("confidence", "N/A")
        checks_summary.append(f"Signature verification: {verdict.upper()} (confidence: {confidence}%, document: {sig_verification.get('filename', 'N/A')})")
    else:
        checks_summary.append("Signature verification: NOT PERFORMED (no document has been verified yet)")

    # Photo
    if photo_verification:
        verdict = photo_verification.get("verdict", "unknown")
        verdict_label = photo_verification.get("verdict_label", verdict.upper())
        output_code = photo_verification.get("output_code", "N/A")
        checks_summary.append(f"Photo/face verification: {verdict_label} (score: {output_code}/5, document: {photo_verification.get('filename', 'N/A')})")
    else:
        checks_summary.append("Photo/face verification: NOT PERFORMED (no document has been verified yet)")

    checks_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(checks_summary))

    prompt = f"""You are a KYC compliance officer AI. Based on the following verification checks, provide a final KYC verdict.

VERIFICATION RESULTS:
{checks_text}

Analyze these results and provide your verdict in the following JSON format:
{{
  "verdict": "APPROVED" or "REJECTED" or "NEEDS_REVIEW",
  "confidence": <number 0-100>,
  "summary": "<one-line summary of the decision>",
  "reasoning": "<detailed 2-3 sentence explanation of why this verdict was reached>",
  "risk_flags": ["<list of any risk flags or concerns, empty if none>"]
}}

Rules:
- APPROVED: All completed cross-validations pass AND at least one biometric verification (signature or photo) is genuine/same_person.
- REJECTED: Any cross-validation fails with clear mismatch OR any biometric verification shows forged/different_person.
- NEEDS_REVIEW: Some checks are incomplete/not performed, or results are uncertain/inconclusive.
- If no biometric verification has been performed at all, verdict should be NEEDS_REVIEW regardless of cross-validation results.
- Be specific in your reasoning about which checks passed and which failed."""

    # ── 4. LLM call ─────────────────────────────────────────────────────────
    try:
        client = get_mistral_client()
        response = client.chat.complete(
            model=settings.LLM_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=500,
        )
        # Reasoning models return content as [ThinkChunk, TextChunk], not a str.
        from platform_core.agent_loop import _parse_json_response
        llm_response = _parse_json_response(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"KYC verdict LLM call failed: {e}")
        # Fallback: compute verdict without LLM
        llm_response = _compute_fallback_verdict(
            passport_dl_result, address_result, sig_verification, photo_verification
        )

    return {
        "verdict": llm_response.get("verdict", "NEEDS_REVIEW"),
        "confidence": llm_response.get("confidence", 0),
        "summary": llm_response.get("summary", ""),
        "reasoning": llm_response.get("reasoning", ""),
        "risk_flags": llm_response.get("risk_flags", []),
        "checks": {
            "passport_dl": passport_dl_result,
            "address": address_result,
            "signature": sig_verification,
            "photo": photo_verification,
        },
    }


def _compute_fallback_verdict(passport_dl, address, sig, photo):
    """Rule-based fallback when the LLM call fails."""
    has_fail = False
    has_incomplete = False
    has_biometric = False

    for cv in [passport_dl, address]:
        o = cv.get("overall", "INCOMPLETE")
        if o == "FAIL":
            has_fail = True
        elif o != "PASS":
            has_incomplete = True

    if sig:
        v = (sig.get("verdict") or "").lower()
        has_biometric = True
        if v == "forged":
            has_fail = True
    if photo:
        v = (photo.get("verdict") or "").lower()
        has_biometric = True
        if v == "different_person":
            has_fail = True

    if has_fail:
        verdict = "REJECTED"
        summary = "One or more KYC checks failed."
    elif not has_biometric or has_incomplete:
        verdict = "NEEDS_REVIEW"
        summary = "Some KYC checks are incomplete or biometric verification is missing."
    else:
        verdict = "APPROVED"
        summary = "All KYC checks passed."

    return {
        "verdict": verdict,
        "confidence": 50 if verdict == "NEEDS_REVIEW" else 85,
        "summary": summary,
        "reasoning": "Computed by rule-based fallback (LLM unavailable).",
        "risk_flags": [],
    }

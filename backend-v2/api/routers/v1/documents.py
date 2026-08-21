"""
Documents Router
================
Document upload, status, retrieval, extracted-data editing, KYC crops,
signature/photo verification, customer references, and cross-document
validation.

Every endpoint here was moved verbatim out of branch-vm3's monolithic
main.py. Paths, query parameters, response models and response *shapes* are
unchanged — the frontend calls these exact paths through nginx, which strips
the `/api` prefix. The router therefore declares no prefix of its own; main.py
mounts it twice (at the root and under /api/v1).
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

@router.post("/upload", response_model=DocumentUploadResponse)
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

        # Trigger Workflow asynchronously using mistralai SDK
        # We start the workflow by its registered name
        run_response = await get_mistral_client().workflows.execute_workflow_async(
            workflow_identifier="document_processing_workflow",
            input={
                "document_id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "auto_split": auto_split
            }
        )

        # run_response.execution_id contains the Mistral workflow execution ID
        run_id = run_response.execution_id if hasattr(run_response, "execution_id") else "unknown_run_id"

        doc.workflow_run_id = run_id
        await session.commit()

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
            message="Upload successful, workflow started.",
            workflow_run_id=run_id,
            batch_id=batch_id
        )


@router.post("/upload/batch")
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

                run_response = await get_mistral_client().workflows.execute_workflow_async(
                    workflow_identifier="document_processing_workflow",
                    input={
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_path": doc.file_path,
                        "auto_split": auto_split
                    }
                )

                run_id = (
                    run_response.execution_id
                    if hasattr(run_response, "execution_id")
                    else "unknown_run_id"
                )
                doc.workflow_run_id = run_id
                await session.commit()

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

@router.get("/status/{document_id}", response_model=WorkflowStatusResponse)
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
    """The batch's contents, as the checklist UI needs to list them."""
    return [
        {
            "document_id": d.id,
            "filename": d.filename,
            "status": d.status,
            "doc_type": d.doc_type or d.split_doc_type_hint,
            "is_split_parent": bool(d.is_split_parent),
        }
        for d in documents
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

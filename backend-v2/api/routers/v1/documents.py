"""
Document Routes (v1)
====================
Handles document upload, status, extraction, retry, delete, and file serving.
Split from the monolithic main.py for API versioning and maintainability.
"""

import os
import asyncio
import logging
import mimetypes
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from config import settings
from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData
from utils.file_handler import save_file
from schemas.documents import (
    DocumentUploadResponse,
    WorkflowStatusResponse,
    UpdateExtractedDataRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    customer_id: str = Query(None, description="Optional customer ID"),
    claim_id: str = Query(None, description="Optional claim ID"),
    doc_type: str = Query(None, description="Document type label for claim"),
):
    """Upload a single document and start processing pipeline."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)

    async with AsyncSessionLocal() as session:
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            customer_id=customer_id,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        redis_pool = getattr(request.app.state, "redis_pool", None)
        if redis_pool:
            # Enqueue to arq background worker
            await redis_pool.enqueue_job(
                "run_document_pipeline",
                document_id=doc.id,
                filename=doc.filename,
                file_path=doc.file_path,
            )
        else:
            # Start pipeline
            from platform_core.pipeline.definitions import build_document_pipeline
            from platform_core.pipeline.engine import PipelineEngine
            from platform_core.pipeline.checkpoint import CheckpointManager
            from platform_core.config import load_config
    
            config = load_config()
            pipeline = build_document_pipeline(config)
            engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
    
            # Run pipeline in background natively
            asyncio.create_task(
                engine.run(
                    pipeline=pipeline,
                    context={
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_path": doc.file_path,
                    },
                )
            )

        # If this upload is part of a claim, create the link
        if claim_id:
            try:
                import db.claim_operations as claim_db

                actual_doc_type = doc_type or "classification_pending"
                await claim_db.link_document_to_claim(
                    claim_id=claim_id,
                    document_id=doc.id,
                    doc_type=actual_doc_type,
                )
            except Exception as link_err:
                logger.warning(f"Failed to link document to claim: {link_err}")

        return DocumentUploadResponse(
            document_id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message="Upload successful, pipeline started.",
            workflow_run_id=doc.id,  # Use document ID as pipeline reference
        )


@router.post("/upload/batch")
async def upload_documents_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    customer_id: str = Query(None, description="Optional customer ID"),
):
    """Batch upload — accepts multiple files in a single request."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    MAX_BATCH_SIZE = 20
    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large. Maximum {MAX_BATCH_SIZE} files.",
        )

    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for '{file.filename}': {file.content_type}",
            )

    async def _process_single(file: UploadFile) -> dict:
        try:
            file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
            async with AsyncSessionLocal() as session:
                doc = Document(
                    filename=file.filename,
                    file_path=file_path,
                    file_hash=file_hash,
                    status="pending",
                    customer_id=customer_id,
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)

                redis_pool = getattr(request.app.state, "redis_pool", None)
                if redis_pool:
                    await redis_pool.enqueue_job(
                        "run_document_pipeline",
                        document_id=doc.id,
                        filename=doc.filename,
                        file_path=doc.file_path,
                    )
                else:
                    # Start pipeline in background natives
                    from platform_core.pipeline.definitions import build_document_pipeline
                    from platform_core.pipeline.engine import PipelineEngine
                    from platform_core.pipeline.checkpoint import CheckpointManager
                    from platform_core.config import load_config
    
                    config = load_config()
                    pipeline = build_document_pipeline(config)
                    engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
                    asyncio.create_task(
                        engine.run(
                            pipeline=pipeline,
                            context={
                                "document_id": doc.id,
                                "filename": doc.filename,
                                "file_path": doc.file_path,
                            },
                        )
                    )

                return {
                    "document_id": doc.id,
                    "filename": file.filename,
                    "status": doc.status,
                    "success": True,
                    "error": None,
                }
        except Exception as e:
            logger.error(f"Batch upload failed for '{file.filename}': {e}")
            return {
                "document_id": None,
                "filename": file.filename,
                "status": "error",
                "success": False,
                "error": str(e),
            }

    results = list(await asyncio.gather(*[_process_single(f) for f in files]))
    succeeded = sum(1 for r in results if r["success"])

    return {
        "total": len(files),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }


# ─── Status & Data ──────────────────────────────────────────────────────────

@router.get("/{document_id}/status", response_model=WorkflowStatusResponse)
async def get_status(document_id: str):
    """Get current status and extracted data for a document."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .options(selectinload(Document.extracted_data))
            .where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc or doc.status == "deleted":
            raise HTTPException(status_code=404, detail="Document not found")

        return WorkflowStatusResponse(
            document_id=doc.id,
            workflow_run_id=doc.workflow_run_id,
            status=doc.status,
            doc_type=doc.doc_type,
            confidence_score=doc.extracted_data.confidence_score if doc.extracted_data else None,
            extracted_data=doc.extracted_data.validated_data if doc.extracted_data else None,
            message=doc.error_details.get("error", "") if doc.error_details else "",
        )


@router.get("")
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List all documents with pagination."""
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * limit
        result = await session.execute(
            select(Document)
            .where(Document.status != "deleted")
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        docs = result.scalars().all()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "doc_type": d.doc_type,
                "workflow_run_id": d.workflow_run_id,
                "message": d.error_details.get("error", "") if d.error_details else "",
            }
            for d in docs
        ]


@router.get("/{document_id}/extracted")
async def get_extracted_data(document_id: str):
    """Get extracted and validated data for a document."""
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


@router.put("/{document_id}/extracted")
async def update_extracted_data(document_id: str, payload: UpdateExtractedDataRequest):
    """Update validated data with corrections."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        if not data:
            raise HTTPException(status_code=404, detail="Extracted data not found")

        old_data = data.validated_data or {}
        new_data = payload.validated_data

        corrections = dict(data.reviewer_corrections) if data.reviewer_corrections else {}
        for k, v in new_data.items():
            if str(old_data.get(k)) != str(v):
                corrections[k] = v

        data.validated_data = new_data
        data.reviewer_corrections = corrections

        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(data, "validated_data")
        flag_modified(data, "reviewer_corrections")

        await session.commit()
        return {
            "success": True,
            "document_id": document_id,
            "validated_data": data.validated_data,
            "reviewer_corrections": data.reviewer_corrections,
        }


# ─── File Serving ────────────────────────────────────────────────────────────

@router.get("/{document_id}/file")
async def get_document_file(document_id: str):
    """Serve the original document file."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if not doc.file_path or not os.path.exists(doc.file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")

        mime_type, _ = mimetypes.guess_type(doc.file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        headers = {
            "Content-Disposition": f'inline; filename="{doc.filename}"',
            "Cache-Control": "no-cache",
        }
        return FileResponse(doc.file_path, media_type=mime_type, headers=headers)


@router.get("/{document_id}/ocr-blocks")
async def get_ocr_blocks(document_id: str):
    """Get OCR bounding blocks for citation highlighting."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        if not data:
            raise HTTPException(status_code=404, detail="Extracted data not found")

        return {
            "document_id": document_id,
            "blocks": data.ocr_blocks or [],
        }


# ─── Retry & Delete ─────────────────────────────────────────────────────────

@router.post("/{document_id}/retry")
async def retry_document(request: Request, document_id: str):
    """Retry a failed document processing pipeline."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.status not in ("failed", "rejected", "error"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot retry document in '{doc.status}' state",
            )

        doc.status = "pending"
        doc.error_details = None
        await session.commit()

        redis_pool = getattr(request.app.state, "redis_pool", None)
        if redis_pool:
            await redis_pool.enqueue_job(
                "run_document_pipeline",
                document_id=doc.id,
                filename=doc.filename,
                file_path=doc.file_path,
            )
        else:
            # Re-run pipeline natively
            from platform_core.pipeline.definitions import build_document_pipeline
            from platform_core.pipeline.engine import PipelineEngine
            from platform_core.pipeline.checkpoint import CheckpointManager
            from platform_core.config import load_config
    
            config = load_config()
            pipeline = build_document_pipeline(config)
            engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
            asyncio.create_task(
                engine.run(
                    pipeline=pipeline,
                    context={
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_path": doc.file_path,
                    },
                )
            )

        return {"message": f"Document {document_id} queued for retry"}


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Soft-delete a document."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        doc.status = "deleted"
        await session.commit()
        return {"message": f"Document {document_id} deleted"}

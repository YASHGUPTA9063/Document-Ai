"""
batch_routes.py
───────────────
FastAPI APIRouter exposing endpoints for the Multi-Document Mistral Batch Workflow:
- POST /api/batch/upload: Upload multiple files or a zip / directory and run the batch workflow.
- POST /api/batch/folder: Run batch workflow on an existing server folder.
- GET  /api/batch/status/{batch_id}: Get live status of all documents in the batch.
"""
import os
import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from sqlalchemy.future import select

from config import settings
from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData, ClaimDocumentLink
from utils.file_handler import save_file
from batch_workflow import BatchDocumentProcessingWorkflow
import mistralai.workflows as workflows
from mistralai.client import Mistral

logger = logging.getLogger(__name__)
batch_router = APIRouter(prefix="/batch", tags=["Batch Processing"])
mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)

ALLOWED_BATCH_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/tiff",
}

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}


class BatchResponse(BaseModel):
    batch_id: str
    total: int
    succeeded: int
    failed: int
    results: List[dict]
    message: str


class BatchFolderRequest(BaseModel):
    folder_path: str
    customer_id: Optional[str] = None
    claim_id: Optional[str] = None


@batch_router.post("/upload")
async def upload_batch_files(
    files: List[UploadFile] = File(...),
    customer_id: Optional[str] = Query(None, description="Optional customer ID"),
    claim_id: Optional[str] = Query(None, description="Optional claim ID to link documents to"),
):
    """
    Accepts multiple documents (PDFs / Images) and starts the unified Mistral Batch API Workflow.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    batch_id = f"batch-{uuid.uuid4().hex[:10]}"
    doc_items = []
    created_docs_info = []

    async with AsyncSessionLocal() as session:
        for file in files:
            ext = os.path.splitext(file.filename.lower())[1]
            if ext not in SUPPORTED_EXTENSIONS and file.content_type not in ALLOWED_BATCH_TYPES:
                logger.warning(f"Skipping unsupported batch file: {file.filename}")
                continue

            file_path, file_hash = await save_file(file, settings.STORAGE_DIR)

            doc = Document(
                filename=file.filename,
                file_path=file_path,
                file_hash=file_hash,
                status="pending_batch",
                customer_id=customer_id
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            created_docs_info.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "status": "pending_batch",
                "success": True,
            })
            doc_items.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "customer_id": customer_id,
                "claim_id": claim_id
            })

            if claim_id:
                link = ClaimDocumentLink(
                    claim_id=claim_id,
                    document_id=doc.id,
                    doc_type="classification_pending",
                    synced="pending"
                )
                session.add(link)

        await session.commit()

    if not doc_items:
        raise HTTPException(status_code=400, detail="No valid PDF or Image files found in upload.")

    # Trigger Mistral Batch Workflow
    logger.info(f"Starting batch workflow for {len(doc_items)} documents (Batch ID: {batch_id})")
    try:
        run_response = await mistral_client.workflows.execute_workflow_async(
            workflow_identifier="batch_document_processing_workflow",
            input={
                "batch_id": batch_id,
                "documents": doc_items
            }
        )
        workflow_run_id = getattr(run_response, "execution_id", batch_id)
    except Exception as e:
        logger.warning(f"Could not trigger via SDK execute_workflow_async ({e}), starting in background task")
        # Direct background execution fallback if worker is running locally
        workflow_instance = BatchDocumentProcessingWorkflow()
        import asyncio
        asyncio.create_task(workflow_instance.run(batch_id=batch_id, documents=doc_items))
        workflow_run_id = batch_id

    # Update workflow_run_id for documents
    async with AsyncSessionLocal() as session:
        for item in created_docs_info:
            doc_id = item["document_id"]
            res = await session.execute(select(Document).where(Document.id == doc_id))
            d = res.scalar_one_or_none()
            if d:
                d.workflow_run_id = workflow_run_id
            item["workflow_run_id"] = workflow_run_id
        await session.commit()

    return {
        "batch_id": batch_id,
        "total": len(created_docs_info),
        "succeeded": len(created_docs_info),
        "failed": 0,
        "results": created_docs_info,
        "message": f"Batch {batch_id} initiated for {len(created_docs_info)} documents using Mistral Batch API."
    }


@batch_router.post("/folder", response_model=BatchResponse)
async def process_folder_batch(request: BatchFolderRequest):
    """
    Scans a directory on the server, ingests all valid PDF/Image documents,
    and runs the batch processing workflow.
    """
    folder = request.folder_path
    if not os.path.exists(folder) or not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail=f"Folder path does not exist or is not a directory: {folder}")

    batch_id = f"batch-folder-{uuid.uuid4().hex[:10]}"
    doc_items = []
    created_doc_ids = []

    async with AsyncSessionLocal() as session:
        for filename in sorted(os.listdir(folder)):
            file_path = os.path.join(folder, filename)
            if not os.path.isfile(file_path):
                continue

            _, ext = os.path.splitext(filename.lower())
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            doc = Document(
                filename=filename,
                file_path=file_path,
                file_hash=None,
                status="pending_batch",
                customer_id=request.customer_id
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            created_doc_ids.append(doc.id)
            doc_items.append({
                "document_id": doc.id,
                "filename": filename,
                "file_path": file_path,
                "customer_id": request.customer_id,
                "claim_id": request.claim_id
            })

            if request.claim_id:
                link = ClaimDocumentLink(
                    claim_id=request.claim_id,
                    document_id=doc.id,
                    doc_type="classification_pending",
                    synced="pending"
                )
                session.add(link)

        await session.commit()

    if not doc_items:
        raise HTTPException(status_code=400, detail=f"No supported documents found in directory '{folder}'.")

    # Start Batch Document Processing Workflow
    workflow_instance = BatchDocumentProcessingWorkflow()
    import asyncio
    asyncio.create_task(workflow_instance.run(batch_id=batch_id, documents=doc_items))

    return BatchResponse(
        batch_id=batch_id,
        total=len(created_doc_ids),
        succeeded=len(created_doc_ids),
        failed=0,
        results=[{"document_id": did, "status": "pending_batch", "success": True} for did in created_doc_ids],
        message=f"Batch {batch_id} initiated for {len(created_doc_ids)} documents from folder '{folder}'."
    )


@batch_router.get("/status/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Returns the current processing status and extraction details of all documents in a batch.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.workflow_run_id == batch_id))
        docs = result.scalars().all()

        if not docs:
            # Check by status or partial
            return {"batch_id": batch_id, "total": 0, "documents": [], "message": "No documents found for this batch ID."}

        doc_statuses = []
        for d in docs:
            ext_res = await session.execute(select(ExtractedData).where(ExtractedData.document_id == d.id))
            ext_data = ext_res.scalar_one_or_none()
            doc_statuses.append({
                "document_id": d.id,
                "filename": d.filename,
                "doc_type": d.doc_type,
                "status": d.status,
                "confidence_score": ext_data.confidence_score if ext_data else None,
                "extracted_fields": ext_data.validated_data if ext_data else None
            })

        completed = sum(1 for x in doc_statuses if x["status"] == "completed")
        awaiting = sum(1 for x in doc_statuses if x["status"] == "awaiting_review")
        processing = sum(1 for x in doc_statuses if "processing" in x["status"] or "pending" in x["status"])

        return {
            "batch_id": batch_id,
            "total_documents": len(docs),
            "completed": completed,
            "awaiting_review": awaiting,
            "in_progress": processing,
            "documents": doc_statuses
        }

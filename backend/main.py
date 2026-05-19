import os
os.environ["DEPLOYMENT_NAME"] = "document-processing-workflow"
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from config import settings
from db.database import init_db, AsyncSessionLocal
from db.models import Document, ExtractedData
from utils.file_handler import save_file, delete_file
from schemas.documents import (
    DocumentUploadResponse, 
    WorkflowStatusResponse, 
    DuplicateDecisionRequest, 
    ReviewerDecisionRequest
)
from workflow import DocumentProcessingWorkflow

import asyncio
import mistralai.workflows as workflows
from mistralai.client import Mistral

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)
worker_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Ensuring storage directory exists...")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    
    logger.info("Starting Mistral Workflow worker...")
    global worker_task
    worker_task = asyncio.create_task(workflows.run_worker([DocumentProcessingWorkflow]))
    
    yield
    
    # Shutdown
    logger.info("Shutting down Mistral Workflow worker...")
    if worker_task:
        worker_task.cancel()
        import contextlib
        with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(worker_task, timeout=2.0)

app = FastAPI(title="Mistral Document Processing POC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_TYPES = {
    "application/pdf", 
    "image/jpeg", 
    "image/png", 
    "image/webp", 
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}

@app.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    file_path = await save_file(file, settings.STORAGE_DIR)
    
    async with AsyncSessionLocal() as session:
        # Create Document record
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            status="pending"
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        
        # Trigger Workflow asynchronously using mistralai SDK
        # We start the workflow by its registered name
        run_response = await mistral_client.workflows.execute_workflow_async(
            workflow_identifier="document_processing_workflow",
            input={
                "document_id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path
            }
        )
        
        # run_response.execution_id contains the Mistral workflow execution ID
        run_id = run_response.execution_id if hasattr(run_response, "execution_id") else "unknown_run_id"
        
        doc.workflow_run_id = run_id
        await session.commit()
        
        return DocumentUploadResponse(
            document_id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message="Upload successful, workflow started.",
            workflow_run_id=run_id
        )

@app.get("/status/{document_id}", response_model=WorkflowStatusResponse)
async def get_status(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).options(selectinload(Document.extracted_data)).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return WorkflowStatusResponse(
            document_id=doc.id,
            workflow_run_id=doc.workflow_run_id,
            status=doc.status,
            doc_type=doc.doc_type,
            confidence_score=doc.extracted_data.confidence_score if doc.extracted_data else None,
            extracted_data=doc.extracted_data.validated_data if doc.extracted_data else None,
            message=doc.error_details.get("error", "") if doc.error_details else ""
        )

@app.post("/workflow/{workflow_run_id}/resume/duplicate")
async def resume_duplicate(workflow_run_id: str, decision: DuplicateDecisionRequest):
    """
    Resume a workflow paused at wait_for_input (duplicate check).
    The Mistral InteractiveWorkflow SDK uses Temporal *Updates* (NOT signals).
    Protocol:
      1. Query '__get_pending_inputs' to get the task_id for the pending input.
      2. Call update '__submit_input' with that task_id and the user's decision payload.
    """
    try:
        # Step 1: get the pending task_id
        query_result = await mistral_client.workflows.executions.query_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__get_pending_inputs",
        )
        pending_inputs = (query_result.result or {}).get("pending_inputs", [])
        if not pending_inputs:
            raise HTTPException(status_code=409, detail="No pending inputs found. Workflow may not be paused yet.")
        task_id = pending_inputs[0]["task_id"]

        # Step 2: submit the decision
        await mistral_client.workflows.executions.update_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__submit_input",
            input={"task_id": task_id, "input": decision.model_dump()},
        )
        return {"message": "Workflow resumed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming duplicate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/{workflow_run_id}/resume/review")
async def resume_review(workflow_run_id: str, decision: ReviewerDecisionRequest):
    """
    Resume a workflow paused at wait_for_input (human review).
    Same two-step protocol: query pending inputs, then submit via update.
    """
    try:
        # Step 1: get the pending task_id
        query_result = await mistral_client.workflows.executions.query_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__get_pending_inputs",
        )
        pending_inputs = (query_result.result or {}).get("pending_inputs", [])
        if not pending_inputs:
            raise HTTPException(status_code=409, detail="No pending inputs found. Workflow may not be paused yet.")
        task_id = pending_inputs[0]["task_id"]

        # Step 2: submit the decision
        await mistral_client.workflows.executions.update_workflow_execution_async(
            execution_id=workflow_run_id,
            name="__submit_input",
            input={"task_id": task_id, "input": decision.model_dump()},
        )
        return {"message": "Workflow resumed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming review: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def list_documents(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * limit
        result = await session.execute(
            select(Document).order_by(Document.created_at.desc()).offset(offset).limit(limit)
        )
        docs = result.scalars().all()
        return [{"id": d.id, "filename": d.filename, "status": d.status, "doc_type": d.doc_type} for d in docs]

@app.get("/documents/{document_id}/extracted")
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
            "reviewer_corrections": data.reviewer_corrections
        }

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        doc.status = "deleted"
        await session.commit()
        
        if doc.file_path:
            delete_file(doc.file_path)
            
        return {"success": True}

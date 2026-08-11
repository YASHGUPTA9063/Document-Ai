import os
os.environ["DEPLOYMENT_NAME"] = "document-processing-workflow"

from utils.perf_logger import install_performance_hooks
install_performance_hooks()

import tempfile
from typing import List
import logging
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete

from config import settings
from db.database import init_db, init_claim_tables, AsyncSessionLocal
from db.models import Document, ExtractedData, CustomerReference
from utils.file_handler import save_file, delete_file
from utils.norm_config import load_normalization_config, save_normalization_config
from utils.classification_config import load_classification_config, save_classification_config
from schemas.documents import (
    DocumentUploadResponse, 
    WorkflowStatusResponse, 
    DuplicateDecisionRequest, 
    ReviewerDecisionRequest,
    UpdateExtractedDataRequest
)
from workflow import DocumentProcessingWorkflow
from claim_workflow import ClaimProcessingWorkflow
from schemas.claims import (
    CreateClaimRequest, ClaimResponse, ClaimStatusResponse,
    ClaimReportResponse, ClaimDecisionRequest
)
import db.claim_operations as claim_db

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
    await init_claim_tables()
    
    logger.info("Ensuring storage directory exists...")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    
    # Preload DINOv2 model at startup for fast signature verification
    logger.info("Preloading DINOv2 model for signature verification...")
    try:
        from utils.signature_verifier import DinoVerifier
        # Run in a background thread to prevent blocking server startup while downloading weights
        asyncio.create_task(asyncio.to_thread(DinoVerifier.preload))
    except Exception as e:
        logger.warning(f"Failed to initiate DINOv2 preload: {e}")
    
    logger.info("Starting Mistral Workflow worker...")
    global worker_task
    worker_task = asyncio.create_task(workflows.run_worker([DocumentProcessingWorkflow, ClaimProcessingWorkflow]))
    
    yield
    
    # Shutdown
    logger.info("Shutting down Mistral Workflow worker...")
    if worker_task:
        worker_task.cancel()
        import contextlib
        with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(worker_task, timeout=2.0)
    os._exit(0)

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
async def upload_document(
    file: UploadFile = File(...),
    customer_id: str = Query(None, description="Optional customer ID to associate with the document"),
    claim_id: str = Query(None, description="Optional claim ID — links this document to a claim and triggers field sync after OCR"),
    doc_type: str = Query(None, description="Document type label for claim (e.g. medical_report, claim_form)"),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
    
    async with AsyncSessionLocal() as session:
        # Create Document record
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            customer_id=customer_id
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
            workflow_run_id=run_id
        )

@app.post("/upload/batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    customer_id: str = Query(None, description="Optional customer ID to associate with all documents in batch")
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
                    customer_id=customer_id
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)

                run_response = await mistral_client.workflows.execute_workflow_async(
                    workflow_identifier="document_processing_workflow",
                    input={
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_path": doc.file_path
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
        "results":   results,
    }


@app.get("/status/{document_id}", response_model=WorkflowStatusResponse)
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
        raise HTTPException(status_code=500, detail=str(e))# ─── Pipeline metadata enrichment ────────────────────────────────────────────
# Maps each agent role to static info that Mistral's API doesn't store:
# step index, icon, accent color, and the workflow tools it runs alongside.
AGENT_PIPELINE_META = {
    "intake": {
        "step": 1,
        "role": "Document ingestion and duplicate checking",
        "emoji": "📥",
        "color": "rgba(6,192,219,0.15)",
        "border": "#06c0db",
        "pipeline_tools": ["check_document_duplicates"],
    },
    "pre_validator": {
        "step": 2,
        "role": "Document quality check",
        "emoji": "🛡️",
        "color": "rgba(6,182,212,0.15)",
        "border": "#06b6d4",
        "pipeline_tools": ["get_file_metadata"],
    },
    "preprocessing": {
        "step": 2.5,
        "role": "Document pre-processing",
        "emoji": "⚙️",
        "color": "rgba(16,185,129,0.15)",
        "border": "#10b981",
        "pipeline_tools": ["enhance_document_image"],
    },
    "classifier": {
        "step": 3,
        "role": "Document classification",
        "emoji": "🏷️",
        "color": "rgba(124,58,237,0.15)",
        "border": "#7c3aed",
        "pipeline_tools": ["get_document_text", "get_supported_document_types"],
    },
    "fraud_checker": {
        "step": 3.5,
        "role": "KYC  fraud check",
        "emoji": "🛡️",
        "color": "rgba(225,29,72,0.15)",
        "border": "#e11d48",
        "pipeline_tools": ["run_identity_proofing"],
    },
    # ── Extractor (step 4) ──────────────────
    "others_extractor": {
        "step": 4,
        "role": "Document extraction",
        "emoji": "📄",
        "color": "rgba(107,114,128,0.15)",
        "border": "#6b7280",
        "pipeline_tools": ["extract_text_from_document", "crop_kyc_images"],
    },
    # ─────────────────────────────────────────────────────────────────────────
    "validator": {
        "step": 5,
        "role": "Document validation & quality assurance",
        "emoji": "✅",
        "color": "rgba(245,158,11,0.15)",
        "border": "#f59e0b",
        "pipeline_tools": ["get_validation_schema"],
    },
    "auto_verifier": {
        "step": 5.5,
        "role": "Automated reference verification",
        "emoji": "👤",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["find_customer_reference", "verify_signature", "verify_face"],
    },
    "signature_vision_agent": {
        "step": 5.5,
        "role": "Signature visual feature analysis",
        "emoji": "🔍",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["compare_signature_features"],
    },
    "signature_judge_agent": {
        "step": 5.5,
        "role": "Signature authenticity verdict",
        "emoji": "⚖️",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["evaluate_signature_match"],
    },
    "face_morphology1_agent": {
        "step": 5.5,
        "role": "Face geometry & morphology check",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["analyze_facial_geometry"],
    },
    "face_morphology2_agent": {
        "step": 5.5,
        "role": "Face secondary features check",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["analyze_secondary_features"],
    },
    "face_age_agent": {
        "step": 5.5,
        "role": "Face age variance analysis",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["evaluate_age_variance"],
    },
    "face_judge_agent": {
        "step": 5.5,
        "role": "Face match verdict judge",
        "emoji": "⚖️",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["render_face_match_decision"],
    },
    "reviewer": {
        "step": 6,
        "role": "Human review",
        "emoji": "👤",
        "color": "rgba(240,64,96,0.15)",
        "border": "#f04060",
        "pipeline_tools": ["get_review_context"],
    },
    "output": {
        "step": 7,
        "role": "Document output persistence and export",
        "emoji": "📤",
        "color": "rgba(79,110,247,0.15)",
        "border": "#4f6ef7",
        "pipeline_tools": ["persist_final_extraction"],
    },
}

# Static agents that don't have Mistral agent IDs (they're pure workflow activities)
STATIC_AGENTS = []


@app.get("/agents")
async def list_agents():
    """
    Returns the full agent pipeline — all live Mistral agents.
    Includes the pre-validator, preprocessing, classifier, fraud checker,
    all 6 type-specific extractors, validator, auto-verifier, sub-verifiers, reviewer, and output agents.
    Each agent is fetched from the Mistral API to get its real name, description, and model.
    """
    agent_configs = [
        ("intake",                 settings.INTAKE_AGENT_ID),
        ("pre_validator",          settings.PRE_VALIDATOR_AGENT_ID),
        ("preprocessing",          settings.PREPROCESSING_AGENT_ID),
        ("classifier",             settings.CLASSIFIER_AGENT_ID),
        ("fraud_checker",          settings.FRAUD_AGENT_ID),
        ("others_extractor",       settings.GENERAL_EXTRACTOR_AGENT_ID),
        ("validator",              settings.VALIDATOR_AGENT_ID),
        ("auto_verifier",          settings.AUTO_VERIFIER_AGENT_ID),
        ("signature_vision_agent", settings.SIGNATURE_VISION_AGENT_ID),
        ("signature_judge_agent",  settings.SIGNATURE_JUDGE_AGENT_ID),
        ("face_morphology1_agent", settings.FACE_MORPHOLOGY1_AGENT_ID),
        ("face_morphology2_agent", settings.FACE_MORPHOLOGY2_AGENT_ID),
        ("face_age_agent",         settings.FACE_AGE_AGENT_ID),
        ("face_judge_agent",       settings.FACE_JUDGE_AGENT_ID),
        ("reviewer",               settings.REVIEWER_AGENT_ID),
        ("output",                 settings.OUTPUT_AGENT_ID),
    ]

    mistral_agents = []
    for key, agent_id in agent_configs:
        if not agent_id:
            continue
        meta = AGENT_PIPELINE_META[key]
        try:
            agent_data = mistral_client.beta.agents.get(agent_id=agent_id)
            # agent_data.tools is a list of tool objects; extract names safely
            tool_names = []
            if agent_data.tools:
                for t in agent_data.tools:
                    if hasattr(t, 'function') and hasattr(t.function, 'name'):
                        tool_names.append(t.function.name)
                    elif hasattr(t, 'type'):
                        tool_names.append(str(t.type))
                    else:
                        tool_names.append(str(t))
            display_name = " ".join(w.capitalize() for w in key.split("_"))
            name_mapping = {
                "intake": "Ingestion Agent",
                "pre_validator": "Quality Check Agent",
                "preprocessing": "Pre Processing Agent",
                "classifier": "Classification Agent",
                "others_extractor": "Extraction Agent",
                "validator": "Validation Agent",
                "reviewer": "Human Review Agent",
                "output": "Output Agent"
            }
            agent_default_name = name_mapping.get(key, display_name + " Agent")
            mistral_agents.append({
                "key": key,
                "name": agent_data.name or agent_default_name,
                "step": meta["step"],
                "role": meta["role"],
                "description": agent_data.description or f"Mistral-hosted agent for {display_name.lower()} tasks.",
                "emoji": meta["emoji"],
                "color": meta["color"],
                "border": meta["border"],
                "model": agent_data.model,
                "agent_id": agent_id,
                "tools": tool_names or meta["pipeline_tools"],
                "source": "mistral",
            })
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral agent '{key}' ({agent_id}): {e}")
            display_name = " ".join(w.capitalize() for w in key.split("_"))
            name_mapping = {
                "intake": "Ingestion Agent",
                "pre_validator": "Quality Check Agent",
                "preprocessing": "Pre Processing Agent",
                "classifier": "Classification Agent",
                "others_extractor": "Extraction Agent",
                "validator": "Validation Agent",
                "reviewer": "Human Review Agent",
                "output": "Output Agent"
            }
            agent_default_name = name_mapping.get(key, display_name + " Agent")
            # Graceful fallback — still show the agent with static data
            mistral_agents.append({
                "key": key,
                "name": agent_default_name,
                "step": meta["step"],
                "role": meta["role"],
                "description": f"Mistral-hosted agent for {display_name.lower()} tasks. (Metadata fetch failed)",
                "emoji": meta["emoji"],
                "color": meta["color"],
                "border": meta["border"],
                "model": "mistral-agent",
                "agent_id": agent_id,
                "tools": meta["pipeline_tools"],
                "source": "mistral_fallback",
            })

    # Merge: static agents + mistral agents, sorted by pipeline step
    all_agents = STATIC_AGENTS + mistral_agents

    all_agents.sort(key=lambda a: a["step"])
    return all_agents


@app.get("/documents")
async def list_documents(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * limit
        # Exclude soft-deleted documents so they don't pollute the list (fix #4)
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
                "message": d.error_details.get("error", "") if d.error_details else ""
            }
            for d in docs
        ]

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
            "reviewer_corrections": data.reviewer_corrections,
            "signature_verification": data.signature_verification,
            "photo_verification": data.photo_verification,
            "fraud_check": data.fraud_check,
        }


@app.put("/documents/{document_id}/extracted")
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

@app.get("/documents/{document_id}/file")
async def get_document_file(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not doc.file_path or not os.path.exists(doc.file_path):
            raise HTTPException(status_code=404, detail="Document file not found on disk")
        
        mime_type, _ = mimetypes.guess_type(doc.file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Use inline disposition so the browser renders PDFs/images directly
        # instead of triggering a file download.
        headers = {
            "Content-Disposition": f"inline; filename=\"{doc.filename}\"",
            "Cache-Control": "no-cache",
        }
        return FileResponse(doc.file_path, media_type=mime_type, headers=headers)

@app.get("/documents/{document_id}/ocr-blocks")
async def get_ocr_blocks(document_id: str):
    """
    Return saved OCR bounding box blocks for field citation highlighting.
    Only available for image documents (PNG/JPEG/WEBP) processed after this feature was added.
    Returns { blocks: [...], available: false } gracefully for PDFs, DOCX, or older documents.
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


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        doc.status = "deleted"
        
        # 1. Delete associated ExtractedData record to clean up database space
        await session.execute(
            delete(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        
        await session.commit()
        
        # 2. Cancel running workflow run in Mistral cloud scheduler
        if doc.workflow_run_id and doc.workflow_run_id != "unknown_run_id":
            try:
                await mistral_client.workflows.executions.cancel_workflow_execution_async(
                    execution_id=doc.workflow_run_id
                )
                logger.info(f"Canceled workflow run {doc.workflow_run_id} for deleted document {document_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel workflow run {doc.workflow_run_id} for deleted document {document_id}: {e}")
        
        if doc.file_path:
            delete_file(doc.file_path)
            
        return {"success": True}

import json

TEMPLATES_FILE = os.path.join(settings.STORAGE_DIR, "templates.json")

DEFAULT_TEMPLATES = {}

def load_templates():
    """Load templates, handling both old (bare list) and new ({fields, is_kyc}) formats."""
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r") as f:
                raw = json.load(f)
                # Normalize: ensure each template entry is in the new dict format
                normalized = {}
                for key, value in raw.items():
                    if isinstance(value, list):
                        # Old format: bare list of fields
                        normalized[key] = {"fields": value, "is_kyc": False}
                    elif isinstance(value, dict):
                        # New format: already has fields + is_kyc + use_vlm
                        if "fields" not in value:
                            value["fields"] = []
                        if "is_kyc" not in value:
                            value["is_kyc"] = False
                        if "use_vlm" not in value:
                            value["use_vlm"] = False
                        normalized[key] = value
                    else:
                        normalized[key] = {"fields": [], "is_kyc": False, "use_vlm": False}
                # Normalize field-level defaults: ensure every field has a weight
                for tpl in normalized.values():
                    for field in tpl.get("fields", []):
                        if "weight" not in field or field["weight"] is None:
                            field["weight"] = 80
                return normalized
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
    return DEFAULT_TEMPLATES

def save_templates_to_file(templates_data):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates_data, f, indent=2)

@app.get("/settings/normalization")
async def get_normalization_settings():
    return load_normalization_config()

@app.put("/settings/normalization")
async def update_normalization_settings(config: dict):
    save_normalization_config(config)
    return {"success": True}

@app.get("/settings/classification")
async def get_classification_settings():
    return load_classification_config()

@app.put("/settings/classification")
async def update_classification_settings(doc_types: list[str]):
    save_classification_config(doc_types)
    return {"success": True}

@app.get("/settings/vllm")
async def get_vllm_settings():
    from utils.vllm_settings import load_vllm_settings
    return load_vllm_settings()

@app.put("/settings/vllm")
async def update_vllm_settings(config: dict):
    from utils.vllm_settings import save_vllm_settings
    save_vllm_settings(config)
    return {"success": True}

@app.get("/templates")
async def get_templates():
    return load_templates()

@app.put("/templates")
async def save_templates(templates_data: dict):
    save_templates_to_file(templates_data)
    return {"success": True}

@app.delete("/templates/{template_name}")
async def delete_template(template_name: str):
    templates = load_templates()
    normalized_name = template_name.strip().lower().replace(" ", "_")
    if normalized_name in templates:
        del templates[normalized_name]
        save_templates_to_file(templates)
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

@app.post("/templates/generate")
async def generate_template_from_sample(
    template_name: str = Query(...),
    is_kyc: bool = Query(False),
    use_vlm: bool = Query(False),
    kyc_boxes: str = Query(None, description="JSON string of {signature: {x1,y1,x2,y2}, photo: {x1,y1,x2,y2}} percentages"),
    file: UploadFile = File(...)
):
    # Save the file temporarily
    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
    
    try:
        from utils.ocr import extract_with_ocr
        # Perform OCR
        ocr_result = extract_with_ocr(file_path, "unknown")
        raw_text = ocr_result.get("raw_text", "")
        
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the sample document.")
            
        # Send OCR text to Mistral LLM to generate the fields schema
        prompt = (
            f"You are a document extraction expert. Analyze the following document text extracted from a sample "
            f"'{template_name}' document. Identify the key structured fields that would be useful to extract "
            f"from this type of document (e.g. names, dates, amounts, item tables, identifiers).\n\n"
            f"Document Content:\n{raw_text}\n\n"
            f"Generate a document extraction schema as a JSON list of field configurations. "
            f"Each field in the list must be an object with the following fields:\n"
            f"- 'key': Unique field identifier in snake_case (e.g., 'invoice_date', 'total_amount'). Must only contain lowercase letters, numbers, and underscores.\n"
            f"- 'label': Human-readable label (e.g., 'Invoice Date', 'Total Amount').\n"
            f"- 'type': Data type. Must be exactly one of: 'Text', 'Number', 'Date', 'Boolean', 'Array of Text', 'Array of Objects'.\n"
            f"- 'required': Boolean indicating whether this field is essential and always expected in similar documents.\n"
            f"- 'description': Short description explaining what this field is and how it should be identified.\n\n"
            f"Output a valid JSON list of objects. Do not include any explanation or markdown formatting, just the raw JSON list."
        )
        
        response = mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        logger.info(f"Generated schema for template '{template_name}': {content}")
        
        # Parse generated fields
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "fields" in parsed:
            fields = parsed["fields"]
        elif isinstance(parsed, dict):
            # Try to find a list inside the dictionary
            fields = None
            for k, v in parsed.items():
                if isinstance(v, list):
                    fields = v
                    break
            if fields is None:
                if all(isinstance(v, dict) and 'label' in v for v in parsed.values()):
                    fields = []
                    for k, v in parsed.items():
                        fields.append({
                            "key": k,
                            "label": v.get("label", k),
                            "type": v.get("type", "Text"),
                            "required": v.get("required", False),
                            "description": v.get("description", "")
                        })
                else:
                    fields = list(parsed.values())
        else:
            fields = parsed
            
        if not isinstance(fields, list):
            raise ValueError("Invalid schema format generated by AI. Expected a list of fields.")
            
        valid_types = {"Text", "Number", "Date", "Boolean", "Array of Text", "Array of Objects"}
        validated_fields = []
        for f in fields:
            if not isinstance(f, dict) or "key" not in f or "label" not in f:
                continue
            key = str(f["key"]).strip().lower().replace(" ", "_")
            key = "".join([c for c in key if c.isalnum() or c == "_"])
            if not key:
                continue
            t = str(f.get("type", "Text")).strip()
            if t not in valid_types:
                t = "Text"
            validated_fields.append({
                "key": key,
                "label": str(f["label"]).strip(),
                "type": t,
                "required": bool(f.get("required", False)),
                "description": str(f.get("description", "")).strip()
            })
            
        if not validated_fields:
            raise ValueError("No valid fields could be parsed from the generated schema.")
            
        # If KYC, auto-append signature_image and photo_image fields
        if is_kyc:
            kyc_image_fields = [
                {
                    "key": "signature_image",
                    "label": "Signature",
                    "type": "Image",
                    "required": False,
                    "description": "Handwritten signature extracted from the KYC document."
                },
                {
                    "key": "photo_image",
                    "label": "Photo",
                    "type": "Image",
                    "required": False,
                    "description": "Cardholder photograph extracted from the KYC document."
                },
                {
                    "key": "signature_detected",
                    "label": "Signature Detected",
                    "type": "Boolean",
                    "required": False,
                    "description": "Whether a handwritten signature was found in the document."
                },
                {
                    "key": "photo_detected",
                    "label": "Photo Detected",
                    "type": "Boolean",
                    "required": False,
                    "description": "Whether a cardholder photo was found in the document."
                }
            ]
            # Remove any duplicates (in case AI already generated these)
            existing_keys = {f["key"] for f in validated_fields}
            for kf in kyc_image_fields:
                if kf["key"] not in existing_keys:
                    validated_fields.append(kf)

        # Save to templates (new format with is_kyc metadata)
        templates = load_templates()
        normalized_name = template_name.strip().lower().replace(" ", "_")
        template_entry = {
            "fields": validated_fields,
            "is_kyc": is_kyc,
            "use_vlm": use_vlm
        }

        # Parse and attach kyc_boxes if provided
        if kyc_boxes:
            try:
                parsed_boxes = json.loads(kyc_boxes)
                if isinstance(parsed_boxes, dict):
                    template_entry["kyc_boxes"] = parsed_boxes
                    logger.info(f"Saved kyc_boxes for template '{normalized_name}': {parsed_boxes}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse kyc_boxes: {e}")

        templates[normalized_name] = template_entry
        save_templates_to_file(templates)
        
        return {"success": True, "template_name": normalized_name, "fields": validated_fields, "is_kyc": is_kyc}
    except Exception as e:
        logger.error(f"Error generating template from sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup sample file
        if os.path.exists(file_path):
            delete_file(file_path)


@app.get("/documents/{document_id}/crops/{filename}")
async def get_document_crop(document_id: str, filename: str):
    """Serve cropped signature/photo images from storage/crops/{document_id}/."""
    # Sanitize filename to prevent directory traversal
    import re
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
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


@app.post("/documents/{document_id}/verify-signature")
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
        detected_key = "signature_detected" if verification_type == "signature" else "photo_detected"

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


from pydantic import BaseModel

class CustomerReferenceCreate(BaseModel):
    customer_id: str
    full_name: str | None = None
    national_id: str | None = None
    reference_signature: str | None = None  # Base64 encoded signature image
    reference_photo: str | None = None      # Base64 encoded photo image

@app.post("/customers/references")
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


# ═══════════════════════════════════════════════════════════════════════════════
# CLAIM PROCESSING ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/claims")
async def create_claim(request: CreateClaimRequest):
    """
    Create a new claim record.
    Returns the generated claim_id — the frontend uses this to link subsequent uploads.
    """
    claim = await claim_db.create_claim(
        claimant_name=request.claimant_name,
        claim_type=request.claim_type,
        policy_number=request.policy_number,
        description=request.description,
        priority=request.priority or "medium",
        amount=request.amount or 0.0,
    )
    return {
        "claim_id": claim.claim_id,
        "claimant_name": claim.claimant_name,
        "claim_type": claim.claim_type,
        "policy_number": claim.policy_id,
        "priority": claim.priority,
        "amount": claim.amount,
        "description": claim.description,
        "status": claim.status,
        "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
    }


@app.get("/claims")
async def list_claims():
    """
    Return all claims ordered by newest first.
    Each claim includes its current status and basic metadata.
    """
    claims = await claim_db.get_all_claims()
    result = []
    for c in claims:
        result.append({
            "claim_id": c.claim_id,
            "claimant_name": c.claimant_name,
            "claim_type": c.claim_type,
            "policy_number": c.policy_id,
            "priority": c.priority,
            "amount": c.amount,
            "description": c.description,
            "status": c.status,
            "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
            "workflow_run_id": c.workflow_run_id,
        })
    return result


@app.get("/claims/{claim_id}/status")
async def get_claim_status(claim_id: str):
    """
    Returns processing status and any agent results written so far.
    agent_results is populated incrementally as each agent finishes,
    so the frontend can show live reasoning without waiting for the full workflow.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    status_info = await claim_db.get_claim_extraction_status(claim_id)

    # Fetch any partial agent results written incrementally by the workflow
    from sqlalchemy.future import select as _sel
    from db.models import ClaimReport as _CR
    agent_results = {}
    async with AsyncSessionLocal() as session:
        res = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        partial_report = res.scalar_one_or_none()
        if partial_report:
            agent_results = partial_report.agent_results or {}

    return {
        "claim_id": claim_id,
        "claim_type": status_info.get("claim_type", claim.claim_type),
        "claim_status": claim.status,
        "agent_results": agent_results,
        "total_docs": status_info["total_docs"],
        "completed_docs": status_info["completed_docs"],
        "failed_docs": status_info["failed_docs"],
        "ready_to_process": status_info["ready_to_process"],
        "doc_statuses": status_info["doc_statuses"],
        "required_docs": status_info.get("required_docs", []),
        "missing_required_count": status_info.get("missing_required_count", 0),
        "all_required_completed": status_info.get("all_required_completed", False),
    }


@app.post("/claims/{claim_id}/run")
async def run_claim_workflow(claim_id: str):
    """
    Triggers the claim_processing_workflow for a given claim.
    Only allowed when claim status is 'ready'.
    """
    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Claim is not ready to process. Current status: {claim.status}"
        )

    status_info = await claim_db.get_claim_extraction_status(claim_id)
    if status_info.get("missing_required_count", 0) > 0 and claim.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run claim processing. {status_info['missing_required_count']} required document(s) are missing or pending extraction."
        )

    try:
        run_response = await mistral_client.workflows.execute_workflow_async(
            workflow_identifier="claim_processing_workflow",
            input={
                "claim_id": claim_id,
                "claimant_id": claim.claimant_id,
                "policy_id": claim.policy_id,
            }
        )
        run_id = run_response.execution_id if hasattr(run_response, "execution_id") else "unknown_run_id"

        # Save run_id and update status → processing
        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select as _sel
            from db.models import Claim as _Claim
            result = await session.execute(_sel(_Claim).where(_Claim.claim_id == claim_id))
            c = result.scalar_one_or_none()
            if c:
                c.workflow_run_id = run_id
                c.status = "processing"
                await session.commit()

        return {"claim_id": claim_id, "workflow_run_id": run_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to start claim workflow for {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/claims/{claim_id}/rerun")
async def rerun_claim_workflow(claim_id: str):
    """
    Resets a completed/approved/rejected/failed claim back to 'ready'
    and re-fires the claim_processing_workflow.
    Deletes the existing report so the workflow starts fresh.
    """
    from sqlalchemy.future import select as _sel
    from db.models import Claim as _Claim, ClaimReport as _CR

    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    async with AsyncSessionLocal() as session:
        # Delete old report so the workflow can write a fresh one
        res = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        old_report = res.scalar_one_or_none()
        if old_report:
            await session.delete(old_report)

        # Reset claim status to 'ready'
        res2 = await session.execute(_sel(_Claim).where(_Claim.claim_id == claim_id))
        c = res2.scalar_one_or_none()
        if c:
            c.status = "ready"
            c.workflow_run_id = None
        await session.commit()

    try:
        run_response = await mistral_client.workflows.execute_workflow_async(
            workflow_identifier="claim_processing_workflow",
            input={
                "claim_id": claim_id,
                "claimant_id": claim.claimant_id,
                "policy_id": claim.policy_id,
            }
        )
        run_id = run_response.execution_id if hasattr(run_response, "execution_id") else "unknown_run_id"

        async with AsyncSessionLocal() as session:
            res = await session.execute(_sel(_Claim).where(_Claim.claim_id == claim_id))
            c = res.scalar_one_or_none()
            if c:
                c.workflow_run_id = run_id
                c.status = "processing"
                await session.commit()

        return {"claim_id": claim_id, "workflow_run_id": run_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to rerun claim workflow for {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/claims/{claim_id}/report")
async def get_claim_report(claim_id: str):
    """
    Returns the final ClaimReport for a completed claim.
    Contains all 5 agent results and the suggestion paragraph.
    """
    from sqlalchemy.future import select as _sel
    from db.models import ClaimReport as _CR

    async with AsyncSessionLocal() as session:
        result = await session.execute(_sel(_CR).where(_CR.claim_id == claim_id))
        report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for claim {claim_id}. Has the workflow completed?")

    return {
        "claim_id": report.claim_id,
        "claimant_name": report.claimant_name,
        "overall_status": report.overall_status,
        "suggestion": report.suggestion,
        "agent_results": report.agent_results,
        "processed_at": report.processed_at.isoformat() if report.processed_at else None,
    }


@app.post("/claims/{claim_id}/decision")
async def submit_claim_decision(claim_id: str, request: ClaimDecisionRequest):
    """
    Records the adjuster's final decision on a claim (approve or reject).
    Updates claim status in the DB.
    """
    if request.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    claim = await claim_db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    new_status = "approved" if request.decision == "approve" else "rejected"
    await claim_db.update_claim_status(claim_id, new_status)

    logger.info(f"[Claim {claim_id}] Decision: {new_status}. Notes: {request.notes}")
    return {"claim_id": claim_id, "decision": new_status, "notes": request.notes}


@app.delete("/claims/{claim_id}")
async def delete_claim(claim_id: str):
    """
    Permanently deletes a claim and all its linked document associations.
    Does NOT delete the underlying document files from storage.
    """
    deleted = await claim_db.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return {"claim_id": claim_id, "deleted": True}

# ─── Cross-Document Validation ────────────────────────────────────────────────
import difflib
import re as _re
from sqlalchemy import desc as _desc

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


@app.get("/cross-validate/latest")
async def cross_validate_latest():
    """
    Cross-validates Name and DOB between the most recently completed
    PAN Card and Aadhaar Card documents in the system.

    No customer_id required — always picks the latest of each doc type.
    Uses fuzzy matching (difflib) for name, normalised exact match for DOB.
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

    pan_name = pan_data.get("full_name", "")
    pan_dob  = pan_data.get("date_of_birth", "")
    aad_name = aad_data.get("full_name_english", "")
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


import os
import tempfile
from typing import List
os.environ["DEPLOYMENT_NAME"] = "document-processing-workflow"
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
from db.database import init_db, AsyncSessionLocal
from db.models import Document, ExtractedData
from utils.file_handler import save_file, delete_file
from schemas.documents import (
    DocumentUploadResponse, 
    WorkflowStatusResponse, 
    DuplicateDecisionRequest, 
    ReviewerDecisionRequest,
    UpdateExtractedDataRequest
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
        
    file_path, file_hash = await save_file(file, settings.STORAGE_DIR)
    
    async with AsyncSessionLocal() as session:
        # Create Document record
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
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

@app.post("/upload/batch")
async def upload_documents_batch(files: List[UploadFile] = File(...)):
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
                    status="pending"
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
        raise HTTPException(status_code=500, detail=str(e))


# ─── Pipeline metadata enrichment ────────────────────────────────────────────
# Maps each agent role to static info that Mistral's API doesn't store:
# step index, icon, accent color, and the workflow tools it runs alongside.
AGENT_PIPELINE_META = {
    "classifier": {
        "step": 2,
        "role": "Document type identification",
        "emoji": "🏷️",
        "color": "rgba(124,58,237,0.15)",
        "border": "#7c3aed",
        "pipeline_tools": ["Mistral OCR", "Type Classifier", "Confidence Scorer"],
    },
    # ── Extractor variants (step 3, conditional on doc type) ──────────────────
    "invoice_extractor": {
        "step": 3,
        "role": "Invoice field extraction",
        "emoji": "🧾",
        "color": "rgba(16,185,129,0.15)",
        "border": "#10b981",
        "pipeline_tools": ["Mistral OCR", "Line Item Parser", "Tax Calculator"],
    },
    "contract_extractor": {
        "step": 3,
        "role": "Contract clause extraction",
        "emoji": "📝",
        "color": "rgba(20,184,166,0.15)",
        "border": "#14b8a6",
        "pipeline_tools": ["Clause Detector", "Party Extractor", "Date Parser"],
    },
    "kyc_extractor": {
        "step": 3,
        "role": "KYC identity field extraction",
        "emoji": "🪪",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "pipeline_tools": ["ID Validator", "Face Match", "Address Normalizer"],
    },
    "medical_extractor": {
        "step": 3,
        "role": "Medical record data extraction",
        "emoji": "🏥",
        "color": "rgba(239,68,68,0.15)",
        "border": "#ef4444",
        "pipeline_tools": ["ICD-10 Mapper", "Drug Name Parser", "Lab Value Extractor"],
    },
    "bank_extractor": {
        "step": 3,
        "role": "Bank statement extraction",
        "emoji": "🏦",
        "color": "rgba(234,179,8,0.15)",
        "border": "#eab308",
        "pipeline_tools": ["Transaction Parser", "Balance Checker", "IBAN Validator"],
    },
    "others_extractor": {
        "step": 3,
        "role": "Generic document extraction",
        "emoji": "📄",
        "color": "rgba(107,114,128,0.15)",
        "border": "#6b7280",
        "pipeline_tools": ["Generic OCR", "Key-Value Parser", "Layout Analyzer"],
    },
    # ─────────────────────────────────────────────────────────────────────────
    "signature_verifier": {
        "step": 3,
        "role": "Signature & photo forensic verification",
        "emoji": "🔍",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "pipeline_tools": ["DINOv2 Embeddings", "Mistral Vision Agent", "Judge Agent"],
    },
    "validator": {
        "step": 4,
        "role": "Data quality assurance",
        "emoji": "✅",
        "color": "rgba(245,158,11,0.15)",
        "border": "#f59e0b",
        "pipeline_tools": ["Math Validator", "Date Checker", "Schema Validator"],
    },
    "reviewer": {
        "step": 5,
        "role": "Human-in-the-loop review",
        "emoji": "👤",
        "color": "rgba(240,64,96,0.15)",
        "border": "#f04060",
        "pipeline_tools": ["Auto-Approver", "Human Signal Listener", "Review Logger"],
    },
}

# Static agents that don't have Mistral agent IDs (they're pure workflow activities)
STATIC_AGENTS = [
    {
        "key": "intake",
        "name": "Intake Agent",
        "step": 1,
        "role": "Entry point for all document processing",
        "description": "Validates file format, detects duplicates via SHA-256 hash, and initializes the workflow run.",
        "emoji": "📥",
        "color": "rgba(6,192,219,0.15)",
        "border": "#06c0db",
        "model": "workflow-activity",
        "agent_id": None,
        "tools": ["File Validator", "Duplicate Checker", "DB Writer"],
        "source": "workflow",
    },
    {
        "key": "signature_verifier",
        "name": "Signature Verifier Agent",
        "step": 3,
        "role": "Signature forensic verification",
        "description": "Compares extracted signatures against a reference using DINOv2 embeddings and Mistral Vision forensic analysis, then a Judge agent produces the final verdict.",
        "emoji": "🔍",
        "color": "rgba(168,85,247,0.15)",
        "border": "#a855f7",
        "model": "dinov2-small + mistral-small-latest",
        "agent_id": None,
        "tools": ["DINOv2 Embeddings", "Mistral Vision Agent", "Judge Agent"],
        "source": "workflow",
    },
    {
        "key": "face_verifier",
        "name": "Face Verifier Agent",
        "step": 3,
        "role": "Multi-agent forensic face comparison",
        "description": "Compares extracted photos against a reference using 3 parallel forensic analysis agents (morphology, age variation) and a final arbitration judge.",
        "emoji": "👤",
        "color": "rgba(59,130,246,0.15)",
        "border": "#3b82f6",
        "model": "mistral-small-latest (×4 agents)",
        "agent_id": None,
        "tools": ["Morphology Part 1", "Morphology Part 2", "Age Variation", "Face Judge"],
        "source": "workflow",
    },
    {
        "key": "output",
        "name": "Output Agent",
        "step": 6,
        "role": "Result persistence and export",
        "description": "Stores validated extracted data and reviewer corrections to the database. Marks the document as completed.",
        "emoji": "📤",
        "color": "rgba(79,110,247,0.15)",
        "border": "#4f6ef7",
        "model": "workflow-activity",
        "agent_id": None,
        "tools": ["DB Writer", "JSON Formatter", "Webhook Notifier"],
        "source": "workflow",
    },
]

@app.get("/agents")
async def list_agents():
    """
    Returns the full agent pipeline — all live Mistral agents + 2 static workflow activities.
    Includes the classifier, all 6 type-specific extractors, the validator, and the reviewer.
    Each agent is fetched from the Mistral API to get its real name, description, and model.
    """
    agent_configs = [
        ("classifier",         settings.CLASSIFIER_AGENT_ID),
        ("invoice_extractor",  settings.INVOICE_EXTRACTOR_AGENT_ID),
        ("contract_extractor", settings.CONTRACT_EXTRACTOR_AGENT_ID),
        ("kyc_extractor",      settings.KYC_EXTRACTOR_AGENT_ID),
        ("medical_extractor",  settings.MEDICAL_EXTRACTOR_AGENT_ID),
        ("bank_extractor",     settings.BANK_EXTRACTOR_AGENT_ID),
        ("others_extractor",   settings.OTHERS_EXTRACTOR_AGENT_ID),
        ("validator",          settings.VALIDATOR_AGENT_ID),
        ("reviewer",           settings.REVIEWER_AGENT_ID),
    ]

    mistral_agents = []
    for key, agent_id in agent_configs:
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
            mistral_agents.append({
                "key": key,
                "name": agent_data.name or display_name + " Agent",
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
            # Graceful fallback — still show the agent with static data
            mistral_agents.append({
                "key": key,
                "name": display_name + " Agent",
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
    
    # Append dynamic custom extractors based on templates.json
    default_keys = {"invoice", "contract", "kyc", "medical_record", "bank_record", "others"}
    templates = load_templates()
    for key in templates.keys():
        norm_key = key.lower().replace(" ", "_")
        if norm_key not in default_keys:
            display_name = " ".join(w.capitalize() for w in norm_key.split("_"))
            all_agents.append({
                "key": f"{norm_key}_extractor",
                "name": f"{display_name} Agent",
                "step": 3,
                "role": f"{display_name} field extraction",
                "description": f"Dynamic extraction agent customized for {display_name} documents.",
                "emoji": "📄",
                "color": "rgba(79,110,247,0.15)",
                "border": "#4f6ef7",
                "model": "mistral-large-latest",
                "agent_id": settings.OTHERS_EXTRACTOR_AGENT_ID,
                "tools": ["Generic OCR", "Dynamic Schema Parser"],
                "source": "mistral",
            })

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
        
        old_data = data.validated_data or {}
        new_data = payload.validated_data
        
        # Determine differences and record them as reviewer corrections
        corrections = dict(data.reviewer_corrections) if data.reviewer_corrections else {}
        for k, v in new_data.items():
            if str(old_data.get(k)) != str(v):
                corrections[k] = v
                
        data.validated_data = new_data
        data.reviewer_corrections = corrections
        
        # Set SQLAlchemy flag to track mutation on JSON columns
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(data, "validated_data")
        flag_modified(data, "reviewer_corrections")
        
        await session.commit()
        return {
            "success": True,
            "document_id": document_id,
            "validated_data": data.validated_data,
            "reviewer_corrections": data.reviewer_corrections
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
                        # New format: already has fields + is_kyc
                        if "fields" not in value:
                            value["fields"] = []
                        if "is_kyc" not in value:
                            value["is_kyc"] = False
                        normalized[key] = value
                    else:
                        normalized[key] = {"fields": [], "is_kyc": False}
                return normalized
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
    return DEFAULT_TEMPLATES

def save_templates_to_file(templates_data):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates_data, f, indent=2)

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
            "is_kyc": is_kyc
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

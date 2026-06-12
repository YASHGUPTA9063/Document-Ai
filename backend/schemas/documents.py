from pydantic import BaseModel
from typing import Optional, Dict, Any

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str
    workflow_run_id: str

class WorkflowStatusResponse(BaseModel):
    document_id: str
    workflow_run_id: Optional[str] = None
    status: str
    doc_type: Optional[str] = None
    confidence_score: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    message: str

class DuplicateDecisionRequest(BaseModel):
    override: bool

class ReviewerDecisionRequest(BaseModel):
    approved: bool
    corrections: Optional[Dict[str, Any]] = None

class UpdateExtractedDataRequest(BaseModel):
    validated_data: Dict[str, Any]


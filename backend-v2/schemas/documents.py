from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

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
    # Packet-splitting lineage. All defaulted, so the response shape is unchanged
    # for every document that was not part of a split.
    parent_document_id: Optional[str] = None
    is_split_parent: bool = False
    page_range: Optional[str] = None
    child_count: int = 0

class DuplicateDecisionRequest(BaseModel):
    override: bool

class ReviewerDecisionRequest(BaseModel):
    approved: bool
    corrections: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None

class UpdateExtractedDataRequest(BaseModel):
    raw_fields: Dict[str, Any]


class SegmentOverride(BaseModel):
    """One human-confirmed document boundary inside a packet (0-based, inclusive)."""
    doc_type: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class SplitDecisionRequest(BaseModel):
    """
    Reviewer's answer to a paused split.

    approved=False means "this is really one document" — the packet is processed
    whole. approved=True with segments=None accepts the detected boundaries as-is.
    """
    approved: bool
    segments: Optional[List[SegmentOverride]] = None


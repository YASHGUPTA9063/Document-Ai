from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str
    workflow_run_id: str
    # Upload batch this file joined — the scope of the Step 3.2 checklist.
    batch_id: Optional[str] = None

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
    # Upload batch the document belongs to — the scope the Step 3.2 checklist
    # is evaluated over. Null for documents uploaded before batches existed.
    batch_id: Optional[str] = None
    # When the row last changed. Lets the UI keep the newest of two responses
    # that cross in flight, so a status never appears to step backwards.
    updated_at: Optional[str] = None

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



class ChecklistDecisionRequest(BaseModel):
    """
    Reviewer's answer to a batch paused at the Step 3.2 checklist gate.

    proceed=True continues the pipeline even though document types are missing —
    the usual case once the reviewer has either uploaded them or established that
    they do not apply. proceed=False rejects the document holding the gate.
    """
    proceed: bool
    note: Optional[str] = None
    rejection_reason: Optional[str] = None

"""
schemas/claims.py
─────────────────
Pydantic request/response models for the Claim Processing API routes.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# ─── REQUEST MODELS ───────────────────────────────────────────────────────────

class CreateClaimRequest(BaseModel):
    claimant_name: str
    claim_type: Optional[str] = "unknown"
    policy_number: Optional[str] = "unknown"
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    amount: Optional[float] = 0.0


class ClaimDecisionRequest(BaseModel):
    decision: str          # "approve" or "reject"
    notes: Optional[str] = None


# ─── RESPONSE MODELS ──────────────────────────────────────────────────────────

class ClaimDocumentStatus(BaseModel):
    document_id: str
    doc_type: str
    filename: str
    status: str            # pending | processing | completed | failed
    extracted: bool        # True if fields were synced to claim_documents


class ClaimResponse(BaseModel):
    claim_id: str
    claimant_name: Optional[str]
    claim_type: Optional[str]
    policy_number: Optional[str]
    description: Optional[str]
    priority: Optional[str]
    amount: Optional[float]
    status: str
    submitted_at: Optional[str]
    documents: List[ClaimDocumentStatus] = []
    workflow_run_id: Optional[str] = None


class ClaimStatusResponse(BaseModel):
    claim_id: str
    status: str
    total_docs: int
    completed_docs: int
    failed_docs: int
    ready_to_process: bool   # True when all docs are completed


class ClaimReportCheckItem(BaseModel):
    name: str
    result: str            # PASS | FAIL | FLAG | ERROR
    explanation: str


class ClaimReportAgentResult(BaseModel):
    status: str
    overall_reason: Optional[str]
    checks: List[ClaimReportCheckItem] = []


class ClaimReportResponse(BaseModel):
    claim_id: str
    claimant_name: Optional[str]
    processed_at: Optional[str]
    overall_status: str    # APPROVE | REVIEW BEFORE APPROVAL | REJECT
    suggestion: Optional[str]
    agent_results: Dict[str, Any]  # keyed by agent name

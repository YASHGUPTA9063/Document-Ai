"""
schemas/kyc.py
──────────────
Pydantic request/response models for the KYC Process API routes.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


# ─── REQUEST MODELS ───────────────────────────────────────────────────────────

class CreateKycApplicationRequest(BaseModel):
    applicant_name: Optional[str] = None
    fathers_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    form_source: Optional[str] = "manual"       # "manual" | "uploaded"
    form_document_id: Optional[str] = None       # if form was uploaded via OCR


class UpdateKycFormRequest(BaseModel):
    applicant_name: Optional[str] = None
    fathers_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None


class KycDecisionRequest(BaseModel):
    decision: str          # "approve" or "reject"
    notes: Optional[str] = None


# ─── RESPONSE MODELS ──────────────────────────────────────────────────────────

class KycFieldCheck(BaseModel):
    field: str
    form_value: Optional[str] = None
    doc_value: Optional[str] = None
    result: str            # MATCH | MISMATCH | PARTIAL | NOT_FOUND
    score: Optional[float] = None


class KycResultResponse(BaseModel):
    kyc_id: str
    form_data: Optional[Dict[str, Any]] = None
    doc_data: Optional[Dict[str, Any]] = None
    field_checks: Optional[List[KycFieldCheck]] = None
    overall_status: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    processed_at: Optional[str] = None

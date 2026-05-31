from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None

class ExtractedInvoiceFields(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    bill_to: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    due_date: Optional[str] = None
    payment_terms: Optional[str] = None

class ExtractedContractFields(BaseModel):
    contract_title: Optional[str] = None
    parties: Optional[List[str]] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    governing_law: Optional[str] = None
    key_obligations: Optional[List[str]] = None
    termination_clauses: Optional[List[str]] = None
    signatures: Optional[List[str]] = None

class ExtractedKYCFields(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[str] = None
    nationality: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    id_expiry: Optional[str] = None
    address: Optional[str] = None
    issuing_authority: Optional[str] = None

class ExtractedMedicalFields(BaseModel):
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    record_date: Optional[str] = None
    provider_name: Optional[str] = None
    provider_address: Optional[str] = None
    diagnoses: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    procedures: Optional[List[str]] = None
    lab_results: Optional[List[str]] = None
    notes: Optional[str] = None

class TransactionItem(BaseModel):
    date: Optional[str] = None
    description: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None

class ExtractedBankStatementFields(BaseModel):
    account_holder: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    statement_period_start: Optional[str] = None
    statement_period_end: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    currency: Optional[str] = None
    transactions: Optional[List[TransactionItem]] = None

class ExtractedOthersFields(BaseModel):
    title: Optional[str] = None
    document_date: Optional[str] = None
    parties: Optional[List[str]] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None

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

from sqlalchemy import Column, String, Float, JSON, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import relationship, backref
import uuid
from datetime import datetime
from db.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class CustomerReference(Base):
    __tablename__ = "customer_references"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, index=True, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    national_id = Column(String, index=True, nullable=True)
    reference_signature = Column(String, nullable=True)  # base64 encoded signature image
    reference_photo = Column(String, nullable=True)      # base64 encoded photo image
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="customer")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, index=True, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, index=True, nullable=True)
    doc_type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    workflow_run_id = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer_id = Column(String, ForeignKey("customer_references.customer_id"), nullable=True)

    # ── Upload batch (Step 3.2 checklist) ──
    # Every file of one upload shares a batch_id, and a packet's split children
    # inherit their parent's. It is what gives the per-document workflow a set to
    # reconcile against the configured classification types.
    batch_id = Column(String, index=True, nullable=True)

    # ── Multi-document packet splitting (Step 1.5) ──
    # A packet upload stays here as the immutable parent (status "split"); each
    # document found inside it becomes a child row with its own file and workflow.
    parent_document_id = Column(String, ForeignKey("documents.id"), nullable=True, index=True)
    page_range = Column(String, nullable=True)           # "3-5", 1-based inclusive — children only
    split_doc_type_hint = Column(String, nullable=True)  # doc_type the splitter assigned to this segment
    split_confidence = Column(Float, nullable=True)      # lowest page confidence within the segment
    is_split_parent = Column(Boolean, nullable=False, default=False)
    split_manifest = Column(JSON, nullable=True)         # parents only: segments + per-page audit trail

    extracted_data = relationship("ExtractedData", back_populates="document", uselist=False, cascade="all, delete-orphan")
    customer = relationship("CustomerReference", back_populates="documents")
    children = relationship(
        "Document",
        backref=backref("parent", remote_side=[id]),
        foreign_keys=[parent_document_id],
    )


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, unique=True)
    raw_extracted = Column(JSON, nullable=False)
    validated_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False)
    reviewer_corrections = Column(JSON, nullable=True)
    signature_verification = Column(JSON, nullable=True)
    photo_verification = Column(JSON, nullable=True)
    fraud_check = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="extracted_data")


class BatchChecklist(Base):
    """
    One row per upload batch: which of the configured classification types were
    actually uploaded, and which are still missing.

    `batch_id` is unique — the row doubles as the mutex that decides which of the
    concurrently-running document workflows gets to perform the (LLM-backed)
    evaluation. `signature` is a fingerprint of the doc types observed at
    evaluation time, so a batch that later gains the missing documents produces a
    different signature and is re-evaluated rather than serving a stale verdict.
    """
    __tablename__ = "batch_checklists"

    id = Column(String, primary_key=True, default=generate_uuid)
    batch_id = Column(String, index=True, unique=True, nullable=False)
    signature = Column(String, nullable=False, default="")

    # evaluating | complete | incomplete | overridden | abandoned
    status = Column(String, nullable=False, default="evaluating")

    required_types = Column(JSON, nullable=False, default=list)   # [{doc_type, label}]
    present_types = Column(JSON, nullable=False, default=list)    # [{doc_type, document_ids}]
    missing_types = Column(JSON, nullable=False, default=list)     # [{doc_type, label}]
    extra_types = Column(JSON, nullable=False, default=list)       # types seen but not configured
    unclassified = Column(JSON, nullable=False, default=list)      # document_ids with no usable type

    summary = Column(Text, nullable=True)          # agent's one-paragraph verdict
    source = Column(String, nullable=True)         # "agent" | "deterministic"

    # The document whose workflow holds the human-facing gate. Every other
    # document in the batch is parked behind it and released with it.
    gate_document_id = Column(String, nullable=True)
    decision_note = Column(Text, nullable=True)

    # Has a human-facing gate ever been opened for this batch? Once it has, only
    # a reviewer releases the batch — a later auto-evaluation that happens to come
    # out complete must not yank the decision away while they are looking at it.
    gate_opened = Column(Boolean, nullable=False, default=False)

    # Release is sticky and batch-wide: every document waits for it, and a
    # document that joins the batch afterwards passes straight through rather
    # than re-gating a batch that has already moved on.
    released = Column(Boolean, nullable=False, default=False)
    release_mode = Column(String, nullable=True)   # "auto" | "human"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── CLAIM PROCESSING MODELS ───────────────────────────────────────────────────

class Claim(Base):
    """
    Represents a single insurance claim submitted for processing.
    Stores top-level metadata; detailed document field-values live in ClaimDocument.
    """
    __tablename__ = "claims"

    id = Column(String, primary_key=True, default=generate_uuid)
    claim_id = Column(String, index=True, unique=True, nullable=False)  # e.g. CLM-2026-001
    claimant_id = Column(String, index=True, nullable=False)
    policy_id = Column(String, index=True, nullable=False)
    claimant_name = Column(String, nullable=True)
    claim_type = Column(String, nullable=True)       # e.g. "Health Insurance"
    amount = Column(Float, nullable=True)            # claimed amount in INR
    priority = Column(String, nullable=True)         # low | medium | high | urgent
    description = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="creating")  # creating | extracting | ready | processing | completed | approved | rejected | failed
    workflow_run_id = Column(String, nullable=True)  # claim_processing_workflow run ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("ClaimDocument", back_populates="claim", cascade="all, delete-orphan")
    report = relationship("ClaimReport", back_populates="claim", uselist=False, cascade="all, delete-orphan")


class ClaimDocument(Base):
    """
    Stores the OCR-extracted field-value pairs for each document type within a claim.
    One row per (claim_id, doc_type) combination.
    In the POC, rows are seeded manually to simulate OCR output.
    """
    __tablename__ = "claim_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    claim_id = Column(String, ForeignKey("claims.claim_id"), nullable=False, index=True)
    doc_type = Column(String, nullable=False)  # e.g. "claim_form", "medical_report"
    fields = Column(JSON, nullable=False, default=dict)  # key-value pairs extracted by OCR
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="documents")


class ClaimantHistory(Base):
    """
    Stores prior claims submitted by a claimant.
    One row per prior claim event per claimant.
    Used by the Integrity and Litigation agents.
    """
    __tablename__ = "claimant_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    claimant_id = Column(String, index=True, nullable=False)
    prior_claim_id = Column(String, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)  # approved / rejected / pending
    created_at = Column(DateTime, default=datetime.utcnow)


class PolicyDetails(Base):
    """
    Stores insurance policy coverage details keyed by policy_id.
    Used by the Integrity agent to validate policy dates and coverage.
    """
    __tablename__ = "policy_details"

    id = Column(String, primary_key=True, default=generate_uuid)
    policy_id = Column(String, index=True, unique=True, nullable=False)
    holder_name = Column(String, nullable=True)
    coverage_type = Column(String, nullable=True)  # e.g. "comprehensive", "basic"
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    details = Column(JSON, nullable=True)  # any extra coverage metadata
    created_at = Column(DateTime, default=datetime.utcnow)


class ClaimReport(Base):
    """
    Stores the final structured report produced by the claim processing workflow.
    One report per claim. Contains all 5 agent results and the final suggestion paragraph.
    """
    __tablename__ = "claim_reports"

    id = Column(String, primary_key=True, default=generate_uuid)
    claim_id = Column(String, ForeignKey("claims.claim_id"), nullable=False, unique=True, index=True)
    claimant_name = Column(String, nullable=True)
    agent_results = Column(JSON, nullable=False, default=dict)  # dict with all 5 agent outputs
    suggestion = Column(Text, nullable=True)  # final LLM-generated suggestion paragraph
    overall_status = Column(String, nullable=True)  # PASS / FAIL / REVIEW
    processed_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="report")


class ClaimDocumentLink(Base):
    """
    Join table that maps a Document (OCR pipeline) to a Claim + doc_type.
    Created when a document is uploaded with a claim_id query param.
    When OCR completes, the extracted fields are synced to claim_documents via this link.
    """
    __tablename__ = "claim_document_links"

    id = Column(String, primary_key=True, default=generate_uuid)
    claim_id = Column(String, ForeignKey("claims.claim_id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    doc_type = Column(String, nullable=False)    # e.g. "medical_report"
    synced = Column(String, nullable=False, default="pending")  # pending | synced | failed
    created_at = Column(DateTime, default=datetime.utcnow)

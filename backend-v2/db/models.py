from sqlalchemy import Column, String, Float, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
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

    extracted_data = relationship("ExtractedData", back_populates="document", uselist=False, cascade="all, delete-orphan")
    customer = relationship("CustomerReference", back_populates="documents")


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


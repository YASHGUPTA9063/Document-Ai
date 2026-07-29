import logging
from sqlalchemy.future import select

from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData, ClaimDocumentLink

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
OUTPUT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "persist_final_extraction",
            "description": "Persists raw extracted data, validated data, reviewer corrections, OCR confidences, fraud check, and auto-verification results to the database, completing the document workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "The document ID."},
                    "doc_type": {"type": "string", "description": "The classified document type."},
                    "raw_extracted": {"type": "object", "description": "The raw extracted dictionary."},
                    "validated_data": {"type": "object", "description": "The validated data dictionary."},
                    "confidence_score": {"type": "number", "description": "Average OCR confidence."},
                    "field_confidences": {"type": "object", "description": "Individual field confidences dictionary."},
                    "fraud_check": {"type": "object", "description": "Identity proofing results dictionary."},
                    "signature_verification": {"type": "object", "description": "Signature verification results dictionary."},
                    "photo_verification": {"type": "object", "description": "Face photo verification results dictionary."},
                    "corrections": {"type": "object", "description": "Human reviewer corrections dictionary."}
                },
                "required": ["document_id", "doc_type", "raw_extracted", "validated_data", "confidence_score"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
async def persist_final_extraction(
    document_id: str, 
    doc_type: str, 
    raw_extracted: dict, 
    validated_data: dict, 
    confidence_score: float, 
    field_confidences: dict, 
    fraud_check: dict, 
    signature_verification: dict, 
    photo_verification: dict, 
    corrections: dict
) -> dict:
    """Persists document validation results to database."""
    final_data = validated_data.copy() if validated_data else {}
    if corrections:
        final_data.update(corrections)
        
    async with AsyncSessionLocal() as session:
        # Check if ExtractedData exists
        result = await session.execute(select(ExtractedData).where(ExtractedData.document_id == document_id))
        extracted_record = result.scalar_one_or_none()
        
        raw_payload = {
            "raw_fields": raw_extracted or {},
            "field_confidences": field_confidences or {}
        }
        
        if not extracted_record:
            extracted_record = ExtractedData(
                document_id=document_id,
                raw_extracted=raw_payload,
                validated_data=final_data,
                confidence_score=confidence_score,
                reviewer_corrections=corrections,
                fraud_check=fraud_check,
                signature_verification=signature_verification,
                photo_verification=photo_verification
            )
            session.add(extracted_record)
        else:
            extracted_record.validated_data = final_data
            extracted_record.confidence_score = confidence_score
            extracted_record.reviewer_corrections = corrections
            extracted_record.raw_extracted = raw_payload
            if fraud_check:
                extracted_record.fraud_check = fraud_check
            if signature_verification:
                extracted_record.signature_verification = signature_verification
            if photo_verification:
                extracted_record.photo_verification = photo_verification
            
        # Update Document status
        doc_result = await session.execute(select(Document).where(Document.id == document_id))
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.status = "completed"
            doc.doc_type = doc_type

        # Sync ClaimDocumentLink: update doc_type from 'classification_pending' → real type
        links_result = await session.execute(
            select(ClaimDocumentLink).where(ClaimDocumentLink.document_id == document_id)
        )
        for link in links_result.scalars().all():
            if link.doc_type in ("classification_pending", "", None):
                link.doc_type = doc_type
            link.synced = "synced"

        await session.commit()

    return {
        "success": True,
        "document_id": document_id,
        "final_data": final_data
    }

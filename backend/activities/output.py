import logging
import mistralai.workflows as workflows
from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

@workflows.activity()
async def output_activity(document_id: str, doc_type: str, validated_data: dict, reviewer_result: dict, confidence_score: float) -> dict:
    try:
        logger.info(f"[Document {document_id}] Starting output activity")
        
        # Merge reviewer corrections if any
        final_data = validated_data.copy()
        corrections = reviewer_result.get("corrections")
        if corrections:
            final_data.update(corrections)
            
        async with AsyncSessionLocal() as session:
            # Check if ExtractedData exists
            result = await session.execute(select(ExtractedData).where(ExtractedData.document_id == document_id))
            extracted_record = result.scalar_one_or_none()
            
            if not extracted_record:
                extracted_record = ExtractedData(
                    document_id=document_id,
                    raw_extracted={}, # Raw OCR text could be passed here if needed
                    validated_data=final_data,
                    confidence_score=confidence_score,
                    reviewer_corrections=corrections
                )
                session.add(extracted_record)
            else:
                extracted_record.validated_data = final_data
                extracted_record.confidence_score = confidence_score
                extracted_record.reviewer_corrections = corrections
                
            # Update Document
            doc_result = await session.execute(select(Document).where(Document.id == document_id))
            doc = doc_result.scalar_one_or_none()
            if doc:
                doc.status = "completed"
                doc.doc_type = doc_type
                
            await session.commit()
            
        return {
            "success": True, 
            "document_id": document_id, 
            "final_data": final_data
        }
    except Exception as e:
        logger.error(f"[Document {document_id}] Output failed: {str(e)}")
        from db.operations import update_error
        await update_error(document_id, {"error": str(e), "stage": "output"})
        raise

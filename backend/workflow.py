import logging
import mistralai.workflows as workflows
from datetime import timedelta
with workflows.workflow.unsafe.imports_passed_through():
    from activities.intake import intake_activity
    from activities.classifier import classifier_activity
    from activities.extractor import extractor_activity
    from activities.validator import validator_activity
    from activities.reviewer import reviewer_activity
    from activities.output import output_activity
    import db.operations as db
    from schemas.documents import DuplicateDecisionRequest, ReviewerDecisionRequest

logger = logging.getLogger(__name__)

@workflows.activity()
async def update_status_activity(document_id: str, status: str) -> str:
    import db.operations as db
    await db.update_status(document_id, status)
    return status

@workflows.activity()
async def update_status_and_message_activity(document_id: str, status: str, message: str) -> str:
    import db.operations as db
    await db.update_status_and_message(document_id, status, message)
    return status

@workflows.activity()
async def update_doc_type_activity(document_id: str, doc_type: str) -> str:
    import db.operations as db
    await db.update_doc_type(document_id, doc_type)
    return doc_type

@workflows.workflow.define(name="document_processing_workflow")
class DocumentProcessingWorkflow(workflows.InteractiveWorkflow):

    @workflows.workflow.entrypoint
    async def run(self, document_id: str, filename: str, file_path: str) -> dict:
        logger.info(f"Starting workflow for document {document_id}")
        
        # Step 1 — Intake
        await update_status_activity(document_id, "processing")
        intake_result = await intake_activity(document_id, filename)

        if intake_result.get("is_duplicate"):
            # Pause — wait for user duplicate override decision
            logger.info(f"[Document {document_id}] Pausing for duplicate check override")
            await update_status_and_message_activity(document_id, "awaiting_review", "Duplicate detected. Waiting for override decision.")
            duplicate_decision = await self.wait_for_input(DuplicateDecisionRequest, timeout=timedelta(hours=24))
            
            if not duplicate_decision.override:
                await update_status_and_message_activity(document_id, "rejected", "Duplicate not overridden.")
                return {"status": "rejected", "reason": "duplicate_not_overridden"}
            else:
                await update_status_and_message_activity(document_id, "processing", "")

        # Step 2 — Classify
        await update_status_activity(document_id, "classifying")
        classifier_result = await classifier_activity(document_id, file_path)
        doc_type = classifier_result["doc_type"]
        await update_doc_type_activity(document_id, doc_type)

        # Step 3 — Extract
        await update_status_activity(document_id, "extracting")
        extractor_result = await extractor_activity(document_id, file_path, doc_type)

        # Step 4 — Validate
        await update_status_activity(document_id, "validating")
        validator_result = await validator_activity(
            document_id=document_id, 
            extracted_data=extractor_result["fields"], 
            doc_type=doc_type, 
            ocr_confidence=extractor_result["confidence"],
            field_confidences=extractor_result.get("field_confidences")
        )

        # Step 5 — Review
        await update_status_activity(document_id, "awaiting_review")
        reviewer_result = await reviewer_activity(
            document_id=document_id, 
            validated_data=validator_result["validated_data"], 
            confidence_score=validator_result["confidence_score"]
        )

        if reviewer_result.get("auto_approved"):
            final_reviewer_result = {"approved": True, "corrections": None}
        else:
            logger.info(f"[Document {document_id}] Pausing for human review. Score < 80%")
            # Pause workflow using Mistral Workflow SDK Interactive Workflow primitives
            human_decision = await self.wait_for_input(ReviewerDecisionRequest, timeout=timedelta(hours=24))
            final_reviewer_result = {
                "approved": human_decision.approved,
                "corrections": human_decision.corrections
            }

        if not final_reviewer_result.get("approved"):
            await update_status_activity(document_id, "rejected")
            return {"status": "rejected", "reason": "reviewer_rejected"}

        # Step 6 — Output
        output_result = await output_activity(
            document_id=document_id, 
            doc_type=doc_type, 
            validated_data=validator_result["validated_data"], 
            reviewer_result=final_reviewer_result, 
            confidence_score=validator_result["confidence_score"],
            field_confidences=validator_result.get("field_confidences")
        )
        
        logger.info(f"Completed workflow for document {document_id}")
        return output_result

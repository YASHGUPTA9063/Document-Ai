import logging
import mistralai.workflows as workflows
from datetime import timedelta
with workflows.workflow.unsafe.imports_passed_through():
    from activities.intake import intake_activity
    from activities.preprocessor import preprocessor_activity
    from activities.classifier import classifier_activity
    from activities.extractor import extractor_activity
    from activities.validator import validator_activity
    from activities.reviewer import reviewer_activity
    from activities.output import output_activity
    from activities.pre_validator import pre_validator_activity
    from activities.fraud_checker import fraud_check_activity
    from activities.auto_verifier import auto_verify_activity
    import db.operations as db
    from schemas.documents import DuplicateDecisionRequest, ReviewerDecisionRequest
    from config import settings


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

@workflows.activity()
async def get_template_metadata_activity(doc_type: str) -> dict:
    from tools.extractor import get_template_metadata
    return get_template_metadata(doc_type)

async def _update_status(document_id: str, status: str) -> str:
    with workflows.run_activities_locally():
        return await update_status_activity(document_id, status)

async def _update_status_and_message(document_id: str, status: str, message: str) -> str:
    with workflows.run_activities_locally():
        return await update_status_and_message_activity(document_id, status, message)

async def _update_doc_type(document_id: str, doc_type: str) -> str:
    with workflows.run_activities_locally():
        return await update_doc_type_activity(document_id, doc_type)

@workflows.workflow.define(name="document_processing_workflow")
class DocumentProcessingWorkflow(workflows.InteractiveWorkflow):

    @workflows.workflow.entrypoint
    async def run(self, document_id: str, filename: str, file_path: str) -> dict:
        logger.info(f"Starting workflow for document {document_id}")

        # Step 1 — Intake
        await _update_status(document_id, "processing")
        intake_result = await intake_activity(document_id, filename)

        if intake_result.get("is_duplicate"):
            # Pause — wait for user duplicate override decision
            logger.info(f"[Document {document_id}] Pausing for duplicate check override")
            await _update_status_and_message(document_id, "awaiting_review", "Duplicate detected. Waiting for override decision.")
            duplicate_decision = await self.wait_for_input(DuplicateDecisionRequest, timeout=timedelta(hours=24))
            
            if not duplicate_decision.override:
                await _update_status_and_message(document_id, "rejected", "Duplicate not overridden.")
                return {"status": "rejected", "reason": "duplicate_not_overridden"}
            else:
                await _update_status_and_message(document_id, "processing", "")

        # Step 2 — Pre-Validation
        # Checks blur, brightness, skew, readability, watermark (warning), orientation, blank document, and password protection.
        # Skipped gracefully if PRE_VALIDATOR_AGENT_ID is not yet configured.
        if settings.PRE_VALIDATOR_AGENT_ID:
            await _update_status(document_id, "pre_validating")
            pre_val = await pre_validator_activity(document_id, file_path)
            if not pre_val.get("passed"):
                reason = pre_val.get("rejection_reason") or "Document failed pre-validation quality check."
                await _update_status_and_message(document_id, "rejected", reason)
                return {"status": "rejected", "reason": reason, "pre_validation": pre_val}
            logger.info(
                f"[Document {document_id}] Pre-validation passed. "
                f"Warnings: {pre_val.get('warnings', [])}"
            )
        else:
            logger.warning(
                f"[Document {document_id}] PRE_VALIDATOR_AGENT_ID not set — skipping pre-validation."
            )

        # Step 2.5 — Preprocessing
        # Applies skew correction, brightness/CLAHE, noise removal, resolution normalization.
        # Gated by ENABLE_PREPROCESSING flag in .env. DOCX and (by default) PDFs are skipped.
        clean_file_path = file_path  # default: pass original to downstream steps
        if settings.ENABLE_PREPROCESSING:
            await _update_status(document_id, "preprocessing")
            preprocess_result = await preprocessor_activity(document_id, file_path)
            clean_file_path = preprocess_result.get("preprocessed_path") or file_path
            logger.info(
                f"[Document {document_id}] Preprocessing complete. "
                f"Steps applied: {preprocess_result.get('applied_steps', [])}. "
                f"Skipped: {preprocess_result.get('skipped', False)}."
            )
        else:
            logger.info(f"[Document {document_id}] ENABLE_PREPROCESSING=false — skipping preprocessing step.")

        # Step 3 — Classify
        await _update_status(document_id, "classifying")
        classifier_result = await classifier_activity(document_id, clean_file_path)
        doc_type = classifier_result["doc_type"]
        await _update_doc_type(document_id, doc_type)

        # Step 3.5 — Fraud Check (if KYC Document)
        fraud_check_result = None
        template_meta = await get_template_metadata_activity(doc_type)
        is_kyc = template_meta.get("is_kyc", False) or doc_type.lower() in ("kyc", "kyc document", "identity document")
        
        if is_kyc:
            await _update_status(document_id, "fraud_checking")
            try:
                fraud_check_result = await fraud_check_activity(document_id, clean_file_path)
                if not fraud_check_result.get("passed", False):
                    reason = fraud_check_result.get("rejection_reason") or "Document failed fraud check verification."
                    await _update_status_and_message(document_id, "rejected", reason)
                    return {"status": "rejected", "reason": reason, "fraud_check": fraud_check_result}
            except Exception as e:
                logger.warning(f"[Document {document_id}] Fraud check failed (gracefully skipping): {e}")


        # Step 4 — Extract
        await _update_status(document_id, "extracting")

        extractor_result = await extractor_activity(document_id, clean_file_path, doc_type)
        raw_extracted = extractor_result.get("raw_extracted")
        vllm_fallback = extractor_result.get("vllm_fallback")

        # Step 5 — Validate
        await _update_status(document_id, "validating")
        validator_result = await validator_activity(
            document_id=document_id, 
            extracted_data=extractor_result["fields"], 
            doc_type=doc_type, 
            ocr_confidence=extractor_result["confidence"],
            field_confidences=extractor_result.get("field_confidences")
        )

        # Step 5.5 — Automated Verification (KYC documents only)
        auto_verify_result = None
        if is_kyc:
            await _update_status(document_id, "auto_verifying")
            try:
                auto_verify_result = await auto_verify_activity(
                    document_id=document_id, 
                    validated_data=validator_result["validated_data"]
                )
            except Exception as e:
                logger.error(f"[Document {document_id}] Automated verification failed: {e}")

        # Step 6 — Review
        reviewer_result = await reviewer_activity(
            document_id=document_id, 
            validated_data=validator_result["validated_data"], 
            confidence_score=validator_result["confidence_score"]
        )

        if reviewer_result.get("auto_approved"):
            final_reviewer_result = {"approved": True, "corrections": None}
        else:
            logger.info(f"[Document {document_id}] Pausing for human review. Score < 80%")
            await _update_status(document_id, "awaiting_review")
            # Pause workflow using Mistral Workflow SDK Interactive Workflow primitives
            human_decision = await self.wait_for_input(ReviewerDecisionRequest, timeout=timedelta(hours=24))
            final_reviewer_result = {
                "approved": human_decision.approved,
                "corrections": human_decision.corrections
            }

        if not final_reviewer_result.get("approved"):
            rejection_reason = human_decision.rejection_reason or "Rejected by human reviewer."
            await _update_status_and_message(document_id, "rejected", rejection_reason)
            return {"status": "rejected", "reason": rejection_reason}

        # Step 7 — Output
        output_result = await output_activity(
            document_id=document_id, 
            doc_type=doc_type, 
            validated_data=validator_result["validated_data"], 
            reviewer_result=final_reviewer_result, 
            confidence_score=validator_result["confidence_score"],
            field_confidences=validator_result.get("field_confidences"),
            fraud_check=fraud_check_result,
            raw_extracted=raw_extracted,
            vllm_fallback=vllm_fallback,
            signature_verification=auto_verify_result.get("signature") if auto_verify_result else None,
            photo_verification=auto_verify_result.get("photo") if auto_verify_result else None
        )
        
        logger.info(f"Completed workflow for document {document_id}")
        return output_result


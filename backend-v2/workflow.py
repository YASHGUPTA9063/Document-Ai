import asyncio
import logging
import mistralai.workflows as workflows
from datetime import timedelta
with workflows.workflow.unsafe.imports_passed_through():
    from activities.intake import intake_activity
    from activities.preprocessor import preprocessor_activity
    from activities.classifier import classifier_activity
    from activities.checklist import checklist_activity
    from activities.splitter import splitter_activity
    from activities.split_fanout import split_fanout_activity
    from activities.extractor import extractor_activity
    from activities.validator import validator_activity
    from activities.reviewer import reviewer_activity
    from activities.output import output_activity
    from activities.pre_validator import pre_validator_activity
    from activities.fraud_checker import fraud_check_activity
    from activities.auto_verifier import auto_verify_activity
    import db.operations as db
    from schemas.documents import (
        DuplicateDecisionRequest, ReviewerDecisionRequest, SplitDecisionRequest,
        ChecklistDecisionRequest,
    )
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
async def rebuild_segments_activity(overrides: list, total_pages: int) -> list:
    """Turn reviewer-confirmed boundaries back into segments (validates coverage)."""
    from tools.splitter import build_segments_from_overrides
    from tools.classifier import get_supported_doc_types
    segments = build_segments_from_overrides(overrides, total_pages, get_supported_doc_types())
    return [s.model_dump() for s in segments]


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

# Every human gate waits this long before giving up on a reviewer.
GATE_TIMEOUT = timedelta(hours=24)


@workflows.workflow.define(name="document_processing_workflow")
class DocumentProcessingWorkflow(workflows.InteractiveWorkflow):

    async def _await_decision(self, document_id: str, schema, gate: str):
        """
        Wait for a reviewer at one of the four human gates.

        Returns None when the 24-hour window expires. `wait_for_input`
        raises asyncio.TimeoutError in that case, and left unhandled it
        failed the whole execution with an opaque error while the document
        stayed at `awaiting_review` / `checklist_hold` forever — visible to
        nobody and actionable by nobody. Callers check for None and end the
        run at the terminal `expired` status instead.
        """
        try:
            return await self.wait_for_input(schema, timeout=GATE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(
                f"[Document {document_id}] {gate} gate expired after "
                f"{GATE_TIMEOUT} with no decision"
            )
            await _update_status_and_message(
                document_id,
                "expired",
                f"No decision was made at the {gate} review within "
                f"{int(GATE_TIMEOUT.total_seconds() // 3600)} hours. Re-upload or retry to try again.",
            )
            return None

    @workflows.workflow.entrypoint
    async def run(self, document_id: str, filename: str, file_path: str,
                  auto_split: bool = True,
                  preclassified_doc_type: str = "",
                  preclassified_confidence: float = 0.0,
                  preclassified_reasoning: str = "") -> dict:
        """
        The per-document pipeline.

        `auto_split` and the `preclassified_*` fields are set by the packet
        splitter when it fans out the documents found inside an upload. They are
        all defaulted, so an ordinary single-document upload — and any execution
        already in flight — behaves exactly as it did before splitting existed.
        """
        logger.info(f"Starting workflow for document {document_id}")

        # Step 1 — Intake
        await _update_status(document_id, "processing")
        intake_result = await intake_activity(document_id, filename)

        if intake_result.get("is_duplicate"):
            # Pause — wait for user duplicate override decision
            logger.info(f"[Document {document_id}] Pausing for duplicate check override")
            await _update_status_and_message(document_id, "awaiting_review", "Duplicate detected. Waiting for override decision.")
            duplicate_decision = await self._await_decision(
                document_id, DuplicateDecisionRequest, "duplicate"
            )
            if duplicate_decision is None:
                return {"status": "expired", "reason": "duplicate_gate_timeout"}
            
            if not duplicate_decision.override:
                await _update_status_and_message(document_id, "rejected", "Duplicate not overridden.")
                return {"status": "rejected", "reason": "duplicate_not_overridden"}
            else:
                await _update_status_and_message(document_id, "processing", "")

        # Step 1.5 — Split detection (multi-document packets)
        # Runs ahead of pre-validation so each document found inside the packet gets
        # its own quality gate instead of one verdict for the whole stack. A failure
        # here degrades to "process the packet whole" rather than failing the upload.
        # ENABLE_DOC_SPLITTING is the only switch — there is no runtime override,
        # exactly as with ENABLE_DOC_CHECKLIST for Step 3.2. With it off the
        # document never enters the "splitting" status, so the step is absent
        # from the pipeline rather than flashing past as a no-op.
        if auto_split and settings.ENABLE_DOC_SPLITTING:
            await _update_status(document_id, "splitting")
            try:
                split_result = await splitter_activity(document_id, file_path)
            except Exception as e:
                logger.warning(
                    f"[Document {document_id}] Split detection failed, processing as a "
                    f"single document: {e}"
                )
                split_result = {"split": False, "reason": "splitter_error"}

            if split_result.get("split"):
                segments = split_result["segments"]

                if split_result.get("needs_review"):
                    logger.info(f"[Document {document_id}] Pausing for split boundary review")
                    await _update_status_and_message(
                        document_id, "awaiting_split_review",
                        f"{len(segments)} documents detected in this file. Confirm the boundaries."
                    )
                    split_decision = await self._await_decision(
                        document_id, SplitDecisionRequest, "split boundary"
                    )
                    if split_decision is None:
                        return {"status": "expired", "reason": "split_gate_timeout"}

                    if not split_decision.approved:
                        logger.info(f"[Document {document_id}] Reviewer rejected the split — processing whole")
                        split_result["split"] = False
                        await _update_status_and_message(document_id, "processing", "")
                    elif split_decision.segments:
                        segments = await rebuild_segments_activity(
                            [s.model_dump() for s in split_decision.segments],
                            split_result.get("page_count", 0),
                        )

                if split_result.get("split"):
                    await _update_status(document_id, "splitting")
                    fanout = await split_fanout_activity(
                        document_id, filename, file_path, segments, split_result.get("pages")
                    )
                    logger.info(
                        f"Completed workflow for document {document_id} — "
                        f"split into {len(fanout['children'])} documents"
                    )
                    # The parent ends here; each child runs this workflow on its own.
                    return {"status": "split", **fanout}
            else:
                logger.info(
                    f"[Document {document_id}] No split "
                    f"({split_result.get('reason') or 'single document'}) — continuing normally."
                )

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
        # A document that came out of a packet split was already classified page by
        # page during Step 1.5, so it carries its type in and skips this call
        # entirely. The splitter withholds the type when it resolved to "others" or
        # landed below the confidence threshold, and the child classifies normally.
        if preclassified_doc_type:
            doc_type = preclassified_doc_type
            logger.info(
                f"[Document {document_id}] Reusing split classification '{doc_type}' "
                f"(conf={preclassified_confidence:.2f}) — skipping classifier. "
                f"{preclassified_reasoning}"
            )
        else:
            await _update_status(document_id, "classifying")
            classifier_result = await classifier_activity(document_id, clean_file_path)
            doc_type = classifier_result["doc_type"]
        await _update_doc_type(document_id, doc_type)

        # Step 3.2 — Batch Checklist (batch-wide barrier)
        # Every document in the upload stops here. They resume together, once the
        # batch is known to be complete or a reviewer has answered for it — see
        # activities/checklist.py for why the barrier is batch-wide rather than
        # per-document. A document that parks here is resumed by whoever releases
        # the batch, which is either the last document to classify (nothing
        # missing) or the reviewer (something missing).
        if settings.ENABLE_DOC_CHECKLIST:
            await _update_status(document_id, "checklist")
            try:
                gate = await checklist_activity(document_id)
            except Exception as e:
                # A checklist failure must never strand a document we already
                # classified — degrade to "walk through" and keep going.
                logger.warning(
                    f"[Document {document_id}] Checklist failed, continuing without it: {e}"
                )
                gate = {"wait": False, "reason": "checklist_error"}

            if gate.get("wait"):
                # The gate holder is the one document a reviewer acts on; the rest
                # simply hold. Both are released by the same batch-wide fan-out.
                hold_status = (
                    "awaiting_checklist_review" if gate.get("gate_holder") else "checklist_hold"
                )
                await _update_status_and_message(document_id, hold_status, gate.get("message", ""))

                checklist_decision = await self._await_decision(
                    document_id, ChecklistDecisionRequest, "batch checklist"
                )
                if checklist_decision is None:
                    return {"status": "expired", "reason": "checklist_gate_timeout"}

                if not checklist_decision.proceed:
                    reason = (
                        checklist_decision.rejection_reason
                        or "Batch rejected as incomplete at the document checklist."
                    )
                    await _update_status_and_message(document_id, "rejected", reason)
                    return {"status": "rejected", "reason": reason, "checklist": gate}

                await _update_status_and_message(document_id, "processing", "")

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
            confidence_score=validator_result["confidence_score"],
            validation_errors=validator_result.get("validation_errors", [])
        )

        if reviewer_result.get("auto_approved"):
            final_reviewer_result = {"approved": True, "corrections": None}
        else:
            logger.info(f"[Document {document_id}] Pausing for human review. Score < 80%")
            review_reason = reviewer_result.get("summary") or "Confidence below threshold — manual review required."
            await _update_status_and_message(document_id, "awaiting_review", review_reason)
            # Pause workflow using Mistral Workflow SDK Interactive Workflow primitives
            human_decision = await self._await_decision(
                document_id, ReviewerDecisionRequest, "manual"
            )
            if human_decision is None:
                return {"status": "expired", "reason": "review_gate_timeout"}
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


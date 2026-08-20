"""
Mistral Managed Workflows Integration
======================================
Defines the document processing pipeline using Mistral's native Workflows SDK,
backed by Mistral's managed cloud orchestration (Temporal-as-a-Service).

When the platform is configured with workflow_engine: "mistral", this module
provides a durable workflow that replaces the local PipelineEngine. The SDK
connects to Mistral's cloud using MISTRAL_API_KEY and DEPLOYMENT_NAME env vars,
making all workflow executions visible in the Mistral Studio dashboard.

Activities wrap the existing activity functions from activities/*.py.
The workflow class orchestrates them in the correct sequence with conditional
logic for optional steps (pre_validate, preprocess, fraud_check, auto_verify).

For non-Mistral providers or explicit "local" config, the local PipelineEngine
(engine.py + definitions.py) continues to be used.
"""


import logging
from datetime import timedelta
from typing import Optional

import mistralai.workflows as workflows
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ─── Input / Output Schemas ─────────────────────────────────────────────────

class DocumentInput(BaseModel):
    """Input schema for the document processing workflow."""
    document_id: str
    filename: str
    file_path: str
    enable_pre_validation: bool = True
    enable_preprocessing: bool = False
    # Set when a reviewer overrides a duplicate: the workflow already ended at
    # the intake gate, so overriding means re-running with the gate disabled.
    skip_duplicate_check: bool = False
    # Same idea for the Step 3.2 checklist gate.
    skip_checklist_gate: bool = False


class DocumentOutput(BaseModel):
    """Output schema for the document processing workflow."""
    document_id: str
    status: str  # "completed" | "paused" | "rejected" | "failed"
    doc_type: Optional[str] = None
    error: Optional[str] = None
    paused_reason: Optional[str] = None


# ─── Progress-Tracking Activities ────────────────────────────────────────────
# The local PipelineEngine writes a status label to the DB before each step
# (engine.py -> on_status_change). The cloud workflow needs the same writes,
# otherwise the document sits at "pending" until the final output step and the
# UI's live pipeline timeline never advances.

@workflows.activity(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy_max_attempts=3,
)
async def activity_set_status(document_id: str, status: str) -> dict:
    """Publish the current pipeline stage so the UI timeline can follow along."""
    import db.operations as db
    await db.update_status(document_id, status)
    return {"document_id": document_id, "status": status}


@workflows.activity(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy_max_attempts=3,
)
async def activity_set_doc_type(document_id: str, doc_type: str) -> dict:
    """Persist the classified type as soon as it is known, not just at output."""
    import db.operations as db
    await db.update_doc_type(document_id, doc_type)
    return {"document_id": document_id, "doc_type": doc_type}


@workflows.activity(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy_max_attempts=3,
)
async def activity_set_terminal_status(document_id: str, status: str, message: str) -> dict:
    """Persist a non-completed terminal outcome (rejected / duplicate / failed).

    Only the output activity writes a status of its own, so without this every
    early return from the workflow left the document stuck mid-pipeline.
    """
    import db.operations as db
    await db.update_status_and_message(document_id, status, message)
    return {"document_id": document_id, "status": status}


# ─── Workflow Activities ─────────────────────────────────────────────────────
# Each activity wraps an existing activity function from activities/*.py.
# Activities are the units of real work — LLM calls, OCR, DB operations.
# They do NOT need to be deterministic and are automatically retried on failure.

@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=2,
)
async def activity_intake(document_id: str, filename: str) -> dict:
    """Step 1: Duplicate detection."""
    from activities.intake import intake_activity
    logger.info(f"[MistralWorkflow] Running intake for {document_id}")
    return await intake_activity(document_id, filename)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=2,
)
async def activity_pre_validate(document_id: str, file_path: str) -> dict:
    """Step 2: Quality pre-validation (blur, brightness, etc.)."""
    from activities.pre_validator import pre_validator_activity
    logger.info(f"[MistralWorkflow] Running pre-validation for {document_id}")
    return await pre_validator_activity(document_id, file_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=2,
)
async def activity_preprocess(document_id: str, file_path: str) -> dict:
    """Step 2.5: Image preprocessing (skew, CLAHE, noise)."""
    from activities.preprocessor import preprocessor_activity
    logger.info(f"[MistralWorkflow] Running preprocessing for {document_id}")
    return await preprocessor_activity(document_id, file_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=2,
)
async def activity_classify(document_id: str, file_path: str) -> dict:
    """Step 3: Document classification."""
    from activities.classifier import classifier_activity
    logger.info(f"[MistralWorkflow] Running classification for {document_id}")
    return await classifier_activity(document_id, file_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=2,
)
async def activity_checklist(document_id: str) -> dict:
    """Step 3.2: Reconcile the upload batch against the configured doc types."""
    from activities.checklist import checklist_activity
    logger.info(f"[MistralWorkflow] Running batch checklist for {document_id}")
    return await checklist_activity(document_id)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=2,
)
async def activity_fraud_check(document_id: str, file_path: str) -> dict:
    """Step 3.5: Fraud check (KYC documents)."""
    from activities.fraud_checker import fraud_check_activity
    logger.info(f"[MistralWorkflow] Running fraud check for {document_id}")
    return await fraud_check_activity(document_id, file_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy_max_attempts=2,
)
async def activity_extract(document_id: str, file_path: str, doc_type: str) -> dict:
    """Step 4: Data extraction (OCR + LLM)."""
    from activities.extractor import extractor_activity
    logger.info(f"[MistralWorkflow] Running extraction for {document_id}")
    return await extractor_activity(document_id, file_path, doc_type)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy_max_attempts=2,
)
async def activity_validate(
    document_id: str,
    extracted_data: dict,
    doc_type: str,
    ocr_confidence: float,
    field_confidences: dict,
) -> dict:
    """Step 5: Data validation."""
    from activities.validator import validator_activity
    logger.info(f"[MistralWorkflow] Running validation for {document_id}")
    return await validator_activity(
        document_id=document_id,
        extracted_data=extracted_data,
        doc_type=doc_type,
        ocr_confidence=ocr_confidence,
        field_confidences=field_confidences,
    )


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy_max_attempts=1,
)
async def activity_auto_verify(document_id: str, validated_data: dict) -> dict:
    """Step 5.5: Automated verification (signature + face matching)."""
    from activities.auto_verifier import auto_verify_activity
    logger.info(f"[MistralWorkflow] Running auto-verification for {document_id}")
    return await auto_verify_activity(document_id, validated_data)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy_max_attempts=2,
)
async def activity_review(
    document_id: str,
    confidence_score: float,
    validated_data: dict,
) -> dict:
    """Step 6: Review (determines if human review is needed)."""
    from activities.reviewer import reviewer_activity
    logger.info(f"[MistralWorkflow] Running review for {document_id}")
    return await reviewer_activity(
        document_id=document_id,
        confidence_score=confidence_score,
        validated_data=validated_data,
    )


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy_max_attempts=2,
)
async def activity_output(document_id: str, pipeline_context: dict) -> dict:
    """Step 7: Final output generation — persist results to DB."""
    from activities.output import output_activity
    logger.info(f"[MistralWorkflow] Running output for {document_id}")
    return await output_activity(document_id, pipeline_context)


# ─── Helper ──────────────────────────────────────────────────────────────────

KYC_DOC_TYPES = {"kyc", "kyc document", "identity document", "id_proof", "pan_card"}


def _is_kyc_doc_type(doc_type: str) -> bool:
    """Check if a document type is a KYC/identity document."""
    return doc_type.lower() in KYC_DOC_TYPES


# ─── Workflow Definition ─────────────────────────────────────────────────────
# The workflow is the "orchestration brain". It MUST be deterministic —
# the platform may replay it from history if a worker restarts.
# All side-effect work (LLM calls, DB ops) happens inside activities.

@workflows.workflow.define(
    name="document-processing",
    workflow_display_name="Document Processing Pipeline",
    workflow_description="OCR → Classify → Extract → Validate → Review → Output",
    execution_timeout=timedelta(minutes=30),
)
class DocumentProcessingWorkflow:
    """
    Mistral-native document processing workflow.

    Replaces the local PipelineEngine for Mistral-configured deployments.
    Each step calls the corresponding @workflows.activity, which in turn
    calls the existing activity function from activities/*.py.
    """

    @workflows.workflow.entrypoint
    async def run(self, input: DocumentInput) -> DocumentOutput:
        document_id = input.document_id
        filename = input.filename
        file_path = input.file_path

        try:
            # ── Step 1: Intake (duplicate detection) ──────────────────────
            await activity_set_status(document_id, "processing")
            intake_result = await activity_intake(document_id, filename)
            if intake_result.get("is_duplicate") and input.skip_duplicate_check:
                logger.info(
                    f"[MistralWorkflow] Duplicate override in effect for {document_id} — continuing"
                )
            elif intake_result.get("is_duplicate"):
                existing_id = intake_result.get("existing_document_id")
                reason = (
                    f"Duplicate of an already-ingested document ({existing_id})."
                    if existing_id
                    else "Duplicate detected. Waiting for override decision."
                )
                await activity_set_terminal_status(document_id, "duplicate", reason)
                return DocumentOutput(
                    document_id=document_id,
                    status="paused",
                    paused_reason=reason,
                )

            # ── Step 2: Pre-Validation (optional) ─────────────────────────
            if input.enable_pre_validation:
                await activity_set_status(document_id, "pre_validating")
                pre_val_result = await activity_pre_validate(document_id, file_path)
                if not pre_val_result.get("passed"):
                    reason = pre_val_result.get("rejection_reason", "Document failed pre-validation.")
                    await activity_set_terminal_status(document_id, "rejected", reason)
                    return DocumentOutput(
                        document_id=document_id,
                        status="rejected",
                        error=reason,
                    )

            # ── Step 2.5: Preprocessing (optional) ────────────────────────
            clean_file_path = file_path
            if input.enable_preprocessing:
                await activity_set_status(document_id, "preprocessing")
                preprocess_result = await activity_preprocess(document_id, file_path)
                clean_file_path = preprocess_result.get("preprocessed_path") or file_path

            # ── Step 3: Classify ──────────────────────────────────────────
            await activity_set_status(document_id, "classifying")
            classify_result = await activity_classify(document_id, clean_file_path)
            doc_type = classify_result.get("doc_type", "others")
            await activity_set_doc_type(document_id, doc_type)

            # ── Step 3.2: Batch Checklist ─────────────────────────────────
            # This workflow has no wait_for_input primitive, so an incomplete
            # batch is parked in the review queue the same way an under-confident
            # extraction is — the API resumes it by re-running with the override.
            if not input.skip_checklist_gate:
                await activity_set_status(document_id, "checklist")
                gate = await activity_checklist(document_id)
                if gate.get("wait"):
                    reason = gate.get("message") or "Waiting on the batch document checklist."
                    await activity_set_terminal_status(
                        document_id,
                        "awaiting_checklist_review" if gate.get("gate_holder") else "checklist_hold",
                        reason,
                    )
                    return DocumentOutput(
                        document_id=document_id,
                        status="paused",
                        doc_type=doc_type,
                        paused_reason=reason,
                    )

            # ── Step 3.5: Fraud Check (KYC only) ─────────────────────────
            fraud_check_result = None
            if _is_kyc_doc_type(doc_type):
                await activity_set_status(document_id, "fraud_checking")
                fraud_check_result = await activity_fraud_check(document_id, clean_file_path)
                if not fraud_check_result.get("passed", False):
                    reason = fraud_check_result.get("rejection_reason", "Document failed fraud check.")
                    await activity_set_terminal_status(document_id, "rejected", reason)
                    return DocumentOutput(
                        document_id=document_id,
                        status="rejected",
                        doc_type=doc_type,
                        error=reason,
                    )

            # ── Step 4: Extract ───────────────────────────────────────────
            await activity_set_status(document_id, "extracting")
            extractor_result = await activity_extract(document_id, clean_file_path, doc_type)

            # ── Step 5: Validate ──────────────────────────────────────────
            await activity_set_status(document_id, "validating")
            validator_result = await activity_validate(
                document_id=document_id,
                extracted_data=extractor_result.get("fields", {}),
                doc_type=doc_type,
                ocr_confidence=extractor_result.get("confidence", 0.0),
                field_confidences=extractor_result.get("field_confidences", {}),
            )

            # ── Step 5.5: Auto-Verify (KYC only) ─────────────────────────
            auto_verify_result = None
            if _is_kyc_doc_type(doc_type):
                await activity_set_status(document_id, "auto_verifying")
                auto_verify_result = await activity_auto_verify(
                    document_id=document_id,
                    validated_data=validator_result.get("validated_data", {}),
                )

            # ── Step 6: Review ────────────────────────────────────────────
            await activity_set_status(document_id, "reviewing")
            review_result = await activity_review(
                document_id=document_id,
                confidence_score=extractor_result.get("confidence", 0.0),
                validated_data=validator_result.get("validated_data", {}),
            )

            reviewer_final = None
            if review_result.get("auto_approved"):
                reviewer_final = {"approved": True, "corrections": None}
            else:
                # Needs human review — park it in the review queue
                reason = "Confidence below threshold. Manual review required."
                await activity_set_terminal_status(document_id, "awaiting_review", reason)
                return DocumentOutput(
                    document_id=document_id,
                    status="paused",
                    doc_type=doc_type,
                    paused_reason=reason,
                )

            # ── Step 7: Output ────────────────────────────────────────────
            pipeline_context = {
                "doc_type": doc_type,
                "validated_data": validator_result.get("validated_data", {}),
                "reviewer_result": reviewer_final or {},
                "confidence_score": extractor_result.get("confidence", 0.0),
                "field_confidences": extractor_result.get("field_confidences"),
                "fraud_check": fraud_check_result,
                "raw_extracted": extractor_result.get("raw_extracted"),
                "auto_verify_result": auto_verify_result,
            }

            await activity_set_status(document_id, "finalizing")
            await activity_output(document_id, pipeline_context)

            return DocumentOutput(
                document_id=document_id,
                status="completed",
                doc_type=doc_type,
            )

        except Exception as e:
            logger.error(f"[MistralWorkflow] Pipeline failed for {document_id}: {e}")
            try:
                await activity_set_terminal_status(document_id, "failed", str(e))
            except Exception as status_err:  # never mask the original failure
                logger.error(f"[MistralWorkflow] Could not persist failure status: {status_err}")
            return DocumentOutput(
                document_id=document_id,
                status="failed",
                error=str(e),
            )

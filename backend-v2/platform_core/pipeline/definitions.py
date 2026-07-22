"""
Pipeline Definitions
====================
Defines the concrete pipeline step sequences for document and claim processing.

This is the direct replacement for workflow.py's step ordering.
Each step is a thin wrapper that calls the appropriate service using
the provider registry.

Current workflow.py flow:
    intake → pre_validate → preprocess → classify → fraud_check
    → extract → validate → auto_verify → review → output

New pipeline flow (identical order, but vendor-agnostic):
    Same steps, but each uses registry.get_llm_chain("step_name")
    instead of client.agents.complete_async(agent_id=...).
"""

import logging
from platform_core.pipeline.engine import (
    PipelineDefinition,
    StepDefinition,
    HumanInputRequired,
    PipelineRejected,
)

logger = logging.getLogger(__name__)


# ─── Document Processing Pipeline ───────────────────────────────────────────

def build_document_pipeline(config: dict) -> PipelineDefinition:
    """
    Build the document processing pipeline definition from config.

    Maps workflow.py:57-205 → PipelineDefinition with StepDefinitions.

    Args:
        config: The pipelines.document_processing section of platform.yaml.
    """
    pipeline_config = config.get("pipelines", {}).get("document_processing", {})
    step_timeout = pipeline_config.get("step_timeout_seconds", 300)

    steps = [
        # Step 1 — Intake (duplicate detection)
        # Maps: workflow.py:66
        StepDefinition(
            name="intake",
            handler=_step_intake,
            status_label="processing",
            required=True,
            timeout_seconds=step_timeout,
        ),

        # Step 2 — Pre-Validation (blur, brightness, readability check)
        # Maps: workflow.py:83-97
        StepDefinition(
            name="pre_validate",
            handler=_step_pre_validate,
            status_label="pre_validating",
            required=False,  # Gracefully skip if not configured
            condition=lambda ctx: pipeline_config.get("enable_pre_validation", True),
            timeout_seconds=step_timeout,
        ),

        # Step 2.5 — Preprocessing (skew, CLAHE, noise removal)
        # Maps: workflow.py:99-113
        StepDefinition(
            name="preprocess",
            handler=_step_preprocess,
            status_label="preprocessing",
            required=False,
            condition=lambda ctx: pipeline_config.get("enable_preprocessing", False),
            timeout_seconds=step_timeout,
        ),

        # Step 3 — Classify
        # Maps: workflow.py:116-119
        StepDefinition(
            name="classify",
            handler=_step_classify,
            status_label="classifying",
            required=True,
            timeout_seconds=step_timeout,
        ),

        # Step 3.5 — Fraud Check (KYC documents only)
        # Maps: workflow.py:121-135
        StepDefinition(
            name="fraud_check",
            handler=_step_fraud_check,
            status_label="fraud_checking",
            required=False,  # Gracefully skip on error
            condition=lambda ctx: _is_kyc_document(ctx),
            timeout_seconds=step_timeout,
        ),

        # Step 4 — Extract
        # Maps: workflow.py:138-142
        StepDefinition(
            name="extract",
            handler=_step_extract,
            status_label="extracting",
            required=True,
            timeout_seconds=step_timeout,
        ),

        # Step 5 — Validate
        # Maps: workflow.py:144-152
        StepDefinition(
            name="validate",
            handler=_step_validate,
            status_label="validating",
            required=True,
            timeout_seconds=step_timeout,
        ),

        # Step 5.5 — Auto-Verify (KYC only: signature + face matching)
        # Maps: workflow.py:154-164
        StepDefinition(
            name="auto_verify",
            handler=_step_auto_verify,
            status_label="auto_verifying",
            required=False,
            condition=lambda ctx: _is_kyc_document(ctx),
            timeout_seconds=step_timeout,
        ),

        # Step 6 — Review (may pause for HITL)
        # Maps: workflow.py:166-188
        StepDefinition(
            name="review",
            handler=_step_review,
            status_label="reviewing",
            required=True,
            timeout_seconds=step_timeout,
        ),

        # Step 7 — Output
        # Maps: workflow.py:190-205
        StepDefinition(
            name="output",
            handler=_step_output,
            status_label="finalizing",
            required=True,
            timeout_seconds=step_timeout,
        ),
    ]

    return PipelineDefinition(name="document_processing", steps=steps)


# ─── Step Handlers ───────────────────────────────────────────────────────────
# Each step handler receives the pipeline context dict and returns
# a dict of outputs to merge back into context.
#
# These are thin orchestration wrappers. The actual business logic
# lives in services/document/steps/*.py (to be migrated from activities/).
#
# For now, they call the existing activity functions as a bridge.

async def _step_intake(context: dict) -> dict:
    """Step 1: Duplicate detection."""
    from activities.intake import intake_activity

    document_id = context["document_id"]
    filename = context["filename"]

    result = await intake_activity(document_id, filename)

    if result.get("is_duplicate"):
        raise HumanInputRequired(
            reason="Duplicate detected. Waiting for override decision.",
            data={"intake_result": result},
        )

    return {"intake_result": result}


async def _step_pre_validate(context: dict) -> dict:
    """Step 2: Quality pre-validation (blur, brightness, etc.)."""
    from activities.pre_validator import pre_validator_activity

    result = await pre_validator_activity(
        context["document_id"], context["file_path"]
    )

    if not result.get("passed"):
        reason = result.get("rejection_reason", "Document failed pre-validation.")
        raise PipelineRejected(reason=reason, data={"pre_validation": result})

    return {"pre_validation_result": result}


async def _step_preprocess(context: dict) -> dict:
    """Step 2.5: Image preprocessing (skew, CLAHE, noise)."""
    from activities.preprocessor import preprocessor_activity

    result = await preprocessor_activity(
        context["document_id"], context["file_path"]
    )

    clean_path = result.get("preprocessed_path") or context["file_path"]
    return {"preprocess_result": result, "clean_file_path": clean_path}


async def _step_classify(context: dict) -> dict:
    """Step 3: Document classification."""
    from activities.classifier import classifier_activity

    file_path = context.get("clean_file_path", context["file_path"])
    result = await classifier_activity(context["document_id"], file_path)

    return {
        "classifier_result": result,
        "doc_type": result["doc_type"],
    }


async def _step_fraud_check(context: dict) -> dict:
    """Step 3.5: Fraud check (KYC documents)."""
    from activities.fraud_checker import fraud_check_activity

    file_path = context.get("clean_file_path", context["file_path"])
    result = await fraud_check_activity(context["document_id"], file_path)

    if not result.get("passed", False):
        reason = result.get("rejection_reason", "Document failed fraud check.")
        raise PipelineRejected(reason=reason, data={"fraud_check": result})

    return {"fraud_check_result": result}


async def _step_extract(context: dict) -> dict:
    """Step 4: Data extraction."""
    from activities.extractor import extractor_activity

    file_path = context.get("clean_file_path", context["file_path"])
    result = await extractor_activity(
        context["document_id"], file_path, context["doc_type"]
    )

    return {
        "extractor_result": result,
        "raw_extracted": result.get("raw_extracted"),
    }


async def _step_validate(context: dict) -> dict:
    """Step 5: Data validation."""
    from activities.validator import validator_activity

    result = await validator_activity(
        document_id=context["document_id"],
        extracted_data=context["extractor_result"]["fields"],
        doc_type=context["doc_type"],
        ocr_confidence=context["extractor_result"]["confidence"],
        field_confidences=context["extractor_result"].get("field_confidences"),
    )

    return {"validator_result": result}


async def _step_auto_verify(context: dict) -> dict:
    """Step 5.5: Automated verification (signature + face matching)."""
    from activities.auto_verifier import auto_verify_activity

    result = await auto_verify_activity(
        document_id=context["document_id"],
        validated_data=context["validator_result"]["validated_data"],
    )

    return {"auto_verify_result": result}


async def _step_review(context: dict) -> dict:
    """Step 6: Review (may trigger HITL pause)."""
    from activities.reviewer import reviewer_activity

    result = await reviewer_activity(
        document_id=context["document_id"],
        validated_data=context["validator_result"]["validated_data"],
        confidence_score=context["validator_result"]["confidence_score"],
    )

    if result.get("auto_approved"):
        return {
            "reviewer_result": result,
            "final_reviewer_result": {"approved": True, "corrections": None},
        }

    # Needs human review — pause the pipeline
    raise HumanInputRequired(
        reason="Confidence below threshold. Manual review required.",
        data={"reviewer_result": result},
    )


async def _step_output(context: dict) -> dict:
    """Step 7: Final output generation."""
    from activities.output import output_activity

    auto_verify = context.get("auto_verify_result")

    result = await output_activity(
        document_id=context["document_id"],
        doc_type=context["doc_type"],
        validated_data=context["validator_result"]["validated_data"],
        reviewer_result=context["final_reviewer_result"],
        confidence_score=context["validator_result"]["confidence_score"],
        field_confidences=context["validator_result"].get("field_confidences"),
        fraud_check=context.get("fraud_check_result"),
        raw_extracted=context.get("raw_extracted"),
        signature_verification=auto_verify.get("signature") if auto_verify else None,
        photo_verification=auto_verify.get("photo") if auto_verify else None,
    )

    return {"output_result": result, "status": "completed"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_kyc_document(context: dict) -> bool:
    """Check if the current document is a KYC/identity document."""
    doc_type = context.get("doc_type", "").lower()
    if doc_type in ("kyc", "kyc document", "identity document", "id_proof", "pan_card"):
        return True
    # Check template metadata if available
    template_meta = context.get("template_metadata", {})
    return template_meta.get("is_kyc", False)


# ─── Claim Processing Pipeline ──────────────────────────────────────────────

def build_claim_pipeline(config: dict) -> PipelineDefinition:
    """
    Build the claim processing pipeline definition from config.

    Maps claim_workflow.py flow → PipelineDefinition with StepDefinitions.
    Flow: integrity → medical → treatment → disability → litigation → report → save

    Args:
        config: The pipelines.claim_processing section of platform.yaml.
    """
    pipeline_config = config.get("pipelines", {}).get("claim_processing", {})
    step_timeout = pipeline_config.get("step_timeout_seconds", 120)

    steps = [
        StepDefinition(
            name="claim_integrity",
            handler=_step_claim_integrity,
            status_label="checking_integrity",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="claim_medical",
            handler=_step_claim_medical,
            status_label="checking_medical",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="claim_treatment",
            handler=_step_claim_treatment,
            status_label="checking_treatment",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="claim_disability",
            handler=_step_claim_disability,
            status_label="checking_disability",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="claim_litigation",
            handler=_step_claim_litigation,
            status_label="checking_litigation",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="claim_report",
            handler=_step_claim_report,
            status_label="generating_report",
            required=True,
            timeout_seconds=step_timeout,
        ),
        StepDefinition(
            name="save_claim_report",
            handler=_step_save_claim_report,
            status_label="saving_report",
            required=True,
            timeout_seconds=step_timeout,
        ),
    ]

    return PipelineDefinition(name="claim_processing", steps=steps)


# ─── Claim Step Handlers ────────────────────────────────────────────────────

async def _step_claim_integrity(context: dict) -> dict:
    """Agent 1: Claim Integrity — completeness, dates, policy, duplicates."""
    from activities.claim_integrity import claim_integrity_activity
    import db.claim_operations as claim_db

    claim_id = context["claim_id"]
    await claim_db.update_claim_status(claim_id, "checking_integrity")

    result = await claim_integrity_activity(
        claim_id=claim_id,
        claimant_id=context["claimant_id"],
        policy_id=context["policy_id"],
    )

    await claim_db.upsert_agent_result(claim_id, "integrity", result)
    return {"agent_results": {"integrity": result}}


async def _step_claim_medical(context: dict) -> dict:
    """Agent 2: Medical — diagnosis, ICD codes, provider, documentation."""
    from activities.claim_medical import claim_medical_activity
    import db.claim_operations as claim_db

    claim_id = context["claim_id"]
    await claim_db.update_claim_status(claim_id, "checking_medical")

    result = await claim_medical_activity(claim_id=claim_id)

    await claim_db.upsert_agent_result(claim_id, "medical", result)
    agent_results = context.get("agent_results", {})
    agent_results["medical"] = result
    return {"agent_results": agent_results}


async def _step_claim_treatment(context: dict) -> dict:
    """Agent 3: Treatment — treatment-diagnosis alignment, billing."""
    from activities.claim_treatment import claim_treatment_activity
    import db.claim_operations as claim_db

    claim_id = context["claim_id"]
    await claim_db.update_claim_status(claim_id, "checking_treatment")

    result = await claim_treatment_activity(claim_id=claim_id)

    await claim_db.upsert_agent_result(claim_id, "treatment", result)
    agent_results = context.get("agent_results", {})
    agent_results["treatment"] = result
    return {"agent_results": agent_results}


async def _step_claim_disability(context: dict) -> dict:
    """Agent 4: Disability — certificate, severity, consistency."""
    from activities.claim_disability import claim_disability_activity
    import db.claim_operations as claim_db

    claim_id = context["claim_id"]
    await claim_db.update_claim_status(claim_id, "checking_disability")

    result = await claim_disability_activity(claim_id=claim_id)

    await claim_db.upsert_agent_result(claim_id, "disability", result)
    agent_results = context.get("agent_results", {})
    agent_results["disability"] = result
    return {"agent_results": agent_results}


async def _step_claim_litigation(context: dict) -> dict:
    """Agent 5: Litigation — attorney involvement, claim frequency, suspicious language."""
    from activities.claim_litigation import claim_litigation_activity
    import db.claim_operations as claim_db

    claim_id = context["claim_id"]
    await claim_db.update_claim_status(claim_id, "checking_litigation")

    result = await claim_litigation_activity(
        claim_id=claim_id,
        claimant_id=context["claimant_id"],
    )

    await claim_db.upsert_agent_result(claim_id, "litigation", result)
    agent_results = context.get("agent_results", {})
    agent_results["litigation"] = result
    return {"agent_results": agent_results}


async def _step_claim_report(context: dict) -> dict:
    """Generate final suggestion via Claim Report Agent (LLM) or fallback."""
    import json
    import db.claim_operations as claim_db
    from platform_core.registry import ProviderRegistry
    from platform_core.prompts.manager import PromptManager
    from platform_core.agent_loop import run_simple_completion

    claim_id = context["claim_id"]
    agent_results = context.get("agent_results", {})
    await claim_db.update_claim_status(claim_id, "generating_report")

    # Build summary for the report agent
    summary_lines = []
    for agent_name, result in agent_results.items():
        status = result.get("status", "UNKNOWN")
        reason = result.get("overall_reason", "")
        summary_lines.append(f"- {agent_name}: {status} — {reason}")

    agent_summary = "\n".join(summary_lines)

    prompt = (
        f"You are generating the final suggestion for claim_id='{claim_id}'.\n\n"
        f"Here are the results from all 5 validator agents:\n"
        f"{agent_summary}\n\n"
        f"Full agent results JSON for detailed context:\n"
        f"{json.dumps(agent_results, indent=2)}\n\n"
        f"Write the final suggestion as per your instructions. Return ONLY the JSON object."
    )

    try:
        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        prompts_mgr = PromptManager()
        system_prompt = prompts_mgr.get("claim_report")

        report = await run_simple_completion(
            llm=llm,
            system_prompt=system_prompt,
            user_message=prompt,
            temperature=0.2,
        )
    except Exception as e:
        logger.error(f"[Claim {claim_id}] Report Agent failed: {e}. Using fallback.")
        report = _fallback_claim_suggestion(agent_results)

    return {
        "report_suggestion": report.get("suggestion", ""),
        "report_overall_status": report.get("overall_status", "REVIEW BEFORE APPROVAL"),
    }


async def _step_save_claim_report(context: dict) -> dict:
    """Persist the final claim report to the database."""
    import db.claim_operations as claim_db
    from datetime import datetime, timezone

    claim_id = context["claim_id"]
    agent_results = context.get("agent_results", {})
    suggestion = context.get("report_suggestion", "")
    overall_status = context.get("report_overall_status", "REVIEW BEFORE APPROVAL")

    claim = await claim_db.get_claim(claim_id)
    claimant_name = claim.claimant_name if claim else None

    await claim_db.save_claim_report(
        claim_id=claim_id,
        claimant_name=claimant_name,
        agent_results=agent_results,
        suggestion=suggestion,
        overall_status=overall_status,
    )

    await claim_db.update_claim_status(claim_id, "completed")

    return {
        "status": "completed",
        "claimant_name": claimant_name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


def _fallback_claim_suggestion(agent_results: dict) -> dict:
    """
    Rule-based fallback suggestion when the Claim Report LLM is unavailable.
    Determines overall_status from agent statuses and writes a basic suggestion.
    """
    failures = [name for name, r in agent_results.items() if r.get("status") == "FAIL"]
    flags = [name for name, r in agent_results.items() if r.get("status") == "FLAG"]

    if failures:
        overall_status = "REJECT"
        suggestion = (
            f"The claim has failed validation in the following areas: {', '.join(failures)}. "
            f"Manual review is required before any further processing. "
            f"The identified issues must be resolved or explained before the claim can be approved."
        )
    elif flags:
        overall_status = "REVIEW BEFORE APPROVAL"
        suggestion = (
            f"The claim has passed core validations but has flagged items in: {', '.join(flags)}. "
            f"These items require human attention before final approval."
        )
    else:
        overall_status = "APPROVE"
        suggestion = (
            "All 5 validator agents have passed. The claim appears to be complete, "
            "consistent, and properly documented. Recommendation: approve."
        )

    return {"overall_status": overall_status, "suggestion": suggestion}

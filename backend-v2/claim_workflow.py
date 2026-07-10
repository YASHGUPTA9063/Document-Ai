"""
claim_workflow.py
─────────────────
Mistral Workflows definition for the Claim Processing Pipeline.

Mirrors the structure of workflow.py (Document OCR pipeline).
Takes a claim_id as input, runs 5 validator agents sequentially,
generates a final suggestion via the Claim Report Agent, and
saves the complete report to the DB.

No human-in-the-loop pauses — fully automated.

Workflow name: "claim_processing_workflow"

Input:
    claim_id    (str) — e.g. "CLM-001"
    claimant_id (str) — e.g. "CLT-001"
    policy_id   (str) — e.g. "POL-123"

Output:
    dict — full claim report (mirrors ClaimReport DB structure)
"""
import json
import logging
import mistralai.workflows as workflows

with workflows.workflow.unsafe.imports_passed_through():
    from activities.claim_integrity import claim_integrity_activity
    from activities.claim_medical import claim_medical_activity
    from activities.claim_treatment import claim_treatment_activity
    from activities.claim_disability import claim_disability_activity
    from activities.claim_litigation import claim_litigation_activity
    import db.claim_operations as claim_db
    from config import settings

logger = logging.getLogger(__name__)


# ─── STATUS UPDATE ACTIVITY ────────────────────────────────────────────────────

@workflows.activity()
async def update_claim_status_activity(claim_id: str, status: str) -> str:
    """Updates the processing status of a claim in the DB."""
    import db.claim_operations as claim_db
    await claim_db.update_claim_status(claim_id, status)
    return status


# ─── REPORT AGENT ACTIVITY ────────────────────────────────────────────────────

@workflows.activity()
async def generate_claim_suggestion_activity(claim_id: str, agent_results: dict) -> dict:
    """
    Calls the Claim Report Agent to generate a plain-English suggestion
    paragraph based on all 5 agent results.

    Returns:
        {
            "overall_status": "APPROVE" | "REVIEW BEFORE APPROVAL" | "REJECT",
            "suggestion": "..."
        }
    """
    from mistralai.client import Mistral

    client = Mistral(api_key=settings.MISTRAL_API_KEY)

    if not settings.CLAIM_REPORT_AGENT_ID:
        logger.warning(f"[Claim {claim_id}] CLAIM_REPORT_AGENT_ID not set — generating fallback suggestion.")
        return _fallback_suggestion(agent_results)

    # Build a compact summary of all 5 agent results to pass to the report agent
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

    messages = [{"role": "user", "content": prompt}]

    logger.info(f"[Claim {claim_id}] Calling Claim Report Agent ({settings.CLAIM_REPORT_AGENT_ID})")
    try:
        response = client.agents.complete(
            agent_id=settings.CLAIM_REPORT_AGENT_ID,
            messages=messages,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(c.text if hasattr(c, "text") else str(c) for c in content)
        parsed = json.loads(content.strip())
        return parsed
    except Exception as e:
        logger.error(f"[Claim {claim_id}] Report Agent failed: {e}. Using fallback.")
        return _fallback_suggestion(agent_results)


def _fallback_suggestion(agent_results: dict) -> dict:
    """
    Rule-based fallback suggestion when the Claim Report Agent is unavailable.
    Determines overall_status from agent statuses and writes a basic suggestion.
    """
    statuses = [r.get("status", "UNKNOWN") for r in agent_results.values()]
    failures = [name for name, r in agent_results.items() if r.get("status") == "FAIL"]
    flags = [name for name, r in agent_results.items() if r.get("status") == "FLAG"]
    errors = [name for name, r in agent_results.items() if r.get("status") == "ERROR"]

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
            f"The claim has passed most validation checks but has been flagged in: {', '.join(flags)}. "
            f"These items require human adjuster review before a final decision can be made. "
            f"If the flagged items can be satisfactorily explained, the claim may proceed to approval."
        )
    elif errors:
        overall_status = "REVIEW BEFORE APPROVAL"
        suggestion = (
            f"Some agent checks could not be completed due to technical errors: {', '.join(errors)}. "
            f"Manual review is recommended to ensure all validations are covered."
        )
    else:
        overall_status = "APPROVE"
        suggestion = (
            "All validation checks passed. The claim is complete, medically sound, "
            "treatment-aligned, and shows no litigation or fraud indicators. "
            "This claim is recommended for approval."
        )

    return {"overall_status": overall_status, "suggestion": suggestion}


# ─── MAIN WORKFLOW ─────────────────────────────────────────────────────────────

@workflows.workflow.define(name="claim_processing_workflow")
class ClaimProcessingWorkflow(workflows.InteractiveWorkflow):
    """
    Claim Processing Pipeline.

    Runs 5 validator agents sequentially against a claim, collects all results,
    generates a final suggestion, and saves the report to the DB.

    This is a fully automated, non-interactive workflow (no human-in-the-loop pauses).
    """

    @workflows.workflow.entrypoint
    async def run(self, claim_id: str, claimant_id: str, policy_id: str) -> dict:
        logger.info(f"[Claim {claim_id}] Starting claim processing workflow.")

        # ── Mark claim as processing ──────────────────────────────────────────
        await update_claim_status_activity(claim_id, "processing")

        # ── Step 1 — Claim Integrity Agent ────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 1: Claim Integrity Agent")
        await update_claim_status_activity(claim_id, "checking_integrity")
        integrity_result = await claim_integrity_activity(claim_id, claimant_id, policy_id)

        # ── Step 2 — Medical Agent ────────────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 2: Medical Agent")
        await update_claim_status_activity(claim_id, "checking_medical")
        medical_result = await claim_medical_activity(claim_id)

        # ── Step 3 — Treatment Agent ──────────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 3: Treatment Agent")
        await update_claim_status_activity(claim_id, "checking_treatment")
        treatment_result = await claim_treatment_activity(claim_id)

        # ── Step 4 — Disability Agent ─────────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 4: Disability Agent")
        await update_claim_status_activity(claim_id, "checking_disability")
        disability_result = await claim_disability_activity(claim_id)

        # ── Step 5 — Litigation Agent ─────────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 5: Litigation Agent")
        await update_claim_status_activity(claim_id, "checking_litigation")
        litigation_result = await claim_litigation_activity(claim_id, claimant_id)

        # ── Collect all agent results ─────────────────────────────────────────
        agent_results = {
            "claim_integrity": integrity_result,
            "medical": medical_result,
            "treatment": treatment_result,
            "disability": disability_result,
            "litigation": litigation_result,
        }

        # ── Step 6 — Generate suggestion ──────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 6: Generating final suggestion")
        await update_claim_status_activity(claim_id, "generating_report")
        suggestion_result = await generate_claim_suggestion_activity(claim_id, agent_results)

        overall_status = suggestion_result.get("overall_status", "REVIEW BEFORE APPROVAL")
        suggestion_text = suggestion_result.get("suggestion", "")

        # Pull claimant name from integrity result if available
        claimant_name = _extract_claimant_name(integrity_result)

        # ── Step 7 — Save report to DB ────────────────────────────────────────
        logger.info(f"[Claim {claim_id}] Step 7: Saving report to DB")
        await claim_db.save_claim_report(
            claim_id=claim_id,
            claimant_name=claimant_name,
            agent_results=agent_results,
            suggestion=suggestion_text,
            overall_status=overall_status
        )
        await update_claim_status_activity(claim_id, "completed")

        # ── Build and return the full report dict ─────────────────────────────
        report = _build_report_dict(
            claim_id=claim_id,
            claimant_name=claimant_name,
            agent_results=agent_results,
            overall_status=overall_status,
            suggestion=suggestion_text
        )

        logger.info(f"[Claim {claim_id}] Workflow completed. Overall status: {overall_status}")
        return report


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _extract_claimant_name(integrity_result: dict) -> str | None:
    """
    Tries to extract the claimant name from the Integrity Agent's evidence/checks.
    Returns None if not found — the DB field is nullable.
    """
    checks = integrity_result.get("checks", [])
    for check in checks:
        explanation = check.get("explanation", "")
        # Simple heuristic: the required fields check usually mentions the claimant name
        # If the agent surfaces evidence, it would be in a structured field
    # Fall back to None — can be set from the Claim table directly
    return integrity_result.get("claimant_name") or None


def _build_report_dict(
    claim_id: str,
    claimant_name: str | None,
    agent_results: dict,
    overall_status: str,
    suggestion: str
) -> dict:
    """
    Builds the structured final report dictionary returned by the workflow.
    Matches the format described in the POC spec.
    """
    from datetime import datetime, timezone

    # Map agent results to a display-friendly summary
    agent_summary = {}
    for key, result in agent_results.items():
        agent_summary[key] = {
            "status": result.get("status", "UNKNOWN"),
            "overall_reason": result.get("overall_reason", ""),
            "checks": result.get("checks", [])
        }

    return {
        "claim_id": claim_id,
        "claimant_name": claimant_name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "agent_results": agent_summary,
        "overall_status": overall_status,
        "suggestion": suggestion
    }

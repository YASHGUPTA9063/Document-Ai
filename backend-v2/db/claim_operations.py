"""
claim_operations.py
───────────────────
Async database operations for the Claim Processing workflow.
Kept separate from operations.py to avoid polluting the OCR document workflow's DB layer.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.future import select
from db.database import AsyncSessionLocal
from db.models import Claim, ClaimDocument, ClaimantHistory, PolicyDetails, ClaimReport

logger = logging.getLogger(__name__)


# ─── FETCH TOOLS (called by claim tool functions) ─────────────────────────────

async def get_claim_documents_data(claim_id: str, doc_types: list[str]) -> dict:
    """
    Fetches the OCR field-value pairs for the specified document types belonging to a claim.
    Returns a dict keyed by doc_type, each containing the extracted fields.

    Example return:
    {
        "claim_form": {"claimant_name": "John Doe", "dob": "1985-03-12", ...},
        "medical_report": {"diagnosis": "Lumbar Disc Herniation", "icd_code": "M51.16", ...}
    }
    """
    result_data = {}
    async with AsyncSessionLocal() as session:
        for doc_type in doc_types:
            query = select(ClaimDocument).where(
                ClaimDocument.claim_id == claim_id,
                ClaimDocument.doc_type == doc_type
            )
            result = await session.execute(query)
            doc = result.scalar_one_or_none()
            if doc:
                result_data[doc_type] = doc.fields
            else:
                result_data[doc_type] = None  # document type not found for this claim
                logger.warning(f"[Claim {claim_id}] No document found for doc_type='{doc_type}'")
    return result_data


async def get_claimant_history(claimant_id: str) -> dict:
    """
    Fetches the prior claims history for a claimant.
    Returns a dict with total count and a list of prior claim records.
    Also computes how many claims were submitted in the last 12 months.

    Example return:
    {
        "claimant_id": "CLT-001",
        "total_prior_claims": 2,
        "claims_last_12_months": 1,
        "prior_claims": [
            {"claim_id": "CLM-000", "submitted_at": "2025-06-01", "status": "approved"},
            ...
        ]
    }
    """
    async with AsyncSessionLocal() as session:
        query = select(ClaimantHistory).where(ClaimantHistory.claimant_id == claimant_id)
        result = await session.execute(query)
        rows = result.scalars().all()

    cutoff = datetime.utcnow() - timedelta(days=365)
    prior_claims = []
    claims_last_12 = 0

    for row in rows:
        submitted_str = row.submitted_at.isoformat() if row.submitted_at else None
        prior_claims.append({
            "claim_id": row.prior_claim_id,
            "submitted_at": submitted_str,
            "status": row.status
        })
        if row.submitted_at and row.submitted_at >= cutoff:
            claims_last_12 += 1

    return {
        "claimant_id": claimant_id,
        "total_prior_claims": len(prior_claims),
        "claims_last_12_months": claims_last_12,
        "prior_claims": prior_claims
    }


async def get_policy_details(policy_id: str) -> dict:
    """
    Fetches the policy coverage details for a given policy_id.
    Returns a dict with policy start/end dates and coverage type.

    Example return:
    {
        "policy_id": "POL-123",
        "holder_name": "John Doe",
        "coverage_type": "comprehensive",
        "start_date": "2024-01-01",
        "end_date": "2026-12-31",
        "details": {...}
    }
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PolicyDetails).where(PolicyDetails.policy_id == policy_id)
        )
        policy = result.scalar_one_or_none()

    if not policy:
        logger.warning(f"[Policy {policy_id}] No policy record found in DB.")
        return {"policy_id": policy_id, "found": False}

    return {
        "policy_id": policy.policy_id,
        "found": True,
        "holder_name": policy.holder_name,
        "coverage_type": policy.coverage_type,
        "start_date": policy.start_date.isoformat() if policy.start_date else None,
        "end_date": policy.end_date.isoformat() if policy.end_date else None,
        "details": policy.details or {}
    }


# ─── REPORT OPERATIONS ────────────────────────────────────────────────────────

async def save_claim_report(
    claim_id: str,
    claimant_name: Optional[str],
    agent_results: dict,
    suggestion: str,
    overall_status: str
) -> ClaimReport:
    """
    Upserts the final claim report into the claim_reports table.
    If a report already exists for this claim_id, it is updated in place.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ClaimReport).where(ClaimReport.claim_id == claim_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.claimant_name = claimant_name
            existing.agent_results = agent_results
            existing.suggestion = suggestion
            existing.overall_status = overall_status
            existing.processed_at = datetime.utcnow()
            report = existing
        else:
            report = ClaimReport(
                claim_id=claim_id,
                claimant_name=claimant_name,
                agent_results=agent_results,
                suggestion=suggestion,
                overall_status=overall_status,
                processed_at=datetime.utcnow()
            )
            session.add(report)

        await session.commit()
        logger.info(f"[Claim {claim_id}] Report saved to DB. Overall status: {overall_status}")
        return report


async def update_claim_status(claim_id: str, status: str):
    """Updates the processing status of a claim record."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if claim:
            claim.status = status
            await session.commit()
        else:
            logger.warning(f"[Claim {claim_id}] Attempted status update but claim not found in DB.")


async def get_claim(claim_id: str) -> Optional[Claim]:
    """Fetches a Claim record by claim_id."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        return result.scalar_one_or_none()

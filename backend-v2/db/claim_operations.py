"""
claim_operations.py
───────────────────
Async database operations for the Claim Processing workflow.
Kept separate from operations.py to avoid polluting the OCR document workflow's DB layer.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from db.database import AsyncSessionLocal
from db.models import Claim, ClaimDocument, ClaimantHistory, PolicyDetails, ClaimReport, ClaimDocumentLink, Document, ExtractedData

logger = logging.getLogger(__name__)


def _gen_claim_id() -> str:
    """Generate a human-readable claim ID like CLM-2026-XXX."""
    suffix = str(uuid.uuid4().int)[:4]
    return f"CLM-{datetime.utcnow().year}-{suffix}"


def _gen_claimant_id(claimant_name: str) -> str:
    """Derive a simple claimant ID from the name."""
    slug = claimant_name.strip().replace(" ", "")[:6].upper()
    return f"CLT-{slug}-{str(uuid.uuid4().int)[:4]}"


# ─── CLAIM CRUD ───────────────────────────────────────────────────────────────

async def create_claim(
    claimant_name: str,
    claim_type: str,
    policy_number: str,
    description: Optional[str] = None,
    priority: str = "medium",
    amount: float = 0.0,
) -> Claim:
    """Creates a new Claim record. Returns the created Claim object."""
    claim_id = _gen_claim_id()
    claimant_id = _gen_claimant_id(claimant_name)

    async with AsyncSessionLocal() as session:
        claim = Claim(
            claim_id=claim_id,
            claimant_id=claimant_id,
            policy_id=policy_number,
            claimant_name=claimant_name,
            claim_type=claim_type,
            amount=amount,
            priority=priority,
            description=description,
            submitted_at=datetime.utcnow(),
            status="creating",
        )
        session.add(claim)
        await session.commit()
        await session.refresh(claim)
        logger.info(f"Created claim {claim_id} for claimant '{claimant_name}'")
        return claim


async def get_all_claims() -> list[Claim]:
    """Returns all claims ordered by created_at descending."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).order_by(Claim.created_at.desc())
        )
        return result.scalars().all()


async def get_claim_with_docs(claim_id: str) -> Optional[Claim]:
    """Returns a Claim with its ClaimDocumentLinks eagerly loaded."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        return result.scalar_one_or_none()


async def get_claim_extraction_status(claim_id: str) -> dict:
    """
    Checks how many documents linked to this claim have finished OCR.
    Returns total, completed, failed, and whether all are done (ready_to_process).
    """
    async with AsyncSessionLocal() as session:
        # Get all document links for this claim
        links_result = await session.execute(
            select(ClaimDocumentLink).where(ClaimDocumentLink.claim_id == claim_id)
        )
        links = links_result.scalars().all()

        if not links:
            return {
                "claim_id": claim_id,
                "total_docs": 0,
                "completed_docs": 0,
                "failed_docs": 0,
                "ready_to_process": False,
                "doc_statuses": []
            }

        doc_statuses = []
        completed = 0
        failed = 0

        for link in links:
            doc_result = await session.execute(
                select(Document).where(Document.id == link.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            status = doc.status if doc else "unknown"
            filename = doc.filename if doc else "unknown"

            if status == "completed":
                completed += 1
            elif status in ("failed", "rejected"):
                failed += 1

            doc_statuses.append({
                "document_id": link.document_id,
                "doc_type": doc.doc_type if doc else link.doc_type,
                "filename": filename,
                "status": status,
                "extracted": link.synced == "synced"
            })

        total = len(links)
        ready = (completed + failed) == total and completed > 0

        if ready:
            claim_result = await session.execute(select(Claim).where(Claim.claim_id == claim_id))
            claim = claim_result.scalar_one_or_none()
            if claim and claim.status == "extracting":
                claim.status = "ready"
                
                # Fetch claim_form data to populate top level fields
                for link in links:
                    doc_res = await session.execute(select(Document).where(Document.id == link.document_id))
                    doc = doc_res.scalar_one_or_none()
                    if doc and doc.doc_type in ("claim_form", "policy_document"):
                        ed_res = await session.execute(select(ExtractedData).where(ExtractedData.document_id == link.document_id))
                        extracted = ed_res.scalar_one_or_none()
                        if extracted and extracted.validated_data:
                            fields = extracted.validated_data
                            if doc.doc_type == "claim_form":
                                claimant_name = fields.get("claimant_name") or fields.get("name")
                                if claimant_name:
                                    claim.claimant_name = str(claimant_name)
                                claim_type = fields.get("claim_type") or fields.get("type")
                                if claim_type:
                                    claim.claim_type = str(claim_type)
                                amount = fields.get("amount") or fields.get("claim_amount") or fields.get("billed_amount")
                                if amount is not None:
                                    try:
                                        claim.amount = float(amount)
                                    except (ValueError, TypeError):
                                        pass
                            if doc.doc_type in ("claim_form", "policy_document"):
                                policy_num = fields.get("policy_number") or fields.get("policy_id") or fields.get("policy_num")
                                if policy_num:
                                    claim.policy_id = str(policy_num)
                await session.commit()
                logger.info(f"[Claim {claim_id}] All docs extracted — status → ready")

        return {
            "claim_id": claim_id,
            "total_docs": total,
            "completed_docs": completed,
            "failed_docs": failed,
            "ready_to_process": ready,
            "doc_statuses": doc_statuses
        }


async def link_document_to_claim(claim_id: str, document_id: str, doc_type: str) -> ClaimDocumentLink:
    """
    Creates a ClaimDocumentLink entry linking an OCR document to a claim.
    Called when a document is uploaded with a claim_id param.
    Also transitions claim status to 'extracting' if it was 'creating'.
    """
    async with AsyncSessionLocal() as session:
        link = ClaimDocumentLink(
            claim_id=claim_id,
            document_id=document_id,
            doc_type=doc_type,
            synced="pending"
        )
        session.add(link)

        # Transition claim status from creating → extracting
        claim_result = await session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()
        if claim and claim.status == "creating":
            claim.status = "extracting"

        await session.commit()
        await session.refresh(link)
        logger.info(f"Linked document {document_id} (type: {doc_type}) → claim {claim_id}")
        return link





# ─── FETCH TOOLS (called by claim tool functions) ─────────────────────────────

async def get_claim_documents_data(claim_id: str, doc_types: list[str]) -> dict:
    """
    Fetches the OCR field-value pairs for the specified document types belonging to a claim.
    Returns a dict keyed by doc_type, each containing the extracted fields.
    """
    result_data = {}
    async with AsyncSessionLocal() as session:
        for doc_type in doc_types:
            query = (
                select(ExtractedData.validated_data)
                .join(Document, Document.id == ExtractedData.document_id)
                .join(ClaimDocumentLink, ClaimDocumentLink.document_id == Document.id)
                .where(
                    ClaimDocumentLink.claim_id == claim_id,
                    Document.doc_type == doc_type
                )
            )
            result = await session.execute(query)
            fields = result.scalar_one_or_none()
            if fields:
                result_data[doc_type] = fields
            else:
                result_data[doc_type] = None
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


async def upsert_agent_result(claim_id: str, agent_key: str, result: dict) -> None:
    """
    Writes a single agent's result into ClaimReport.agent_results incrementally.
    Creates a shell ClaimReport row if one does not exist yet.
    Called after each agent activity so results are visible before the workflow finishes.
    """
    import copy
    from sqlalchemy.orm.attributes import flag_modified

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ClaimReport).where(ClaimReport.claim_id == claim_id)
        )
        report = res.scalar_one_or_none()

        if not report:
            report = ClaimReport(claim_id=claim_id, agent_results={})
            session.add(report)

        current = copy.deepcopy(report.agent_results or {})
        current[agent_key] = result
        report.agent_results = current
        flag_modified(report, "agent_results")  # force SQLAlchemy to detect JSON mutation

        await session.commit()
        logger.info(f"[Claim {claim_id}] Incremental agent result saved: {agent_key}")


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


async def delete_claim(claim_id: str) -> bool:
    """Deletes a Claim record and all its linked ClaimDocumentLinks. Returns True if deleted, False if not found."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim)
            .options(selectinload(Claim.documents), selectinload(Claim.report))
            .where(Claim.claim_id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if not claim:
            return False
        # Delete linked documents first
        from sqlalchemy import delete as sql_delete
        await session.execute(sql_delete(ClaimDocumentLink).where(ClaimDocumentLink.claim_id == claim_id))
        await session.delete(claim)
        await session.commit()
        logger.info(f"Deleted claim {claim_id} and its document links.")
        return True


"""
Batch Checklist DB Operations
=============================
Reads for the Step 3.2 checklist and the write path that decides *which* of a
batch's concurrently-running document workflows performs the evaluation.

Every document in an upload batch reaches the checklist step independently, so
without a mutex a five-file batch would fire five identical LLM calls and open
five review gates for one verdict. `claim_evaluation` is that mutex: it is won
by exactly one caller per (batch_id, signature), via the unique index on
`batch_checklists.batch_id` plus a signature-guarded conditional UPDATE.
"""

import logging

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from db.database import AsyncSessionLocal
from db.models import BatchChecklist, Document

# Documents parked behind the batch checklist. Both are released together.
GATE_STATUSES = ("checklist_hold", "awaiting_checklist_review")

logger = logging.getLogger(__name__)

# Once a batch reaches one of these the verdict is settled for that signature.
_SETTLED_STATUSES = {"complete", "incomplete", "overridden", "abandoned"}


async def get_batch_documents(batch_id: str) -> list[Document]:
    """Every document uploaded under this batch, split children included."""
    if not batch_id:
        return []
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.batch_id == batch_id)
            .where(Document.status != "deleted")
            .order_by(Document.created_at)
        )
        return list(result.scalars().all())


async def get_checklist(batch_id: str) -> BatchChecklist | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BatchChecklist).where(BatchChecklist.batch_id == batch_id)
        )
        return result.scalar_one_or_none()


async def claim_evaluation(batch_id: str, signature: str, gate_document_id: str) -> bool:
    """
    Try to become the workflow that evaluates this batch.

    Returns True to exactly one caller per (batch_id, signature). A batch whose
    contents changed since the last verdict carries a new signature and is
    re-opened — that is what lets a reviewer upload the missing documents and
    have the checklist judged again rather than replayed.
    """
    async with AsyncSessionLocal() as session:
        row = BatchChecklist(
            batch_id=batch_id,
            signature=signature,
            status="evaluating",
            gate_document_id=gate_document_id,
        )
        session.add(row)
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()

    # A row already exists. Take it over only if it was judged under a different
    # set of documents — a matching signature means the verdict already stands.
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(BatchChecklist)
            .where(BatchChecklist.batch_id == batch_id)
            .where(BatchChecklist.signature != signature)
            .where(BatchChecklist.status.in_(_SETTLED_STATUSES))
            .values(signature=signature, status="evaluating", gate_document_id=gate_document_id)
        )
        await session.commit()
        return result.rowcount > 0


async def save_evaluation(batch_id: str, result: dict, summary: str, source: str) -> None:
    """Persist the verdict produced by the workflow that won the claim."""
    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(BatchChecklist).where(BatchChecklist.batch_id == batch_id)
        )).scalar_one_or_none()
        if not row:
            logger.warning(f"[Batch {batch_id}] No checklist row to save the evaluation into")
            return

        row.status = "complete" if result["complete"] else "incomplete"
        row.required_types = result["required"]
        row.present_types = result["present"]
        row.missing_types = result["missing"]
        row.extra_types = result["extra"]
        row.unclassified = result["unclassified"]
        row.summary = summary
        row.source = source
        for field in ("required_types", "present_types", "missing_types", "extra_types", "unclassified"):
            flag_modified(row, field)
        await session.commit()


async def release_claim(batch_id: str) -> None:
    """Hand the claim back when the evaluation itself blew up, so a later
    document in the batch can retry instead of the gate silently vanishing."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(BatchChecklist)
            .where(BatchChecklist.batch_id == batch_id)
            .where(BatchChecklist.status == "evaluating")
            .values(status="abandoned", signature="")
        )
        await session.commit()


async def record_decision(batch_id: str, proceed: bool, note: str | None) -> None:
    """Close the review gate with the reviewer's answer."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(BatchChecklist)
            .where(BatchChecklist.batch_id == batch_id)
            .values(status="overridden" if proceed else "abandoned", decision_note=note)
        )
        await session.commit()


async def get_gate_documents(batch_id: str) -> list[Document]:
    """Every document in the batch currently parked behind the checklist."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.batch_id == batch_id)
            .where(Document.status.in_(GATE_STATUSES))
            .order_by(Document.created_at)
        )
        return list(result.scalars().all())


async def get_open_gate_batch_ids() -> list[str]:
    """Batches sitting at the human gate — judged incomplete and not yet released."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BatchChecklist.batch_id)
            .where(BatchChecklist.gate_opened.is_(True))
            .where(BatchChecklist.released.is_(False))
        )
        return list(result.scalars().all())


async def is_released(batch_id: str) -> bool:
    """Has this batch already been let through the gate?"""
    row = await get_checklist(batch_id)
    return bool(row and row.released)


async def mark_gate_opened(batch_id: str) -> None:
    """Record that a human gate is now open, so auto-release stops applying."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(BatchChecklist)
            .where(BatchChecklist.batch_id == batch_id)
            .values(gate_opened=True)
        )
        await session.commit()


async def mark_released(batch_id: str, mode: str, note: str | None = None) -> bool:
    """
    Flip the batch to released, exactly once.

    Guarded on `released == False` so two callers racing to release the same
    batch — an auto-release and a reviewer pressing Continue — cannot both fan
    out. Returns True to the caller that actually made the transition.
    """
    async with AsyncSessionLocal() as session:
        values = {"released": True, "release_mode": mode}
        if note is not None:
            values["decision_note"] = note
        result = await session.execute(
            update(BatchChecklist)
            .where(BatchChecklist.batch_id == batch_id)
            .where(BatchChecklist.released.is_(False))
            .values(**values)
        )
        await session.commit()
        return result.rowcount > 0


async def ensure_row(batch_id: str, gate_document_id: str | None = None) -> None:
    """Create the checklist row if the batch has never been evaluated.

    A reviewer can release a batch that never got a verdict — every document
    failed before classifying, say — and the release has to be recorded
    somewhere for the documents behind the gate to observe.
    """
    if await get_checklist(batch_id):
        return
    async with AsyncSessionLocal() as session:
        session.add(BatchChecklist(
            batch_id=batch_id, signature="", status="evaluating",
            gate_document_id=gate_document_id,
        ))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()


def serialize(row: BatchChecklist | None) -> dict | None:
    """Shape the checklist row for the API/UI."""
    if not row:
        return None
    return {
        "batch_id": row.batch_id,
        "status": row.status,
        "complete": row.status in ("complete", "overridden"),
        "required": row.required_types or [],
        "present": row.present_types or [],
        "missing": row.missing_types or [],
        "extra": row.extra_types or [],
        "unclassified": row.unclassified or [],
        "summary": row.summary,
        "source": row.source,
        "gate_document_id": row.gate_document_id,
        "decision_note": row.decision_note,
        "gate_opened": bool(row.gate_opened),
        "released": bool(row.released),
        "release_mode": row.release_mode,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }

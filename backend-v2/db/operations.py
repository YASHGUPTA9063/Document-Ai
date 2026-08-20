from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

async def update_status(document_id: str, status: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            await session.commit()

async def update_status_and_message(document_id: str, status: str, message: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            new_details = dict(doc.error_details) if doc.error_details else {}
            new_details["error"] = message
            doc.error_details = new_details
            await session.commit()

async def update_doc_type(document_id: str, doc_type: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.doc_type = doc_type
            await session.commit()

async def update_error(document_id: str, error_details: dict):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = "failed"
            doc.error_details = error_details
            await session.commit()

async def check_duplicate_filename(filename: str, exclude_id: str = None) -> str:
    """Returns document_id if duplicate filename exists, else None."""
    async with AsyncSessionLocal() as session:
        query = select(Document).where(Document.filename == filename).where(Document.status != "deleted")
        if exclude_id:
            query = query.where(Document.id != exclude_id)
        result = await session.execute(query)
        doc = result.scalars().first()
        if doc:
            return doc.id
    return None

async def get_document(document_id: str) -> Document:
    """Fetch a document by its ID."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

async def check_duplicate_hash(file_hash: str, exclude_id: str = None) -> str:
    """Returns document_id if duplicate file_hash exists, else None."""
    if not file_hash:
        return None
    async with AsyncSessionLocal() as session:
        query = select(Document).where(Document.file_hash == file_hash).where(Document.status != "deleted")
        if exclude_id:
            query = query.where(Document.id != exclude_id)
        result = await session.execute(query)
        doc = result.scalars().first()
        if doc:
            return doc.id
    return None


# ─── Multi-document packet splitting (Step 1.5) ──────────────────────────────

async def get_or_create_split_child(parent_id: str, filename: str, file_path: str,
                                    file_hash: str, page_range: str,
                                    doc_type_hint: str | None,
                                    split_confidence: float | None,
                                    customer_id: str | None,
                                    batch_id: str | None = None) -> tuple[str, bool]:
    """
    Create the Document row for one split segment.

    Keyed on (parent_document_id, page_range) so a retried fan-out activity picks
    up the children it already made instead of duplicating them. Returns
    (document_id, created).
    """
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Document)
            .where(Document.parent_document_id == parent_id)
            .where(Document.page_range == page_range)
        )
        child = existing.scalars().first()
        if child:
            return child.id, False

        child = Document(
            filename=filename,
            file_path=file_path,
            file_hash=file_hash,
            status="pending",
            customer_id=customer_id,
            parent_document_id=parent_id,
            page_range=page_range,
            split_doc_type_hint=doc_type_hint,
            split_confidence=split_confidence,
            # Children stand in for the packet on the batch checklist — the parent
            # is excluded from it, so without this a split upload would look empty.
            batch_id=batch_id,
        )
        session.add(child)
        await session.commit()
        await session.refresh(child)
        return child.id, True


async def update_workflow_run_id(document_id: str, run_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.workflow_run_id = run_id
            await session.commit()


async def mark_split_parent(document_id: str, manifest: dict, status: str = "split"):
    """Record the split outcome on the packet row and close it out."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.is_split_parent = True
            doc.split_manifest = manifest
            doc.status = status
            flag_modified(doc, "split_manifest")
            await session.commit()


async def get_split_children(parent_id: str) -> list[Document]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.parent_document_id == parent_id)
            .order_by(Document.created_at)
        )
        return list(result.scalars().all())

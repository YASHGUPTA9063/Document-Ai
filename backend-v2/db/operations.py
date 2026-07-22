from db.database import AsyncSessionLocal
from db.models import Document, ExtractedData
from sqlalchemy.future import select

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

# ─── PIPELINE CHECKPOINT OPERATIONS ──────────────────────────────────────────

from db.models import PipelineCheckpoint

async def save_checkpoint(pipeline_id: str, data: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PipelineCheckpoint).where(PipelineCheckpoint.pipeline_id == pipeline_id))
        checkpoint = result.scalar_one_or_none()
        if checkpoint:
            checkpoint.data = data
        else:
            checkpoint = PipelineCheckpoint(pipeline_id=pipeline_id, data=data)
            session.add(checkpoint)
        await session.commit()

async def load_checkpoint(pipeline_id: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PipelineCheckpoint).where(PipelineCheckpoint.pipeline_id == pipeline_id))
        checkpoint = result.scalar_one_or_none()
        return checkpoint.data if checkpoint else None

async def clear_checkpoint(pipeline_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PipelineCheckpoint).where(PipelineCheckpoint.pipeline_id == pipeline_id))
        checkpoint = result.scalar_one_or_none()
        if checkpoint:
            await session.delete(checkpoint)
            await session.commit()

async def list_checkpoints() -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PipelineCheckpoint))
        checkpoints = result.scalars().all()
        return [c.data for c in checkpoints]

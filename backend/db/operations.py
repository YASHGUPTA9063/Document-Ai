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
        query = select(Document).where(Document.filename == filename)
        if exclude_id:
            query = query.where(Document.id != exclude_id)
        result = await session.execute(query)
        doc = result.scalars().first()
        if doc:
            return doc.id
    return None

"""
kyc_operations.py
─────────────────
Async database operations for the KYC Process workflow.
Mirrors claim_operations.py structure.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from db.database import AsyncSessionLocal
from db.models import (
    KycApplication, KycDocument, KycResult,
    Document, ExtractedData,
)

logger = logging.getLogger(__name__)


def _gen_kyc_id() -> str:
    """Generate a human-readable KYC ID like KYC-2026-XXXX."""
    suffix = str(uuid.uuid4().int)[:4]
    return f"KYC-{datetime.utcnow().year}-{suffix}"


# ─── KYC APPLICATION CRUD ─────────────────────────────────────────────────────

async def create_kyc_application(
    applicant_name: Optional[str] = None,
    fathers_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    address: Optional[str] = None,
    form_source: str = "manual",
    form_document_id: Optional[str] = None,
) -> KycApplication:
    """Creates a new KYC application record. Returns the created object."""
    kyc_id = _gen_kyc_id()

    async with AsyncSessionLocal() as session:
        app = KycApplication(
            kyc_id=kyc_id,
            applicant_name=applicant_name,
            fathers_name=fathers_name,
            date_of_birth=date_of_birth,
            address=address,
            form_source=form_source,
            form_document_id=form_document_id,
            status="form_submitted",
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)
        logger.info(f"Created KYC application {kyc_id} for '{applicant_name}'")
        return app


async def get_kyc_application(kyc_id: str) -> Optional[KycApplication]:
    """Fetches a KYC application by kyc_id."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        return result.scalar_one_or_none()


async def get_all_kyc_applications() -> list[KycApplication]:
    """Returns all KYC applications ordered by created_at descending."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).order_by(KycApplication.created_at.desc())
        )
        return result.scalars().all()


async def update_kyc_status(kyc_id: str, status: str):
    """Updates the processing status of a KYC application."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        app = result.scalar_one_or_none()
        if app:
            app.status = status
            await session.commit()
        else:
            logger.warning(f"[KYC {kyc_id}] Attempted status update but application not found.")


async def update_kyc_form_data(
    kyc_id: str,
    applicant_name: Optional[str] = None,
    fathers_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    address: Optional[str] = None,
):
    """Updates the applicant form data (e.g. after OCR extraction or manual edit)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        app = result.scalar_one_or_none()
        if not app:
            return None
        if applicant_name is not None:
            app.applicant_name = applicant_name
        if fathers_name is not None:
            app.fathers_name = fathers_name
        if date_of_birth is not None:
            app.date_of_birth = date_of_birth
        if address is not None:
            app.address = address
        await session.commit()
        await session.refresh(app)
        return app


async def delete_kyc_application(kyc_id: str) -> bool:
    """Deletes a KYC application and all its linked documents/results. Returns True if deleted."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication)
            .options(selectinload(KycApplication.documents), selectinload(KycApplication.result))
            .where(KycApplication.kyc_id == kyc_id)
        )
        app = result.scalar_one_or_none()
        if not app:
            return False
        await session.delete(app)
        await session.commit()
        logger.info(f"Deleted KYC application {kyc_id} and related records.")
        return True


# ─── KYC DOCUMENT OPERATIONS ──────────────────────────────────────────────────

async def link_document_to_kyc(kyc_id: str, document_id: str, doc_type: str) -> KycDocument:
    """
    Creates a KycDocument entry linking an OCR document to a KYC application.
    Also transitions status to 'doc_uploaded' → 'extracting'.
    """
    async with AsyncSessionLocal() as session:
        kyc_doc = KycDocument(
            kyc_id=kyc_id,
            document_id=document_id,
            doc_type=doc_type,
            synced="pending",
        )
        session.add(kyc_doc)

        # Transition application status
        app_result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        app = app_result.scalar_one_or_none()
        if app and app.status in ("form_submitted", "doc_uploaded"):
            app.status = "extracting"

        await session.commit()
        await session.refresh(kyc_doc)
        logger.info(f"Linked document {document_id} (type: {doc_type}) → KYC {kyc_id}")
        return kyc_doc


async def get_kyc_doc_status(kyc_id: str) -> dict:
    """
    Checks extraction status of documents linked to this KYC application.
    Returns structured status info for the frontend.
    """
    async with AsyncSessionLocal() as session:
        app_result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        app = app_result.scalar_one_or_none()
        if not app:
            return {"kyc_id": kyc_id, "found": False}

        # Get linked KYC documents
        docs_result = await session.execute(
            select(KycDocument).where(KycDocument.kyc_id == kyc_id)
        )
        kyc_docs = docs_result.scalars().all()

        doc_statuses = []
        completed = 0
        failed = 0
        images_pending = 0

        for kyc_doc in kyc_docs:
            doc_result = await session.execute(
                select(Document).where(Document.id == kyc_doc.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            status = doc.status if doc else "unknown"
            filename = doc.filename if doc else "unknown"

            if status == "completed":
                completed += 1
            elif status in ("failed", "rejected"):
                failed += 1
            if kyc_doc.images_status == "running":
                images_pending += 1

            doc_statuses.append({
                "document_id": kyc_doc.document_id,
                "doc_type": kyc_doc.doc_type,
                "filename": filename,
                "status": status,
                "synced": kyc_doc.synced,
                "images_status": kyc_doc.images_status,
                "photo_url": kyc_doc_image_url(kyc_id, kyc_doc.document_id, "photo") if kyc_doc.photo_path else None,
                "signature_url": kyc_doc_image_url(kyc_id, kyc_doc.document_id, "signature") if kyc_doc.signature_path else None,
            })

        total = len(kyc_docs)
        all_done = total > 0 and (completed + failed) == total
        # Photo/signature crops must be finished too, otherwise verification
        # would run without the images it is supposed to compare.
        ready = all_done and completed > 0 and images_pending == 0

        # Auto-transition to 'ready' if all docs are extracted
        if ready and app.status == "extracting":
            app.status = "ready"
            await session.commit()
            logger.info(f"[KYC {kyc_id}] All docs extracted — status → ready")

        return {
            "kyc_id": kyc_id,
            "found": True,
            "status": app.status,
            "total_docs": total,
            "completed_docs": completed,
            "failed_docs": failed,
            "ready_to_verify": ready,
            "images_pending": images_pending,
            "doc_statuses": doc_statuses,
            "form_data": {
                "applicant_name": app.applicant_name,
                "fathers_name": app.fathers_name,
                "date_of_birth": app.date_of_birth,
                "address": app.address,
                "form_source": app.form_source,
            },
        }


async def sync_kyc_document_fields(kyc_id: str) -> int:
    """
    Sync OCR-extracted fields from the Document table into KycDocument.extracted_fields.
    Called after OCR completes. Returns the number of docs synced.
    """
    synced_count = 0
    async with AsyncSessionLocal() as session:
        docs_result = await session.execute(
            select(KycDocument).where(KycDocument.kyc_id == kyc_id)
        )
        kyc_docs = docs_result.scalars().all()

        for kyc_doc in kyc_docs:
            if kyc_doc.synced == "synced":
                continue

            ed_result = await session.execute(
                select(ExtractedData).where(ExtractedData.document_id == kyc_doc.document_id)
            )
            extracted = ed_result.scalar_one_or_none()

            if extracted and extracted.validated_data:
                kyc_doc.extracted_fields = extracted.validated_data
                kyc_doc.synced = "synced"
                synced_count += 1
                logger.info(f"[KYC {kyc_id}] Synced fields for doc {kyc_doc.document_id} ({kyc_doc.doc_type})")
            else:
                # Check if the Document itself failed
                doc_result = await session.execute(
                    select(Document).where(Document.id == kyc_doc.document_id)
                )
                doc = doc_result.scalar_one_or_none()
                if doc and doc.status in ("failed", "rejected"):
                    kyc_doc.synced = "failed"

        await session.commit()
    return synced_count


# ─── KYC IMAGE (PHOTO / SIGNATURE) OPERATIONS ────────────────────────────────

def kyc_form_image_url(kyc_id: str, attachment_type: str) -> str:
    return f"/api/v1/kyc/{kyc_id}/attachment/{attachment_type}"


def kyc_doc_image_url(kyc_id: str, document_id: str, attachment_type: str) -> str:
    return f"/api/v1/kyc/{kyc_id}/documents/{document_id}/attachment/{attachment_type}"


async def set_form_images(
    kyc_id: str,
    status: str,
    photo_path: Optional[str] = None,
    signature_path: Optional[str] = None,
):
    """
    Records the photo/signature cropped from the uploaded application form.
    Never overwrites an image the applicant uploaded explicitly — a manual
    upload is a better reference than a crop.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycApplication).where(KycApplication.kyc_id == kyc_id)
        )
        app = result.scalar_one_or_none()
        if not app:
            return
        app.form_images_status = status
        if photo_path and not app.photo_path:
            app.photo_path = photo_path
        if signature_path and not app.signature_path:
            app.signature_path = signature_path
        await session.commit()


async def set_doc_images(
    kyc_id: str,
    document_id: str,
    status: str,
    photo_path: Optional[str] = None,
    signature_path: Optional[str] = None,
):
    """Records the photo/signature cropped from an uploaded ID document."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycDocument).where(
                KycDocument.kyc_id == kyc_id,
                KycDocument.document_id == document_id,
            )
        )
        kyc_doc = result.scalar_one_or_none()
        if not kyc_doc:
            return
        kyc_doc.images_status = status
        if photo_path:
            kyc_doc.photo_path = photo_path
        if signature_path:
            kyc_doc.signature_path = signature_path
        await session.commit()


async def get_kyc_documents(kyc_id: str) -> list[KycDocument]:
    """Returns all identity documents linked to a KYC application, oldest first."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycDocument)
            .where(KycDocument.kyc_id == kyc_id)
            .order_by(KycDocument.created_at)
        )
        return result.scalars().all()


async def get_kyc_document(kyc_id: str, document_id: str) -> Optional[KycDocument]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycDocument).where(
                KycDocument.kyc_id == kyc_id,
                KycDocument.document_id == document_id,
            )
        )
        return result.scalar_one_or_none()


# ─── KYC RESULT OPERATIONS ────────────────────────────────────────────────────

async def save_kyc_result(
    kyc_id: str,
    form_data: dict,
    doc_data: dict,
    field_checks: list,
    overall_status: str,
    confidence: float,
    summary: str,
) -> KycResult:
    """Upserts the final KYC verification result."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycResult).where(KycResult.kyc_id == kyc_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.form_data = form_data
            existing.doc_data = doc_data
            existing.field_checks = field_checks
            existing.overall_status = overall_status
            existing.confidence = confidence
            existing.summary = summary
            existing.processed_at = datetime.utcnow()
            kyc_result = existing
        else:
            kyc_result = KycResult(
                kyc_id=kyc_id,
                form_data=form_data,
                doc_data=doc_data,
                field_checks=field_checks,
                overall_status=overall_status,
                confidence=confidence,
                summary=summary,
                processed_at=datetime.utcnow(),
            )
            session.add(kyc_result)

        await session.commit()
        logger.info(f"[KYC {kyc_id}] Result saved. Overall: {overall_status}, Confidence: {confidence}")
        return kyc_result


async def get_kyc_result(kyc_id: str) -> Optional[KycResult]:
    """Fetches the KYC verification result."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KycResult).where(KycResult.kyc_id == kyc_id)
        )
        return result.scalar_one_or_none()

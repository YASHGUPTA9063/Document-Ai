"""
activities/kyc_images.py
────────────────────────
Photo + signature extraction for the KYC flow.

Both sides of the comparison come from here:
  - the uploaded application form  → reference photo/signature on KycApplication
  - the uploaded Passport / DL     → ID photo/signature on KycDocument

Runs independently of the generic OCR pipeline (which only crops images for
templates flagged `is_kyc`), so the KYC flow always gets its images regardless
of how the document was classified.
"""
import asyncio
import logging
import os
import time

import db.kyc_operations as kyc_db
from config import settings

logger = logging.getLogger(__name__)

# How long /verify waits for a crop that is still running before giving up.
IMAGE_WAIT_TIMEOUT_S = 120
IMAGE_WAIT_POLL_S = 2


def _kyc_dir(kyc_id: str, *parts: str) -> str:
    return os.path.join(settings.STORAGE_DIR, "kyc_attachments", kyc_id, *parts)


async def _crop(file_path: str, document_id: str, output_dir: str) -> dict:
    """Runs the (blocking, Mistral-backed) extractor off the event loop."""
    from utils.signature_extractor import extract_signature_and_photo
    return await asyncio.to_thread(
        extract_signature_and_photo,
        file_path=file_path,
        document_id=document_id,
        output_dir=output_dir,
    )


async def extract_form_images(kyc_id: str, file_path: str, document_id: str) -> None:
    """Crop the applicant's photo and signature from the uploaded application form."""
    await kyc_db.set_form_images(kyc_id, "running")
    try:
        logger.info(f"[KYC {kyc_id}] Extracting photo/signature from application form {document_id}")
        res = await _crop(file_path, document_id, _kyc_dir(kyc_id, "form"))
        await kyc_db.set_form_images(
            kyc_id,
            "done",
            photo_path=res.get("photo_crop_path"),
            signature_path=res.get("signature_crop_path"),
        )
        logger.info(
            f"[KYC {kyc_id}] Form images: photo={bool(res.get('photo_crop_path'))}, "
            f"signature={bool(res.get('signature_crop_path'))}"
        )
    except Exception as e:
        logger.error(f"[KYC {kyc_id}] Form photo/signature extraction failed: {e}")
        await kyc_db.set_form_images(kyc_id, "failed")


async def extract_doc_images(kyc_id: str, file_path: str, document_id: str) -> None:
    """Crop the holder's photo and signature from an uploaded Passport / Driving License."""
    await kyc_db.set_doc_images(kyc_id, document_id, "running")
    try:
        logger.info(f"[KYC {kyc_id}] Extracting photo/signature from ID document {document_id}")
        res = await _crop(file_path, document_id, _kyc_dir(kyc_id, f"doc_{document_id}"))
        await kyc_db.set_doc_images(
            kyc_id,
            document_id,
            "done",
            photo_path=res.get("photo_crop_path"),
            signature_path=res.get("signature_crop_path"),
        )
        logger.info(
            f"[KYC {kyc_id}] ID images ({document_id}): photo={bool(res.get('photo_crop_path'))}, "
            f"signature={bool(res.get('signature_crop_path'))}"
        )
    except Exception as e:
        logger.error(f"[KYC {kyc_id}] ID photo/signature extraction failed for {document_id}: {e}")
        await kyc_db.set_doc_images(kyc_id, document_id, "failed")


async def ensure_images_ready(kyc_id: str) -> None:
    """
    Called before verification. Waits for in-flight crops to finish, and runs
    the crop inline for any document that never had one (e.g. uploaded before
    this feature existed, or a lost background task after a restart).
    """
    from db.database import AsyncSessionLocal
    from db.models import Document

    deadline = time.monotonic() + IMAGE_WAIT_TIMEOUT_S
    while True:
        app = await kyc_db.get_kyc_application(kyc_id)
        docs = await kyc_db.get_kyc_documents(kyc_id)
        running = (app and app.form_images_status == "running") or any(
            d.images_status == "running" for d in docs
        )
        if not running or time.monotonic() >= deadline:
            break
        await asyncio.sleep(IMAGE_WAIT_POLL_S)

    if running:
        logger.warning(f"[KYC {kyc_id}] Image extraction still running after {IMAGE_WAIT_TIMEOUT_S}s; verifying without it.")

    async def _file_path(document_id: str):
        async with AsyncSessionLocal() as session:
            doc = await session.get(Document, document_id)
        if doc and doc.file_path and os.path.exists(doc.file_path):
            return doc.file_path
        return None

    if (
        app and app.form_document_id and app.form_images_status is None
        and not (app.photo_path and app.signature_path)
    ):
        path = await _file_path(app.form_document_id)
        if path:
            await extract_form_images(kyc_id, path, app.form_document_id)

    for d in docs:
        if d.images_status is not None:
            continue
        path = await _file_path(d.document_id)
        if path:
            await extract_doc_images(kyc_id, path, d.document_id)

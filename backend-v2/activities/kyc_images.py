"""
activities/kyc_images.py
────────────────────────
Photo + signature extraction for the KYC flow.

Both sides of the comparison come from here:
  - the uploaded application form  → reference photo/signature on KycApplication
  - the uploaded Passport / DL     → ID photo/signature on KycDocument

Runs independently of the generic OCR pipeline (which only crops images for
templates flagged `is_kyc`), so the KYC flow always gets its images regardless
of how the document was classified. Once the pipeline has finished, any crop
it produced that ours missed is adopted (see adopt_pipeline_images).
"""
import asyncio
import base64
import logging
import os
import time

import db.kyc_operations as kyc_db
from config import settings

logger = logging.getLogger(__name__)

# How long /verify waits for a crop that is still running before giving up.
IMAGE_WAIT_TIMEOUT_S = 120
IMAGE_WAIT_POLL_S = 2

# Template whose kyc_boxes, when drawn, locate the form's photo / signature.
KYC_FORM_TYPE = "kyc_form"


def _kyc_dir(kyc_id: str, *parts: str) -> str:
    return os.path.join(settings.STORAGE_DIR, "kyc_attachments", kyc_id, *parts)


async def _crop(file_path: str, document_id: str, output_dir: str, doc_type: str = None) -> dict:
    """
    Runs the (blocking, Mistral-backed) extractor off the event loop. When the
    doc type has a template with manual kyc_boxes (passport / driving_license),
    those coordinates are used — the same crop the extraction pipeline makes.
    """
    from utils.kyc_signature_extractor import extract_signature_and_photo
    from tools.extractor import get_template_metadata
    kyc_boxes = get_template_metadata(doc_type).get("kyc_boxes") if doc_type else None
    return await asyncio.to_thread(
        extract_signature_and_photo,
        file_path=file_path,
        document_id=document_id,
        output_dir=output_dir,
        kyc_boxes=kyc_boxes,
    )


async def _extract_form_identity(kyc_id: str, file_path: str) -> None:
    """Fill the applicant's name / DOB from the form."""
    from activities.kyc_form import extract_form_identity
    try:
        ident = await asyncio.to_thread(extract_form_identity, file_path)
        await kyc_db.fill_empty_form_fields(kyc_id, **ident)
        found = [k for k, v in ident.items() if v]
        logger.info(f"[KYC {kyc_id}] Form identity fields found: {found}")
    except Exception as e:
        logger.error(f"[KYC {kyc_id}] Form identity extraction failed: {e}")


async def extract_form_images(kyc_id: str, file_path: str, document_id: str) -> None:
    """
    Process the uploaded application form: crop the applicant's photo and
    signature, and read their identity fields. form_images_status stays
    'running' until both are done so /form-status holds the review step.
    """
    await kyc_db.set_form_images(kyc_id, "running")
    try:
        logger.info(f"[KYC {kyc_id}] Extracting photo/signature/details from application form {document_id}")
        res, _ = await asyncio.gather(
            # A kyc_form template with drawn photo/signature regions gives an
            # exact crop; without one this falls back to OCR + vision detection.
            _crop(file_path, document_id, _kyc_dir(kyc_id, "form"), doc_type=KYC_FORM_TYPE),
            _extract_form_identity(kyc_id, file_path),
        )
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


async def extract_doc_images(kyc_id: str, file_path: str, document_id: str, doc_type: str = None) -> None:
    """Crop the holder's photo and signature from an uploaded ID document."""
    await kyc_db.set_doc_images(kyc_id, document_id, "running")
    try:
        logger.info(f"[KYC {kyc_id}] Extracting photo/signature from ID document {document_id} ({doc_type})")
        res = await _crop(file_path, document_id, _kyc_dir(kyc_id, f"doc_{document_id}"), doc_type)
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
            await extract_doc_images(kyc_id, path, d.document_id, d.doc_type)


def _save_b64_png(b64: str, path: str):
    try:
        if b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        path = os.path.abspath(path)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path
    except Exception as e:
        logger.warning(f"Could not save pipeline image to {path}: {e}")
        return None


def _pipeline_paths(data: dict, target, out_dir: str, override: bool = False) -> dict:
    """
    Save the pipeline's crops for whichever of photo/signature `target` lacks —
    or, with override, for any it has that isn't already the pipeline's crop.
    """
    paths = {}
    for kind in ("photo", "signature"):
        b64 = data.get(f"{kind}_image")
        current = getattr(target, f"{kind}_path")
        adopted = current and os.path.basename(current) == f"pipeline_{kind}.png"
        if b64 and (not current or (override and not adopted)):
            path = _save_b64_png(b64, os.path.join(out_dir, f"pipeline_{kind}.png"))
            if path:
                paths[kind] = path
    return paths


async def adopt_pipeline_images(kyc_id: str) -> None:
    """
    Bring in the photo/signature the extraction pipeline produced for the same
    document (base64 in validated_data). Skips anything whose own crop is still
    running, so the two can't race.

    - Application form: only fills gaps; never replaces an existing image
      (it may be the applicant's own upload).
    - ID documents: the pipeline's crop wins. It uses the template boxes of the
      type the pipeline *classified*, whereas our crop uses the type picked in
      the KYC UI — pick "Passport" for a driving license and our crop lands on
      the wrong region.
    """
    app = await kyc_db.get_kyc_application(kyc_id)
    if not app:
        return

    if app.form_document_id and app.form_images_status != "running" and not (app.photo_path and app.signature_path):
        data = await kyc_db.get_validated_data(app.form_document_id)
        paths = _pipeline_paths(data, app, _kyc_dir(kyc_id, "form"))
        if paths:
            logger.info(f"[KYC {kyc_id}] Adopted pipeline {sorted(paths)} for application form")
            await kyc_db.set_form_images(
                kyc_id, app.form_images_status or "done",
                photo_path=paths.get("photo"), signature_path=paths.get("signature"),
            )

    for d in await kyc_db.get_kyc_documents(kyc_id):
        if d.images_status == "running":
            continue
        data = await kyc_db.get_validated_data(d.document_id)
        paths = _pipeline_paths(data, d, _kyc_dir(kyc_id, f"doc_{d.document_id}"), override=True)
        if paths:
            logger.info(f"[KYC {kyc_id}] Adopted pipeline {sorted(paths)} for ID document {d.document_id}")
            await kyc_db.set_doc_images(
                kyc_id, d.document_id, d.images_status or "done",
                photo_path=paths.get("photo"), signature_path=paths.get("signature"),
            )

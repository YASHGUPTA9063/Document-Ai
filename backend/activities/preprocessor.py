import logging
import os
from pathlib import Path

import mistralai.workflows as workflows

from config import settings
import db.operations as db

logger = logging.getLogger(__name__)


@workflows.activity()
async def preprocessor_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2.5 — Preprocessing.

    Applies the following image enhancement steps (in order):
      1. Resolution Normalization — upscale low-res images (< 1000px short side)
      2. Brightness / CLAHE      — adaptive histogram equalization on L-channel
      3. Noise Removal           — light 3×3 Gaussian blur
      4. Skew Correction         — Hough line angle detection and rotation

    Skip rules:
      - DOCX files are always skipped (no pixel representation).
      - PDF files are skipped unless settings.ENABLE_PREPROCESSING_PDF is True.

    On any error, falls back to the original file so the pipeline is never blocked.

    Returns:
        {
            "preprocessed_path": str,   # cleaned image/PDF path (or original if skipped/error)
            "original_path":     str,   # original file path (untouched)
            "applied_steps":     list,  # e.g. ["resolution", "brightness", "noise_removal", "skew_correction"]
            "skipped":           bool,  # True if file type was skipped
        }
    """
    try:
        logger.info(f"[Document {document_id}] Starting preprocessing activity for: {file_path}")

        # Build output path: {STORAGE_DIR}/preprocessed/{document_id}/{basename}_preprocessed.{ext}
        path = Path(file_path)
        ext = path.suffix.lower()

        # For images we always output PNG; for PDFs we keep PDF
        output_ext = ".pdf" if ext == ".pdf" else ".png"
        output_filename = f"{path.stem}_preprocessed{output_ext}"
        output_dir = os.path.join(settings.STORAGE_DIR, "preprocessed", document_id)
        output_path = os.path.join(output_dir, output_filename)

        # Lazy import to avoid startup cost
        from utils.preprocessor import preprocess_image

        result = preprocess_image(
            file_path=file_path,
            output_path=output_path,
            preprocess_pdf=settings.ENABLE_PREPROCESSING_PDF,
        )

        if result.get("skipped"):
            logger.info(
                f"[Document {document_id}] Preprocessing skipped for '{ext}' file "
                f"(PDF toggle={settings.ENABLE_PREPROCESSING_PDF}). "
                f"Using original file path."
            )
        else:
            logger.info(
                f"[Document {document_id}] Preprocessing complete. "
                f"Steps applied: {result.get('applied_steps', [])}. "
                f"Output: {result.get('preprocessed_path')}"
            )

        return result

    except Exception as e:
        logger.error(
            f"[Document {document_id}] Preprocessing failed with error: {str(e)}. "
            f"Falling back to original file path to avoid blocking the pipeline."
        )
        # Record the error but do NOT re-raise — preprocessing failure must never kill the workflow
        await db.update_error(document_id, {"error": str(e), "stage": "preprocessor"})
        return {
            "preprocessed_path": file_path,
            "original_path": file_path,
            "applied_steps": [],
            "skipped": True,
        }

"""
Preprocessor Activity
======================
Enhances document image quality to optimize downstream OCR extraction.

Runs as a direct function call. The Preprocessing Agent only ever invoked a
single deterministic tool (`enhance_document_image`) and made no decisions of
its own, so the LLM round-trip was ~4-10s of pure latency — and it could
hallucinate output paths that didn't exist. The prompt file
(platform_core/prompts/preprocessor.md) is retained for reference but unused.
"""

import logging
import os
from pathlib import Path
import db.operations as db
from config import settings

logger = logging.getLogger(__name__)


async def preprocessor_activity(document_id: str, file_path: str) -> dict:
    """
    Step 2.5 — Preprocessing (direct call).

    Applies image enhancement steps via the enhance_document_image tool:
      1. Resolution Normalization — upscale low-res images
      2. Brightness / CLAHE — adaptive histogram equalization
      3. Noise Removal — light Gaussian blur
      4. Skew Correction — Hough line angle detection and rotation

    On any error, falls back to the original file so the pipeline is never blocked.
    """
    try:
        logger.info(f"[Document {document_id}] Starting preprocessing activity (direct mode) for: {file_path}")

        # Build output path: {STORAGE_DIR}/preprocessed/{document_id}/{basename}_preprocessed.{ext}
        path = Path(file_path)
        ext = path.suffix.lower()
        output_ext = ".pdf" if ext == ".pdf" else ".png"
        output_filename = f"{path.stem}_preprocessed{output_ext}"
        output_dir = os.path.join(settings.STORAGE_DIR, "preprocessed", document_id)
        output_path = os.path.join(output_dir, output_filename)

        from tools.preprocessor import enhance_document_image

        logger.info(f"[Document {document_id}] Executing image enhancement: {file_path} -> {output_path}")
        result = enhance_document_image(file_path=file_path, output_path=output_path)

        logger.info(
            f"[Document {document_id}] Preprocessing complete. "
            f"Applied steps: {result.get('applied_steps', [])}. "
            f"Skipped: {result.get('skipped', False)}."
        )
        return result

    except Exception as e:
        logger.error(
            f"[Document {document_id}] Preprocessing failed: {str(e)}. "
            f"Falling back to original file to avoid blocking the pipeline."
        )
        await db.update_error(document_id, {"error": str(e), "stage": "preprocessor"})
        return {
            "preprocessed_path": file_path,
            "original_path": file_path,
            "applied_steps": [],
            "skipped": True,
        }

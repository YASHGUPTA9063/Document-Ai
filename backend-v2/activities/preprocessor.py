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
    Step 2.5 — Preprocessing (Direct Function Call).

    Applies image enhancement steps (resolution normalization, brightness/CLAHE,
    noise removal, skew correction) via the enhance_document_image tool.

    Previously routed through the Preprocessing Agent, but since the agent only
    called a single deterministic tool, this now calls the tool directly
    to eliminate ~4-10s of unnecessary LLM latency.

    On any error, falls back to the original file so the pipeline is never blocked.
    """
    try:
        logger.info(f"[Document {document_id}] Starting preprocessing activity (direct mode) for: {file_path}")

        # Build output path: {STORAGE_DIR}/preprocessed/{document_id}/{basename}_preprocessed.{ext}
        path = Path(file_path)
        ext = path.suffix.lower()

        # For images we always output PNG; for PDFs we keep PDF
        output_ext = ".pdf" if ext == ".pdf" else ".png"
        output_filename = f"{path.stem}_preprocessed{output_ext}"
        output_dir = os.path.join(settings.STORAGE_DIR, "preprocessed", document_id)
        output_path = os.path.join(output_dir, output_filename)

        from tools.preprocessor import enhance_document_image

        logger.info(f"[Document {document_id}] Executing image enhancement: {file_path} -> {output_path}")
        result = enhance_document_image(
            file_path=file_path,
            output_path=output_path
        )

        logger.info(
            f"[Document {document_id}] Preprocessing complete. "
            f"Applied steps: {result.get('applied_steps', [])}. "
            f"Skipped: {result.get('skipped', False)}."
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

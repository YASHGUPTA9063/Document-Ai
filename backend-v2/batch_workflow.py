"""
batch_workflow.py
─────────────────
Mistral Workflows definition for the Multi-Document Batch Processing Pipeline.
Processes multiple documents simultaneously using the Mistral Batch API:
- Step 1: Batch Intake & Validation
- Step 2: Batch Vision Classification (directly with mistral-large-latest, no OCR)
- Step 3: Batch OCR (via /v1/ocr, extraction step only)
- Step 4: Batch Structured Field Extraction (via /v1/chat/completions with templates)
- Step 5: Batch Validation, Confidence Scoring, and Database Persistence

Workflow name: "batch_document_processing_workflow"
"""
import logging
import mistralai.workflows as workflows
from typing import List, Dict, Any

with workflows.workflow.unsafe.imports_passed_through():
    import time
    from activities.batch_activities import (
        batch_intake_activity,
        batch_classify_activity,
        batch_ocr_activity,
        batch_extract_activity,
        batch_validate_and_save_activity,
    )
    from config import settings

logger = logging.getLogger(__name__)


@workflows.workflow.define(name="batch_document_processing_workflow")
class BatchDocumentProcessingWorkflow(workflows.InteractiveWorkflow):

    @workflows.workflow.entrypoint
    async def run(self, batch_id: str, documents: List[Dict[str, Any]]) -> dict:
        """
        Executes the batch processing pipeline across all supplied documents.
        
        Args:
            batch_id: Unique identifier for the batch run (e.g. 'batch-12345').
            documents: List of document dicts, each containing:
                       - document_id (str)
                       - filename (str)
                       - file_path (str)
                       - (optional) customer_id, claim_id
        
        Returns:
            dict with batch execution summary and per-document status.
        """
        import time
        t_start_total = time.perf_counter()
        logger.info(f"🚀 [Batch {batch_id}] Starting batch workflow with {len(documents)} documents")

        # Step 1: Batch Intake
        t0 = time.perf_counter()
        intake_res = await batch_intake_activity(documents)
        valid_docs = intake_res.get("valid_documents", [])
        invalid_docs = intake_res.get("invalid_documents", [])
        t_intake = time.perf_counter() - t0
        logger.info(f"⏱️ [Batch {batch_id}] Step 1 (Intake) took: {t_intake:.2f}s ({len(valid_docs)} valid, {len(invalid_docs)} invalid)")

        if not valid_docs:
            logger.error(f"[Batch {batch_id}] No valid documents to process.")
            return {
                "status": "failed",
                "batch_id": batch_id,
                "reason": "No valid documents found in batch intake.",
                "invalid_documents": invalid_docs
            }

        # Step 2: Batch Vision Classification (No OCR)
        logger.info(f"[Batch {batch_id}] Step 2: Executing Batch Vision Classification for {len(valid_docs)} docs...")
        t0 = time.perf_counter()
        classification_res = await batch_classify_activity(valid_docs)
        t_classify = time.perf_counter() - t0
        logger.info(f"⏱️ [Batch {batch_id}] Step 2 (Vision Classification) took: {t_classify:.2f}s")

        # Step 3: Batch OCR (Extraction Step Only)
        logger.info(f"[Batch {batch_id}] Step 3: Executing Batch OCR for {len(valid_docs)} docs...")
        t0 = time.perf_counter()
        ocr_res = await batch_ocr_activity(valid_docs)
        t_ocr = time.perf_counter() - t0
        logger.info(f"⏱️ [Batch {batch_id}] Step 3 (Batch OCR) took: {t_ocr:.2f}s")

        # Step 4: Batch Structured Field Extraction
        logger.info(f"[Batch {batch_id}] Step 4: Executing Batch Field Extraction for {len(valid_docs)} docs...")
        t0 = time.perf_counter()
        extraction_res = await batch_extract_activity(valid_docs, classification_res, ocr_res)
        t_extract = time.perf_counter() - t0
        logger.info(f"⏱️ [Batch {batch_id}] Step 4 (Field Extraction) took: {t_extract:.2f}s")

        # Step 5: Batch Validation, Scoring, and Persistence
        logger.info(f"[Batch {batch_id}] Step 5: Executing Batch Validation & DB Persistence for {len(valid_docs)} docs...")
        t0 = time.perf_counter()
        summary = await batch_validate_and_save_activity(
            valid_docs,
            classification_res,
            ocr_res,
            extraction_res
        )
        t_val = time.perf_counter() - t0
        logger.info(f"⏱️ [Batch {batch_id}] Step 5 (Validation & Persistence) took: {t_val:.2f}s")

        t_total = time.perf_counter() - t_start_total
        avg_per_doc = (t_total / len(valid_docs)) if valid_docs else 0.0
        
        logger.info(
            f"🎉 [Batch {batch_id}] BATCH PIPELINE FINISHED!\n"
            f"   ├── Total Pipeline Time: {t_total:.2f}s\n"
            f"   ├── Average Time per Doc: {avg_per_doc:.2f}s/doc ({len(valid_docs)} documents)\n"
            f"   ├── Step 1 (Intake):        {t_intake:.2f}s\n"
            f"   ├── Step 2 (Classification): {t_classify:.2f}s\n"
            f"   ├── Step 3 (Batch OCR):      {t_ocr:.2f}s\n"
            f"   ├── Step 4 (Extraction):     {t_extract:.2f}s\n"
            f"   └── Step 5 (Validation/Save):{t_val:.2f}s"
        )

        return {
            "status": "completed",
            "batch_id": batch_id,
            "timing": {
                "total_seconds": round(t_total, 2),
                "avg_per_doc_seconds": round(avg_per_doc, 2),
                "step_1_intake": round(t_intake, 2),
                "step_2_classify": round(t_classify, 2),
                "step_3_ocr": round(t_ocr, 2),
                "step_4_extract": round(t_extract, 2),
                "step_5_validate_save": round(t_val, 2),
            },
            "summary": summary,
            "invalid_documents": invalid_docs
        }

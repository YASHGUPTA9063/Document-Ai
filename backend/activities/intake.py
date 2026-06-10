import logging
import mistralai.workflows as workflows
import db.operations as db
from config import settings
from utils.file_handler import list_stored_filenames

logger = logging.getLogger(__name__)

@workflows.activity()
async def intake_activity(document_id: str, filename: str) -> dict:
    try:
        # Get current document metadata to retrieve its hash
        doc = await db.get_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found in database")

        existing_id = None
        if doc.file_hash:
            logger.info(f"[Document {document_id}] Checking duplicate by hash: {doc.file_hash}")
            existing_id = await db.check_duplicate_hash(doc.file_hash, exclude_id=document_id)

        if not existing_id:
            logger.info(f"[Document {document_id}] Fallback checking duplicate by filename: {filename}")
            existing_id = await db.check_duplicate_filename(filename, exclude_id=document_id)

        if existing_id:
            return {"is_duplicate": True, "existing_document_id": existing_id}
            
        stored_files = list_stored_filenames(settings.STORAGE_DIR)
        # Note: Since the file was just uploaded in main.py, it will exist in storage.
        # However, checking storage for duplicate meaning if it was uploaded previously.
        # But wait, if it was uploaded in main.py, it's ALREADY in storage, so it will always be duplicate?
        # Actually, if main.py saves it as filename, it will exist. Let's just rely on DB for true duplicate logic,
        # or assume if there are multiple files with the same name, we can check DB.
        # For POC, DB check is enough since every upload inserts a DB record.
        
        return {"is_duplicate": False, "existing_document_id": None}
    except Exception as e:
        logger.error(f"[Document {document_id}] Intake failed: {str(e)}")
        await db.update_error(document_id, {"error": str(e), "stage": "intake"})
        raise

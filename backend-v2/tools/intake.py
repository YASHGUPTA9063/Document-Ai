import logging
import db.operations as db

logger = logging.getLogger(__name__)

# ─── TOOL SCHEMAS ───
INTAKE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_document_duplicates",
            "description": "Checks the database for existing duplicate documents by file hash or filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The unique ID of the document being processed."
                    },
                    "filename": {
                        "type": "string",
                        "description": "The name of the uploaded document file."
                    }
                },
                "required": ["document_id", "filename"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
async def check_document_duplicates(document_id: str, filename: str) -> dict:
    doc = await db.get_document(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found in database")

    existing_id = None
    if doc.file_hash:
        existing_id = await db.check_duplicate_hash(doc.file_hash, exclude_id=document_id)

    if not existing_id:
        existing_id = await db.check_duplicate_filename(filename, exclude_id=document_id)

    return {
        "is_duplicate": bool(existing_id),
        "existing_document_id": existing_id
    }

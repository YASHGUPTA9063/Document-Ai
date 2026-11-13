import os
import base64
import aiofiles
from fastapi import UploadFile

import hashlib
import uuid

async def save_file(file: UploadFile, storage_dir: str) -> tuple[str, str]:
    """
    Saves an uploaded file to the storage directory and returns (absolute_path, sha256_hash).

    Each upload gets its own file. Storing under the bare original name let a
    later upload with the same name overwrite a document still in the pipeline
    (e.g. one parked at the checklist gate, which would then resume and extract
    the newer file), and let the template-generation cleanup delete it outright.
    The original name is kept as the suffix, and is what the UI shows from
    Document.filename.
    """
    os.makedirs(storage_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload") or "upload"
    file_path = os.path.join(storage_dir, f"{uuid.uuid4().hex[:12]}_{safe_name}")
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    file_hash = hashlib.sha256(content).hexdigest()
    return os.path.abspath(file_path), file_hash

def get_file_as_base64(file_path: str) -> str:
    """Reads file and returns base64 string."""
    with open(file_path, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode('utf-8')
    return encoded_string

def delete_file(file_path: str):
    """Removes file from disk if it exists."""
    if os.path.exists(file_path):
        os.remove(file_path)

def list_stored_filenames(storage_dir: str) -> list[str]:
    """Returns all filenames currently in the storage directory."""
    if not os.path.exists(storage_dir):
        return []
    return os.listdir(storage_dir)

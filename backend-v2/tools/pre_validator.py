import os

# MIME type map by extension
MIME_MAP = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
}

# ─── TOOL SCHEMAS ───
PRE_VALIDATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_file_metadata",
            "description": "Checks the file extension, MIME type, and determines if visual representation is required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path of the document."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def get_file_metadata(file_path: str) -> dict:
    ext = os.path.splitext(file_path.lower())[1]
    mime_type = MIME_MAP.get(ext)
    is_docx = (ext == ".docx")

    return {
        "extension": ext,
        "mime_type": mime_type,
        "is_docx": is_docx,
        "is_visual": not is_docx and bool(mime_type)
    }

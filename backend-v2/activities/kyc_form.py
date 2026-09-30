"""
activities/kyc_form.py
──────────────────────
Reads the applicant's identity (name, date of birth, father's name, address)
and contact / ID details (gender, nationality, passport and driving license
numbers, email, contact number) off an uploaded KYC application form.

The generic pipeline extracts forms against their template, and a template may
not expose these as flat fields (e.g. `kyc_form` puts them in the
`personal_details` array, which the extractor's array
schema drops). This targeted pass makes sure the KYC flow always has them to
display and verify against, whatever the form's template looks like.

It runs its own OCR call rather than utils.ocr.extract_with_ocr: that one asks
for markdown tables but leaves only "[tbl-0.md](tbl-0.md)" links in the text,
and forms keep the applicant's details in tables.
"""
import json
import logging
import mimetypes
import os

from config import settings
from platform_core.adapters.resilient_mistral import get_mistral_client
from platform_core.prompts.manager import PromptManager
from utils.file_handler import get_file_as_base64
from utils.ocr import extract_with_ocr

logger = logging.getLogger(__name__)

PROMPTS = PromptManager()

IDENTITY_FIELDS = (
    "applicant_name", "date_of_birth", "fathers_name", "address",
    "gender", "nationality", "passport_number", "driving_license_number",
    "email", "contact_number",
)

_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "kyc_form_identity",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {k: {"type": ["string", "null"]} for k in IDENTITY_FIELDS},
            "required": list(IDENTITY_FIELDS),
            "additionalProperties": False,
        },
    },
}


def _ocr_text_with_tables(file_path: str) -> str:
    """OCR the form to markdown with its tables inlined where they appear."""
    if os.path.splitext(file_path.lower())[1] == ".docx":
        return extract_with_ocr(file_path=file_path, doc_type="kyc_form").get("raw_text", "")

    mime = mimetypes.guess_type(file_path)[0] or "application/pdf"
    resp = get_mistral_client().ocr.process(
        model="mistral-ocr-4-1",
        document={"type": "document_url", "document_url": f"data:{mime};base64,{get_file_as_base64(file_path)}"},
        table_format="markdown",
    )
    pages = []
    for page in resp.pages:
        markdown = page.markdown or ""
        for table in getattr(page, "tables", None) or []:
            t_id, t_content = getattr(table, "id", None), getattr(table, "content", None)
            if t_id and t_content:
                markdown = markdown.replace(f"[{t_id}]({t_id})", t_content)
        pages.append(markdown)
    return "\n\n".join(pages).strip()


def extract_form_identity(file_path: str) -> dict:
    """
    OCR the form and pull out the identity fields. Blocking (Mistral calls) —
    run it off the event loop. Returns {field: value | None}.
    """
    raw_text = _ocr_text_with_tables(file_path)
    if not raw_text.strip():
        logger.warning(f"No OCR text for KYC form {file_path}; cannot extract identity fields.")
        return {k: None for k in IDENTITY_FIELDS}

    resp = get_mistral_client().chat.complete(
        model="mistral-large-latest",
        messages=[
            {"role": "system", "content": PROMPTS.get("kyc_form_identity")},
            {"role": "user", "content": f"--- DOCUMENT TEXT ---\n{raw_text}\n--- END ---"},
        ],
        response_format=_SCHEMA,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    data = json.loads(resp.choices[0].message.content)
    return {k: (str(data[k]).strip() or None) if data.get(k) else None for k in IDENTITY_FIELDS}

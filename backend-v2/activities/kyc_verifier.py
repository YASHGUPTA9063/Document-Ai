"""
activities/kyc_verifier.py
──────────────────────────
KYC verification logic: cross-validates form data against OCR-extracted
document data using fuzzy matching + date normalization.

This is the core verification engine — called synchronously from the
/kyc/{kyc_id}/verify endpoint (no Mistral Workflow needed for the simpler
KYC flow).
"""
import logging
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ─── FIELD MATCHERS ────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip, collapse whitespace, remove titles."""
    if not name:
        return ""
    n = name.lower().strip()
    # Remove common titles/prefixes
    for title in ("mr.", "mrs.", "ms.", "dr.", "shri", "smt.", "mr ", "mrs ", "ms ", "dr "):
        if n.startswith(title):
            n = n[len(title):]
    # Collapse multiple spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def _fuzzy_name_match(name1: str, name2: str) -> tuple[str, float]:
    """
    Compare two names using fuzzy matching.
    Returns (result, score) where result is MATCH/PARTIAL/MISMATCH.
    """
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)

    if not n1 or not n2:
        return ("NOT_FOUND", 0.0)

    # Exact match after normalization
    if n1 == n2:
        return ("MATCH", 1.0)

    # Fuzzy ratio
    ratio = SequenceMatcher(None, n1, n2).ratio()

    if ratio >= 0.85:
        return ("MATCH", ratio)
    elif ratio >= 0.65:
        return ("PARTIAL", ratio)
    else:
        return ("MISMATCH", ratio)


def _normalize_date(date_str: str) -> Optional[str]:
    """
    Try to normalize a date string to YYYY-MM-DD.
    Handles common formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD.MM.YYYY, etc.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Common formats to try
    formats = [
        "%Y-%m-%d",      # 1995-03-15
        "%d/%m/%Y",      # 15/03/1995
        "%d-%m-%Y",      # 15-03-1995
        "%d.%m.%Y",      # 15.03.1995
        "%m/%d/%Y",      # 03/15/1995
        "%d %b %Y",      # 15 Mar 1995
        "%d %B %Y",      # 15 March 1995
        "%B %d, %Y",     # March 15, 1995
        "%b %d, %Y",     # Mar 15, 1995
        "%Y/%m/%d",      # 1995/03/15
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str  # Return as-is if no format matched


def _date_match(date1: str, date2: str) -> tuple[str, float]:
    """Compare two date strings. Normalizes both before comparing."""
    d1 = _normalize_date(date1)
    d2 = _normalize_date(date2)

    if not d1 or not d2:
        return ("NOT_FOUND", 0.0)

    if d1 == d2:
        return ("MATCH", 1.0)

    # Try stripping leading zeros and comparing again
    d1_stripped = re.sub(r'(\D)0(\d)', r'\1\2', d1)
    d2_stripped = re.sub(r'(\D)0(\d)', r'\1\2', d2)
    if d1_stripped == d2_stripped:
        return ("MATCH", 0.95)

    return ("MISMATCH", 0.0)


def _normalize_address(addr: str) -> str:
    """Normalize an address for comparison."""
    if not addr:
        return ""
    a = addr.lower().strip()
    # Normalize common abbreviations
    replacements = {
        "road": "rd", "street": "st", "avenue": "ave", "lane": "ln",
        "nagar": "ngr", "colony": "col", "sector": "sec",
        "m.g.": "mg", "m.g": "mg",
        ",": " ", ".": " ", "#": " ", "-": " ",
    }
    for old, new in replacements.items():
        a = a.replace(old, new)
    # Collapse whitespace
    a = re.sub(r'\s+', ' ', a).strip()
    return a


def _address_match(addr1: str, addr2: str) -> tuple[str, float]:
    """Compare two addresses using fuzzy matching."""
    a1 = _normalize_address(addr1)
    a2 = _normalize_address(addr2)

    if not a1 or not a2:
        return ("NOT_FOUND", 0.0)

    if a1 == a2:
        return ("MATCH", 1.0)

    ratio = SequenceMatcher(None, a1, a2).ratio()

    if ratio >= 0.80:
        return ("MATCH", ratio)
    elif ratio >= 0.55:
        return ("PARTIAL", ratio)
    else:
        return ("MISMATCH", ratio)


# ─── MAIN VERIFICATION FUNCTION ───────────────────────────────────────────────

def _find_field_value(data: dict, field_names: list[str]) -> Optional[str]:
    """Look up a field from extracted data by trying multiple possible key names."""
    if not data:
        return None
    for key in field_names:
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    # Also try case-insensitive lookup
    lower_data = {k.lower().replace(" ", "_"): v for k, v in data.items()}
    for key in field_names:
        val = lower_data.get(key.lower().replace(" ", "_"))
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


async def verify_kyc(form_data: dict, doc_data: dict) -> dict:
    """
    Cross-validate applicant form data against OCR-extracted document data.

    Args:
        form_data: {"applicant_name", "fathers_name", "date_of_birth", "address", "photo_image", "signature_image"}
        doc_data:  OCR-extracted fields from passport/DL (variable keys, plus "photo_image" and "signature_image")

    Returns:
        {
            "field_checks": [...],
            "overall_status": "VERIFIED" | "FAILED" | "REVIEW",
            "confidence": 0.0-100.0,
            "summary": "..."
        }
    """
    field_checks = []
    scores = []

    # 1. Name check
    form_name = form_data.get("applicant_name", "")
    doc_name = _find_field_value(doc_data, [
        "name", "full_name", "applicant_name", "holder_name",
        "Name", "Full Name", "Holder Name", "surname",
        "first_name", "given_name", "Given Name",
    ])

    name_result, name_score = _fuzzy_name_match(form_name, doc_name or "")
    field_checks.append({
        "field": "Name",
        "form_value": form_name,
        "doc_value": doc_name,
        "result": name_result,
        "score": round(name_score, 3),
    })
    if name_result != "NOT_FOUND":
        scores.append(name_score)

    # 2. Father's Name check
    form_father = form_data.get("fathers_name", "")
    doc_father = _find_field_value(doc_data, [
        "fathers_name", "father_name", "father's_name", "father",
        "Father Name", "Father's Name", "guardian_name", "parent_name",
        "s/o", "S/O", "son_of", "daughter_of", "d/o", "D/O",
    ])

    father_result, father_score = _fuzzy_name_match(form_father, doc_father or "")
    field_checks.append({
        "field": "Father's Name",
        "form_value": form_father,
        "doc_value": doc_father,
        "result": father_result,
        "score": round(father_score, 3),
    })
    if father_result != "NOT_FOUND":
        scores.append(father_score)

    # 3. DOB check
    form_dob = form_data.get("date_of_birth", "")
    doc_dob = _find_field_value(doc_data, [
        "date_of_birth", "dob", "DOB", "birth_date", "Date of Birth",
        "Date_of_Birth", "birthdate", "d.o.b", "d.o.b.",
    ])

    dob_result, dob_score = _date_match(form_dob, doc_dob or "")
    field_checks.append({
        "field": "Date of Birth",
        "form_value": form_dob,
        "doc_value": doc_dob,
        "result": dob_result,
        "score": round(dob_score, 3),
    })
    if dob_result != "NOT_FOUND":
        scores.append(dob_score)

    # 4. Address check
    form_addr = form_data.get("address", "")
    doc_addr = _find_field_value(doc_data, [
        "address", "Address", "residential_address", "permanent_address",
        "current_address", "full_address", "addr", "correspondence_address",
    ])

    addr_result, addr_score = _address_match(form_addr, doc_addr or "")
    field_checks.append({
        "field": "Address",
        "form_value": form_addr,
        "doc_value": doc_addr,
        "result": addr_result,
        "score": round(addr_score, 3),
    })
    if addr_result != "NOT_FOUND":
        scores.append(addr_score)

    # 5. Photo check
    form_photo = form_data.get("photo_image")
    doc_photo = doc_data.get("photo_image")
    if form_photo and doc_photo:
        from tools.auto_verifier import verify_face
        try:
            face_res = await verify_face("KYC_VERIFY", doc_photo, form_photo)
            face_result = "MATCH" if face_res.get("match") else "MISMATCH"
            face_score = face_res.get("confidence", 0.0)
            field_checks.append({
                "field": "Applicant Photo",
                "form_value": "[Photo Attached]",
                "doc_value": "[Photo on ID]",
                "result": face_result,
                "score": round(face_score, 3),
            })
            scores.append(face_score)
        except Exception as e:
            logger.error(f"Face verification failed in KYC: {e}")
            field_checks.append({
                "field": "Applicant Photo",
                "form_value": "[Photo Attached]",
                "doc_value": "[Photo on ID]",
                "result": "REVIEW",
                "score": 0.0,
            })
    else:
        field_checks.append({
            "field": "Applicant Photo",
            "form_value": "[Photo Attached]" if form_photo else "[Not Attached]",
            "doc_value": "[Photo on ID]" if doc_photo else "[Not Found]",
            "result": "NOT_FOUND",
            "score": 0.0,
        })

    # 6. Signature check
    form_sig = form_data.get("signature_image")
    doc_sig = doc_data.get("signature_image")
    if form_sig and doc_sig:
        from tools.auto_verifier import verify_signature
        try:
            sig_res = await verify_signature("KYC_VERIFY", doc_sig, form_sig)
            sig_result = "MATCH" if sig_res.get("match") else "MISMATCH"
            sig_score = sig_res.get("confidence", 0.0)
            field_checks.append({
                "field": "Applicant Signature",
                "form_value": "[Signature Attached]",
                "doc_value": "[Signature on ID]",
                "result": sig_result,
                "score": round(sig_score, 3),
            })
            scores.append(sig_score)
        except Exception as e:
            logger.error(f"Signature verification failed in KYC: {e}")
            field_checks.append({
                "field": "Applicant Signature",
                "form_value": "[Signature Attached]",
                "doc_value": "[Signature on ID]",
                "result": "REVIEW",
                "score": 0.0,
            })
    else:
        field_checks.append({
            "field": "Applicant Signature",
            "form_value": "[Signature Attached]" if form_sig else "[Not Attached]",
            "doc_value": "[Signature on ID]" if doc_sig else "[Not Found]",
            "result": "NOT_FOUND",
            "score": 0.0,
        })

    # ── Compute overall verdict ──
    results = [c["result"] for c in field_checks]
    has_mismatch = "MISMATCH" in results
    has_partial = "PARTIAL" in results
    has_not_found = "NOT_FOUND" in results
    match_count = results.count("MATCH")

    if has_mismatch:
        overall_status = "FAILED"
    elif has_partial or has_not_found:
        overall_status = "REVIEW"
    else:
        overall_status = "VERIFIED"

    confidence = round((sum(scores) / len(scores) * 100) if scores else 0, 1)

    # ── Generate summary ──
    summary_parts = []
    for check in field_checks:
        if check["result"] == "MATCH":
            summary_parts.append(f"✅ {check['field']}: Match confirmed")
        elif check["result"] == "PARTIAL":
            summary_parts.append(f"⚠️ {check['field']}: Partial match ({int(check['score']*100)}%)")
        elif check["result"] == "MISMATCH":
            summary_parts.append(f"❌ {check['field']}: Mismatch — form: \"{check['form_value']}\" vs document: \"{check['doc_value']}\"")
        else:
            summary_parts.append(f"❓ {check['field']}: Not found in document")

    if overall_status == "VERIFIED":
        summary = f"All {match_count} fields verified successfully. KYC verification passed with {confidence}% confidence."
    elif overall_status == "FAILED":
        mismatch_fields = [c["field"] for c in field_checks if c["result"] == "MISMATCH"]
        summary = f"KYC verification failed. Mismatches found in: {', '.join(mismatch_fields)}. Manual review required."
    else:
        summary = f"KYC verification needs review. {match_count} of {len(field_checks)} fields matched. Some fields could not be fully verified."

    summary += "\n\n" + "\n".join(summary_parts)

    return {
        "field_checks": field_checks,
        "overall_status": overall_status,
        "confidence": confidence,
        "summary": summary,
    }

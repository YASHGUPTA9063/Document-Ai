"""
activities/kyc_verifier.py
──────────────────────────
KYC verification logic: cross-validates form data against OCR-extracted
document data using fuzzy matching + date normalization.

This is the core verification engine — called synchronously from the
/kyc/{kyc_id}/verify endpoint (no Mistral Workflow needed for the simpler
KYC flow).
"""
import asyncio
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


# Key aliases seen across form templates, passports and driving licences.
NAME_KEYS = [
    "name", "full_name", "applicant_name", "holder_name", "name_of_holder",
    "card_holder_name", "customer_name", "claimant_name", "Name", "Full Name", "Holder Name",
]
GIVEN_NAME_KEYS = ["given_name", "given_names", "first_name", "Given Name", "First Name"]
MIDDLE_NAME_KEYS = ["middle_name", "Middle Name"]
SURNAME_KEYS = ["surname", "last_name", "family_name", "Surname", "Last Name"]
FATHER_KEYS = [
    "fathers_name", "father_name", "father's_name", "father", "Father Name", "Father's Name",
    "father_spouse_name", "father_or_spouse_name", "father_husband_name", "father_or_husband_name",
    "son_daughter_wife_of", "s/d/w_of", "s/d/w", "s/o", "S/O", "son_of", "d/o", "D/O", "daughter_of",
    "guardian_name", "parent_name",
]
DOB_KEYS = [
    "date_of_birth", "dob", "DOB", "birth_date", "Date of Birth",
    "Date_of_Birth", "birthdate", "d.o.b", "d.o.b.",
]
ADDRESS_KEYS = [
    "address", "Address", "residential_address", "permanent_address", "present_address",
    "current_address", "full_address", "addr", "correspondence_address",
]
ADDRESS_LINE_KEYS = ["address_line_1", "address_line_2", "address_line_3"]


def extract_identity_fields(data: dict) -> dict:
    """
    Resolve name / father's name / DOB / address from an extracted-field dict
    whose keys depend on the template (e.g. passports split given_name + surname,
    bank forms use first_name + last_name and address_line_1..3).
    """
    data = data or {}

    name = _find_field_value(data, NAME_KEYS)
    if not name:
        parts = [
            _find_field_value(data, keys)
            for keys in (GIVEN_NAME_KEYS, MIDDLE_NAME_KEYS, SURNAME_KEYS)
        ]
        name = " ".join(p for p in parts if p) or None

    address = _find_field_value(data, ADDRESS_KEYS)
    if not address:
        lines = [_find_field_value(data, [k]) for k in ADDRESS_LINE_KEYS]
        address = ", ".join(l for l in lines if l) or None

    return {
        "applicant_name": name,
        "fathers_name": _find_field_value(data, FATHER_KEYS),
        "date_of_birth": _find_field_value(data, DOB_KEYS),
        "address": address,
    }


# Face / signature pipelines return output_code 1 | 3 | 5 (see utils/face_verifier.py,
# utils/signature_verifier.py): 5 = same person / genuine, 3 = needs review, 1 = mismatch.
_OUTPUT_CODE_RESULT = {5: ("MATCH", 1.0), 3: ("PARTIAL", 0.5), 1: ("MISMATCH", 0.0)}


async def _image_check(field: str, form_label: str, doc_label: str,
                       form_img: Optional[str], doc_img: Optional[str], verify_fn) -> dict:
    """Run one photo/signature comparison and shape it as a field check."""
    check = {
        "field": field,
        "form_value": f"[{form_label} Attached]" if form_img else "[Not Attached]",
        "doc_value": f"[{doc_label} on ID]" if doc_img else "[Not Found]",
        "result": "NOT_FOUND",
        "score": 0.0,
    }
    if not (form_img and doc_img):
        return check

    try:
        res = await verify_fn("KYC_VERIFY", doc_img, form_img)
        if res.get("status") == "skipped":
            return check
        code = res.get("output_code")
        result, score = _OUTPUT_CODE_RESULT.get(code, ("PARTIAL", 0.5))
        check.update(
            result=result,
            score=score,
            verdict=res.get("verdict_label") or res.get("verdict"),
            output_code=code,
        )
    except Exception as e:
        logger.error(f"{field} verification failed in KYC: {e}")
        check.update(result="REVIEW", score=0.0, error=str(e))
    return check


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
    doc_ident = extract_identity_fields(doc_data)

    # 1. Name check
    form_name = form_data.get("applicant_name", "")
    doc_name = doc_ident["applicant_name"]

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
    doc_father = doc_ident["fathers_name"]

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
    doc_dob = doc_ident["date_of_birth"]

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
    doc_addr = doc_ident["address"]

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

    # 5 + 6. Photo and signature checks — independent, multi-agent pipelines,
    # so run them concurrently.
    from tools.auto_verifier import verify_face, verify_signature
    photo_check, sig_check = await asyncio.gather(
        _image_check("Applicant Photo", "Photo", "Photo",
                     form_data.get("photo_image"), doc_data.get("photo_image"), verify_face),
        _image_check("Applicant Signature", "Signature", "Signature",
                     form_data.get("signature_image"), doc_data.get("signature_image"), verify_signature),
    )
    for check in (photo_check, sig_check):
        field_checks.append(check)
        if check["result"] in ("MATCH", "PARTIAL", "MISMATCH"):
            scores.append(check["score"])

    # ── Compute overall verdict ──
    results = [c["result"] for c in field_checks]
    has_mismatch = "MISMATCH" in results
    has_partial = "PARTIAL" in results or "REVIEW" in results
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
        elif check["result"] == "PARTIAL" and check.get("verdict"):
            summary_parts.append(f"⚠️ {check['field']}: {check['verdict']}")
        elif check["result"] == "PARTIAL":
            summary_parts.append(f"⚠️ {check['field']}: Partial match ({int(check['score']*100)}%)")
        elif check["result"] == "REVIEW":
            summary_parts.append(f"⚠️ {check['field']}: Automated comparison failed — manual review required")
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

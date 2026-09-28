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


# Common address abbreviations, expanded so "Rd" and "Road" compare equal.
_ADDRESS_ABBREVIATIONS = {
    "rd": "road", "st": "street", "ave": "avenue", "apt": "apartment", "bldg": "building",
    "flr": "floor", "fl": "floor", "no": "number", "nr": "near", "opp": "opposite",
    "sec": "sector", "ngr": "nagar", "dist": "district", "po": "post", "ps": "police",
    "e": "east", "w": "west", "n": "north", "s": "south",
}
# Filler words that say nothing about where the address is.
_ADDRESS_NOISE = {"h", "hno", "house", "no", "number", "flat", "the", "of", "and", "at", "near", "nr", "post", "po"}
_PIN_RE = re.compile(r"\b\d{6}\b")


def _address_tokens(address: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (address or "").lower())
    # Join runs of single letters so "M.G. Road" and "MG Road" agree.
    merged, run = [], ""
    for w in words:
        if len(w) == 1 and w.isalpha():
            run += w
            continue
        if run:
            merged.append(run)
            run = ""
        merged.append(w)
    if run:
        merged.append(run)
    return {
        _ADDRESS_ABBREVIATIONS.get(w, w)
        for w in merged
        if w not in _ADDRESS_NOISE
    }


def _address_match(addr1: str, addr2: str) -> tuple[str, float]:
    """
    Compare two addresses by the words they share. IDs and forms order, abbreviate
    and punctuate addresses differently, so the score is the share of the shorter
    address's words found in the other. Differing PIN codes are a mismatch outright.
    """
    t1, t2 = _address_tokens(addr1), _address_tokens(addr2)
    if not t1 or not t2:
        return ("NOT_FOUND", 0.0)

    pins1, pins2 = set(_PIN_RE.findall(addr1)), set(_PIN_RE.findall(addr2))
    if pins1 and pins2 and not (pins1 & pins2):
        return ("MISMATCH", 0.0)

    score = len(t1 & t2) / min(len(t1), len(t2))
    if score >= 0.8:
        return ("MATCH", score)
    elif score >= 0.5:
        return ("PARTIAL", score)
    return ("MISMATCH", score)


# ─── MAIN VERIFICATION FUNCTION ───────────────────────────────────────────────

def _is_scalar(val) -> bool:
    return isinstance(val, (str, int, float)) and not isinstance(val, bool) and str(val).strip() != ""


def _find_field_value(data: dict, field_names: list[str]) -> Optional[str]:
    """Look up a field from extracted data by trying multiple possible key names."""
    if not data:
        return None
    for key in field_names:
        val = data.get(key)
        if _is_scalar(val):
            return str(val).strip()
    # Also try case-insensitive lookup
    lower_data = {k.lower().replace(" ", "_"): v for k, v in data.items()}
    for key in field_names:
        val = lower_data.get(key.lower().replace(" ", "_"))
        if _is_scalar(val):
            return str(val).strip()
    return None


_ROW_LABEL_KEYS = ("field", "label", "key", "description")
_ROW_VALUE_KEYS = ("value", "amount")


def _flatten_fields(data: dict) -> dict:
    """
    Lift values out of nested sections so templates that group identity data
    (e.g. `personal_details: {...}` or `[{"label": "Full Name", "value": ...}]`)
    resolve like flat ones. Top-level keys win over nested ones.
    """
    flat = {}

    def _put(key, val):
        if isinstance(key, str) and _is_scalar(val):
            flat.setdefault(key.strip().lower().replace(" ", "_").replace("'", ""), val)

    def _walk(node):
        if isinstance(node, dict):
            label = next((node[k] for k in _ROW_LABEL_KEYS if isinstance(node.get(k), str)), None)
            value = next((node[k] for k in _ROW_VALUE_KEYS if _is_scalar(node.get(k))), None)
            if label and value is not None:
                _put(label, value)
            for k, v in node.items():
                _put(k, v)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    for k, v in data.items():
        _put(k, v)
    _walk({k: v for k, v in data.items() if isinstance(v, (dict, list))})
    return flat


# Key aliases seen across form templates, passports and driving licences.
NAME_KEYS = [
    "name", "full_name", "applicant_name", "holder_name", "name_of_holder",
    "card_holder_name", "customer_name", "claimant_name", "Name", "Full Name", "Holder Name",
]
GIVEN_NAME_KEYS = ["given_name", "given_names", "first_name", "Given Name", "First Name"]
MIDDLE_NAME_KEYS = ["middle_name", "Middle Name"]
SURNAME_KEYS = ["surname", "last_name", "family_name", "Surname", "Last Name"]
DOB_KEYS = [
    "date_of_birth", "dob", "DOB", "birth_date", "Date of Birth",
    "Date_of_Birth", "birthdate", "d.o.b", "d.o.b.",
]
FATHERS_NAME_KEYS = [
    "fathers_name", "father_name", "father_s_name", "Father's Name", "Father Name",
    "father_or_spouse_name", "father_spouse_name", "Father/Spouse Name", "s_o", "son_of",
]
ADDRESS_KEYS = [
    "address", "permanent_address", "residential_address", "correspondence_address",
    "current_address", "Address", "Permanent Address", "Residential Address",
    "billing_address", "service_address",
]
# Where the utility_bill template (and bills in general) keep the customer's address.
UTILITY_ADDRESS_KEYS = [
    "billing_address", "service_address", "supply_address", "installation_address",
    "customer_address", "address", "Billing Address", "Service Address",
]


def extract_utility_address(fields: dict) -> Optional[str]:
    """The customer's address from a utility bill's extracted fields, as one line."""
    fields = fields or {}
    for key in UTILITY_ADDRESS_KEYS:
        val = fields.get(key)
        # Some extractions split the address into parts (street, city, postcode…).
        if isinstance(val, dict):
            joined = ", ".join(str(v).strip() for v in val.values() if _is_scalar(v))
            if joined:
                return joined
    return _find_field_value(_flatten_fields(fields), UTILITY_ADDRESS_KEYS)


def extract_identity_fields(data: dict) -> dict:
    """
    Resolve name / DOB / father's name / address from an extracted-field dict whose keys depend on the
    template (e.g. passports split given_name + surname, bank forms use
    first_name + last_name).
    """
    data = _flatten_fields(data or {})

    name = _find_field_value(data, NAME_KEYS)
    if not name:
        parts = [
            _find_field_value(data, keys)
            for keys in (GIVEN_NAME_KEYS, MIDDLE_NAME_KEYS, SURNAME_KEYS)
        ]
        name = " ".join(p for p in parts if p) or None

    return {
        "applicant_name": name,
        "date_of_birth": _find_field_value(data, DOB_KEYS),
        "fathers_name": _find_field_value(data, FATHERS_NAME_KEYS),
        "address": _find_field_value(data, ADDRESS_KEYS),
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


# Fields many IDs don't carry — missing values don't affect the verdict.
_OPTIONAL_FIELDS = {"Father's Name", "Address"}
_ADDRESS_FIELDS = {"Address"}


async def verify_kyc(form_data: dict, doc_data: dict) -> dict:
    """
    Cross-validate applicant form data against OCR-extracted document data.

    Args:
        form_data: {"applicant_name", "date_of_birth", "fathers_name", "address", "photo_image", "signature_image"}
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

    # 2. DOB check
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

    # 3. Father's name + address. Many IDs don't print them, so a value missing
    # on either side is informational and doesn't hold the verdict for review.
    for field, key, matcher in (
        ("Father's Name", "fathers_name", _fuzzy_name_match),
        ("Address", "address", _address_match),
    ):
        form_val = form_data.get(key) or ""
        doc_val = doc_ident[key]
        result, score = matcher(form_val, doc_val or "")
        field_checks.append({
            "field": field,
            "form_value": form_val,
            "doc_value": doc_val,
            "result": result,
            "score": round(score, 3),
        })
        if result != "NOT_FOUND":
            scores.append(score)

    # 4 + 5. Photo and signature checks — independent, multi-agent pipelines,
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
    verdict_results = [
        # People move — a different address needs a look, it doesn't fail the check.
        "PARTIAL" if c["field"] in _ADDRESS_FIELDS and c["result"] == "MISMATCH" else c["result"]
        for c in field_checks
        if not (c["field"] in _OPTIONAL_FIELDS and c["result"] == "NOT_FOUND")
    ]
    has_mismatch = "MISMATCH" in verdict_results
    has_partial = "PARTIAL" in verdict_results or "REVIEW" in verdict_results
    has_not_found = "NOT_FOUND" in verdict_results
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
        elif not check["form_value"]:
            summary_parts.append(f"❓ {check['field']}: Not provided on the application")
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

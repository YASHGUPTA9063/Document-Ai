"""
kyc_signature_extractor.py

Photo + signature cropping for the KYC Process flow (activities/kyc_images.py).

A KYC-only variant of utils/signature_extractor.py, which the main extraction
pipeline uses. Differences:
  - Uses OCR's native `signature` blocks, so non-raster signatures (e.g.
    script-font text on generated PDFs) are found; the shared version only
    looks at raster images.
  - The vision bbox fallback uses BBOX_VISION_MODEL instead of the retired
    pixtral-large-latest (which now returns "Invalid model").
  - The fallback gets labelled OCR text blocks as coordinate landmarks, and
    discards crops that come out blank.
  - Every page of a PDF is searched. Application forms put the applicant's
    signature on the declaration page — usually the last one — so a
    first-page-only search never finds it.
Unchanged helpers and schemas are imported from the shared module.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from mistralai.client import Mistral  # retained for type annotations only
from platform_core.adapters.resilient_mistral import get_mistral_client

from config import settings
from utils.signature_extractor import (
    BboxAnnotation,
    DocumentSignatureAnnotation,
    KycImageBboxes,
    _crop_region,
    _image_to_base64,
    _page_for_box,
    _prepare_pages,
    _resolve_raw_file_path,
    _schema,
)

logger = logging.getLogger(__name__)

# Vision model for the pixel-bbox pass. The shared extractor still uses
# pixtral-large-latest, which the Mistral API has retired.
BBOX_VISION_MODEL = "mistral-large-latest"

# Concurrent per-page OCR calls in the block pass.
MAX_PARALLEL_PAGES = 4


def _message_text(content) -> str:
    """
    Text of a chat reply. Reasoning models (mistral-large-latest included)
    return a list of chunks — a ThinkChunk then the TextChunk with the JSON —
    rather than a plain string.
    """
    if isinstance(content, str):
        return content
    parts = []
    for chunk in content or []:
        if isinstance(chunk, dict):
            if chunk.get("type") == "text":
                parts.append(chunk.get("text") or "")
        elif getattr(chunk, "type", None) == "text":
            parts.append(getattr(chunk, "text", None) or "")
    return "".join(parts)


def _is_blank(img, min_stddev: float = 4.0) -> bool:
    """True when a crop is (near-)uniform — i.e. the bbox missed the content."""
    from PIL import ImageStat
    return max(ImageStat.Stat(img.convert("L")).stddev) < min_stddev


def _locate_kyc_bboxes(
    client: Mistral,
    resolved_url: str,
    width: int,
    height: int,
    location_hint: Optional[str] = None,
    landmarks: Optional[list] = None,
) -> Optional[KycImageBboxes]:
    """
    Second-pass vision call to BBOX_VISION_MODEL.
    Returns pixel-precise bounding boxes for BOTH signature AND photo.
    """
    landmarks_str = ""
    if landmarks:
        landmarks_str = (
            "Here are the pixel coordinates of reference regions detected by OCR "
            "to help you calibrate your coordinate space:\n"
            + "\n".join(landmarks)
            + "\n"
        )

    hint_str = ""
    if location_hint:
        hint_str = (
            f" The OCR system suggests the signature might be near: '{location_hint}'."
        )

    prompt = (
        f"You are a document analysis assistant specializing in locating handwritten elements.\n"
        f"The image dimensions are {width}x{height} pixels.\n"
        f"{landmarks_str}"
        f"{hint_str}\n"
        f"Your task: locate up to TWO regions in this document image:\n\n"
        f"1. **SIGNATURE** — any handwritten cursive mark, scrawl, initials, or name written "
        f"by hand (typically in blue or black ink). It is NOT printed/typed text, NOT a stamp, "
        f"NOT a logo. It may appear near words like 'Signature', 'Sign', 'Authorized by', "
        f"'हस्ताक्षर', or at the bottom of the document near a date. "
        f"Capture the full extent of all handwriting strokes. "
        f"Do NOT include the printed label itself in the bounding box.\n\n"
        f"2. **PHOTO** — a face photograph of a person (passport-style or otherwise). "
        f"It is a rectangular image of a human head/shoulders. It is NOT an emblem, "
        f"NOT a QR code, NOT text. If no photo is present, set photo_found to false.\n\n"
        f"Guidelines:\n"
        f"- Use the OCR region coordinates above to calibrate your coordinate space.\n"
        f"- Return x1 (left), y1 (top), x2 (right), y2 (bottom) as integer pixel coordinates "
        f"on the original {width}x{height} image.\n"
        f"- Crop tightly — do not include surrounding whitespace or labels.\n"
        f"- If a region is not present, set its _found field to false and coordinates to null."
    )

    try:
        response = client.chat.complete(
            model=BBOX_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": resolved_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "KycImageBboxes",
                    "schema": KycImageBboxes.model_json_schema(),
                    "strict": True,
                },
            },
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        raw = response.choices[0].message.content
        d = dict(raw) if isinstance(raw, dict) else json.loads(_message_text(raw))
        bboxes = KycImageBboxes(**d)

        logger.info(
            f"  Vision bbox result: signature_found={bboxes.signature_found} "
            f"({bboxes.sig_x1},{bboxes.sig_y1})->({bboxes.sig_x2},{bboxes.sig_y2}) | "
            f"photo_found={bboxes.photo_found} "
            f"({bboxes.photo_x1},{bboxes.photo_y1})->({bboxes.photo_x2},{bboxes.photo_y2})"
        )
        if bboxes.step_by_step_analysis:
            logger.debug(f"  Pixtral analysis: {bboxes.step_by_step_analysis}")

        return bboxes
    except Exception as e:
        logger.error(f"  Vision bbox call failed: {e}")
        return None


# ─── Small helpers ──────────────────────────────────────────────────────────

def _empty_result() -> dict:
    return {
        "has_signature": False,
        "signature_crop_path": None,
        "signature_base64": None,
        "signature_bbox": None,
        "has_photo": False,
        "photo_crop_path": None,
        "photo_base64": None,
        "photo_bbox": None,
        "confidence": "low",
        "signer_name": None,
    }


def _found_all(result: dict) -> bool:
    return result["has_signature"] and result["has_photo"]


def _coords(obj) -> Optional[tuple]:
    c = tuple(getattr(obj, a, None) for a in ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"))
    return None if None in c else c


def _annotated_type(img_obj) -> Optional[str]:
    """block_type from an OCR image's BboxAnnotation (JSON string or dict)."""
    annotation = getattr(img_obj, "image_annotation", None)
    if isinstance(annotation, str):
        try:
            annotation = json.loads(annotation)
        except Exception:
            return None
    return annotation.get("block_type") if isinstance(annotation, dict) else None


def _save_crop(result: dict, kind: str, cropped, bbox: tuple, output_dir: str) -> str:
    """Record a signature/photo crop on `result` and write it to disk."""
    x1, y1, x2, y2 = bbox
    path = os.path.join(output_dir, f"{kind}.png")
    cropped.save(path)
    result[f"has_{kind}"] = True
    result[f"{kind}_bbox"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    result[f"{kind}_crop_path"] = os.path.abspath(path)
    result[f"{kind}_base64"] = _image_to_base64(cropped)
    return path


# ─── PATH 1: template-level manual coordinates ──────────────────────────────

def _crop_manual_boxes(pages: list, kyc_boxes: dict, result: dict, output_dir: str, document_id: str) -> None:
    """
    Coordinates are percentages (0-100) of the page image — page 1 unless the
    box carries a 1-based `page`. No API calls.
    """
    for kind in ("signature", "photo"):
        box = kyc_boxes.get(kind)
        if not box:
            continue
        img = _page_for_box(pages, box)
        width, height = img.size
        bbox = (
            int(box["x1"] / 100.0 * width),
            int(box["y1"] / 100.0 * height),
            int(box["x2"] / 100.0 * width),
            int(box["y2"] / 100.0 * height),
        )
        logger.info(f"[Document {document_id}] {kind.capitalize()} manual bbox: {bbox} from pct ({box})")
        cropped = _crop_region(img, *bbox)
        if not cropped:
            logger.warning(f"[Document {document_id}] {kind.capitalize()} crop returned empty region")
            continue
        path = _save_crop(result, kind, cropped, bbox, output_dir)
        if kind == "signature":
            result["confidence"] = "high"
        logger.info(f"[Document {document_id}] {kind.capitalize()} crop saved (manual): {path}")


# ─── PATH 2: Mistral OCR block & image annotations ──────────────────────────

def _ocr_blocks(client: Mistral, resolved_url: str):
    return client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": resolved_url},
        include_blocks=True,
        include_image_base64=True,
        bbox_annotation_format=_schema(BboxAnnotation),
    )


def _take_from_ocr_blocks(ocr_response, img, result: dict, output_dir: str, document_id: str, page_no: int) -> None:
    """Crop whatever `result` still lacks from one page's OCR blocks/images."""
    for page in getattr(ocr_response, "pages", []) or []:
        # Native signature blocks first: OCR tags signatures it recognises
        # as block.type == "signature" even when they aren't raster images
        # (e.g. vector / script-font signatures on generated PDFs), which
        # the image search below can never find.
        if not result["has_signature"]:
            for block in getattr(page, "blocks", []) or []:
                if getattr(block, "type", None) != "signature" or not _coords(block):
                    continue
                cropped = _crop_region(img, *_coords(block))
                if cropped:
                    _save_crop(result, "signature", cropped, _coords(block), output_dir)
                    result["confidence"] = "high"
                    logger.info(f"[Document {document_id}] Path 2: Signature extracted from OCR signature block on page {page_no}: {_coords(block)}")
                    break

        # Then images annotated by BboxAnnotation. NOTE: Mistral OCR stores
        # the custom annotation in image_annotation, NOT the block `.type`.
        for img_obj in getattr(page, "images", []) or []:
            kind = _annotated_type(img_obj)
            if kind not in ("signature", "photo") or result[f"has_{kind}"] or not _coords(img_obj):
                continue
            cropped = _crop_region(img, *_coords(img_obj))
            if cropped:
                _save_crop(result, kind, cropped, _coords(img_obj), output_dir)
                if kind == "signature":
                    result["confidence"] = "high"
                logger.info(f"[Document {document_id}] Path 2: {kind.capitalize()} extracted from annotated image on page {page_no}: {_coords(img_obj)}")


# ─── FALLBACK: OCR document annotation + vision bboxes ──────────────────────

def _vision_fallback(
    client: Mistral, img, resolved_url: str, result: dict, output_dir: str,
    document_id: str, page_no: int, multi_page: bool,
) -> None:
    """Pass 1 (OCR document_annotation + landmarks) and Pass 2 (vision bboxes) on one page."""
    width, height = img.size

    # ── Pass 1: Document annotation via Mistral OCR ──────────────────────
    logger.info(f"[Document {document_id}] KYC Pass 1: Running document_annotation on page {page_no}...")
    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": resolved_url},
            include_image_base64=False,
            include_blocks=True,
            document_annotation_format=_schema(DocumentSignatureAnnotation),
        )
    except Exception as e:
        logger.error(f"[Document {document_id}] OCR document_annotation failed on page {page_no}: {e}")
        return

    # Collect OCR-detected image region bboxes as landmarks
    ocr_bboxes = []
    ocr_image_count = 0
    for page in getattr(ocr_response, "pages", []) or []:
        page_images = getattr(page, "images", []) or []
        ocr_image_count += len(page_images)
        ocr_bboxes.extend(page_images)
        # Labelled text blocks give the vision model far better coordinate
        # anchors than image regions alone (e.g. "SIGNATURE OF ACCOUNT HOLDER").
        ocr_bboxes.extend(
            b for b in (getattr(page, "blocks", []) or [])
            if (getattr(b, "content", "") or "").strip()
        )
    logger.info(f"[Document {document_id}] OCR detected {len(ocr_bboxes)} region(s) on page {page_no}.")

    # Parse document_annotation
    raw_annotation = getattr(ocr_response, "document_annotation", None)
    annotation = None
    if raw_annotation:
        try:
            d = json.loads(raw_annotation) if isinstance(raw_annotation, str) else dict(raw_annotation)
            annotation = DocumentSignatureAnnotation(**d)
        except Exception as e:
            logger.warning(f"[Document {document_id}] Failed to parse document_annotation: {e}")

    if annotation:
        if not result["has_signature"]:
            result["confidence"] = annotation.confidence
        result["signer_name"] = result["signer_name"] or annotation.signer_name
        logger.info(
            f"[Document {document_id}] Annotation (page {page_no}): has_signature={annotation.has_signature}, "
            f"confidence={annotation.confidence}, location={annotation.signature_location}"
        )

    # ── Pass 2: vision model for pixel-precise bboxes ────────────────────
    logger.info(f"[Document {document_id}] KYC Pass 2: Calling {BBOX_VISION_MODEL} on page {page_no}...")

    landmarks = []
    for idx, item in enumerate(ocr_bboxes):
        c = _coords(item)
        bid = getattr(item, "id", "")
        text = " ".join((getattr(item, "content", "") or "").split())[:60]
        label = f'text "{text}"' if text else (bid or f"Region {idx+1}")
        if c:
            landmarks.append(f"- {label}: ({c[0]}, {c[1]}) to ({c[2]}, {c[3]})")

    bboxes = _locate_kyc_bboxes(
        client, resolved_url, width, height,
        location_hint=annotation.signature_location if annotation else None,
        landmarks=landmarks,
    )
    if not bboxes:
        logger.warning(f"[Document {document_id}] Vision bbox call returned no results for page {page_no}.")
        return

    candidates = {
        "signature": bboxes.signature_found and (bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2),
        "photo": bboxes.photo_found and (bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2),
    }
    # On a multi-page form, most pages are filled-in fields: script fonts and
    # ink look handwritten, and the vision model will "find" a photo in a page
    # that has none. Take a vision result only from a page OCR backs up — it
    # didn't rule out a signature there, and it saw an image where a photo
    # would be (a printed photo is always an image region to OCR).
    if multi_page and candidates["signature"] and annotation and not annotation.has_signature:
        logger.info(f"[Document {document_id}] Ignoring vision signature on page {page_no}: OCR found no signature there.")
        candidates["signature"] = None
    if multi_page and candidates["photo"] and not ocr_image_count:
        logger.info(f"[Document {document_id}] Ignoring vision photo on page {page_no}: OCR found no image there.")
        candidates["photo"] = None

    for kind, bbox in candidates.items():
        if result[f"has_{kind}"] or not bbox or None in bbox:
            continue
        cropped = _crop_region(img, *bbox)
        if cropped and _is_blank(cropped):
            # Vision-model pixel boxes can land on empty space — a blank crop
            # would be compared as if it were the real image, so drop it.
            logger.warning(f"[Document {document_id}] Vision {kind} bbox on page {page_no} is blank; discarding.")
        elif cropped:
            path = _save_crop(result, kind, cropped, bbox, output_dir)
            logger.info(f"[Document {document_id}] {kind.capitalize()} crop saved from page {page_no}: {path}")


# ─── Entry point ────────────────────────────────────────────────────────────

def extract_signature_and_photo(
    file_path: str,
    document_id: str,
    output_dir: str = None,
    kyc_boxes: dict = None,
) -> dict:
    """
    KYC image extraction with optional template-level manual coordinates.

    If `kyc_boxes` is provided (e.g. {"signature": {"x1":40,"y1":80,"x2":95,"y2":95}, ...}),
    coordinates are treated as percentages (0-100) of the image dimensions. The image is
    cropped directly — no Mistral API calls needed. This gives 100% reliable extraction.

    Otherwise every page (up to MAX_KYC_PAGES) is searched:
      Path 2:   mistral-ocr-latest blocks/annotations on all pages (in parallel)
      Fallback: for whatever is still missing, page by page —
                OCR document_annotation + landmarks, then BBOX_VISION_MODEL bboxes
    Then crop using Pillow, save to disk, and return base64.

    Returns:
    {
        "has_signature": bool,
        "signature_crop_path": str | None,
        "signature_base64": str | None,
        "signature_bbox": dict | None,
        "has_photo": bool,
        "photo_crop_path": str | None,
        "photo_base64": str | None,
        "photo_bbox": dict | None,
        "confidence": str,
        "signer_name": str | None,
    }
    """
    client = get_mistral_client()

    if output_dir is None:
        output_dir = os.path.join(settings.STORAGE_DIR, "crops", document_id)
    os.makedirs(output_dir, exist_ok=True)

    result = _empty_result()

    # ── Prepare page images ──────────────────────────────────────────────
    try:
        pages = _prepare_pages(_resolve_raw_file_path(file_path))
    except Exception as e:
        logger.error(f"[Document {document_id}] Failed to prepare image: {e}")
        return result
    if not pages:
        logger.error(f"[Document {document_id}] Document has no pages.")
        return result
    multi_page = len(pages) > 1

    # ══ PATH 1: Template-level manual coordinates (HIGHEST PRIORITY) ══════
    if kyc_boxes:
        logger.info(f"[Document {document_id}] Using MANUAL template coordinates for extraction (no API calls)")
        _crop_manual_boxes(pages, kyc_boxes, result, output_dir, document_id)
        return result

    # ══ PATH 2: OCR block & image annotations, every page ═════════════════
    logger.info(f"[Document {document_id}] KYC Path 2: Running Mistral OCR block extraction on {len(pages)} page(s)...")

    def _ocr_page(page):
        try:
            return _ocr_blocks(client, page[1]), None
        except Exception as e:
            return None, e

    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_PAGES, len(pages))) as pool:
        ocr_results = list(pool.map(_ocr_page, pages))

    # Pages are read in order, so the earliest page with a match wins.
    for page_no, ((img, _), (ocr_response, err)) in enumerate(zip(pages, ocr_results), 1):
        if err is not None:
            logger.error(f"[Document {document_id}] Path 2 failed on page {page_no}: {err}")
            continue
        _take_from_ocr_blocks(ocr_response, img, result, output_dir, document_id, page_no)

    if _found_all(result):
        logger.info(f"[Document {document_id}] Path 2 found both signature and photo. Returning result.")
        return result
    # ID cards often yield the photo here but not the signature (or vice
    # versa) — fall back for whatever is missing, keeping what was found.
    logger.info(
        f"[Document {document_id}] Path 2 partial (signature={result['has_signature']}, "
        f"photo={result['has_photo']}). Falling back for the missing region(s)..."
    )

    # ══ FALLBACK: OCR annotation + vision bboxes, page by page ════════════
    for page_no, (img, resolved_url) in enumerate(pages, 1):
        if _found_all(result):
            break
        _vision_fallback(client, img, resolved_url, result, output_dir, document_id, page_no, multi_page)

    return result

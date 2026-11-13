"""
kyc_signature_extractor.py

Photo + signature cropping for the KYC Process flow (activities/kyc_images.py).

A KYC-only variant of utils/signature_extractor.py, which the main extraction
pipeline uses and which is left untouched. Differences:
  - Uses OCR's native `signature` blocks, so non-raster signatures (e.g.
    script-font text on generated PDFs) are found; the shared version only
    looks at raster images.
  - The vision bbox fallback uses BBOX_VISION_MODEL instead of the retired
    pixtral-large-latest (which now returns "Invalid model").
  - The fallback gets labelled OCR text blocks as coordinate landmarks, and
    discards crops that come out blank.
Unchanged helpers and schemas are imported from the shared module.
"""

import json
import logging
import math
import os
import re
from typing import Optional

from mistralai.client import Mistral  # retained for type annotations only
from platform_core.adapters.resilient_mistral import get_mistral_client
from platform_core.agent_loop import _parse_json_response

from config import settings
from utils.signature_extractor import (
    BboxAnnotation,
    DocumentSignatureAnnotation,
    KycImageBboxes,
    _crop_region,
    _image_to_base64,
    _prepare_image_and_url,
    _resolve_raw_file_path,
    _schema,
)

logger = logging.getLogger(__name__)

# Vision model for the pixel-bbox pass (LLM_VISION_MODEL, mistral-large-latest
# by default). The shared extractor still uses pixtral-large-latest, which the
# Mistral API has retired.
BBOX_VISION_MODEL = settings.LLM_VISION_MODEL


def _is_blank(img, min_stddev: float = 4.0) -> bool:
    """True when a crop is (near-)uniform — i.e. the bbox missed the content."""
    from PIL import ImageStat
    return max(ImageStat.Stat(img.convert("L")).stddev) < min_stddev


# ─── Layout-based location (application forms) ─────────────────────────────
# OCR returns exact boxes for every text block and embedded image. On a form the
# photo and signature sit next to printed labels ("Applicant Photo", "Signature
# of Applicant"), so the region beside the label is the answer — no coordinate
# guessing. The vision model's pixel boxes vary from run to run and often cover
# only half the signature or photo, so they are kept as the last resort only.

_SIG_LABEL = re.compile(r"\bsign(?:ature|ed)?\b|हस्ताक्षर", re.IGNORECASE)
_PHOTO_LABEL = re.compile(r"\b(?:photo(?:graph)?|picture)\b", re.IGNORECASE)
_DATE_VALUE = re.compile(r"\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}")
_NON_CONTENT_BLOCKS = {"title", "header", "footer", "page_number"}
_MAX_LABEL_LEN = 60  # a label is a short caption, not a paragraph mentioning "signature"


def _coords(obj) -> Optional[tuple]:
    box = tuple(getattr(obj, a, None) for a in ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"))
    return None if None in box else box


def _annotation_type(img_obj) -> Optional[str]:
    """The BboxAnnotation block_type OCR attached to an embedded image, if any."""
    ann = getattr(img_obj, "image_annotation", None)
    if isinstance(ann, str):
        try:
            ann = json.loads(ann)
        except Exception:
            return None
    return ann.get("block_type") if isinstance(ann, dict) else None


def _nearest_to_label(label: tuple, candidates: list, page_h: float) -> Optional[tuple]:
    """
    The candidate box sitting right below, right of, or just above `label`.

    Below / right are preferred (the usual "Signature: ____" and
    "Signature\\n____" layouts); above covers a caption printed under the line.
    """
    lx1, ly1, lx2, ly2 = label
    lh = max(1, ly2 - ly1)
    tol = lh * 0.5
    reach_x2 = lx2 + (lx2 - lx1)  # the field can run past the end of its label
    best, best_score = None, None
    for box in candidates:
        cx1, cy1, cx2, cy2 = box
        x_overlap = min(reach_x2, cx2) - max(lx1, cx1) > 0
        y_overlap = min(ly2, cy2) - max(ly1, cy1) > 0
        if cy1 >= ly2 - tol and x_overlap:
            score = cy1 - ly2
        elif cx1 >= lx2 - tol and y_overlap:
            score = cx1 - lx2
        elif cy2 <= ly1 + tol and x_overlap:
            score = (ly1 - cy2) * 1.5
        else:
            continue
        if score > page_h * 0.25:
            continue
        if best_score is None or score < best_score:
            best, best_score = box, score
    return best


def _locate_from_layout(page, img_w: int, img_h: int) -> dict:
    """
    Find the photo and signature on one OCR page from its layout.
    Returns {"photo": box | None, "signature": box | None} in image pixels.
    """
    dims = getattr(page, "dimensions", None)
    sx = img_w / dims.width if dims and getattr(dims, "width", None) else 1.0
    sy = img_h / dims.height if dims and getattr(dims, "height", None) else 1.0

    def scaled(box):
        x1, y1, x2, y2 = box
        return (round(x1 * sx), round(y1 * sy), round(x2 * sx), round(y2 * sy))

    blocks = [b for b in (getattr(page, "blocks", None) or []) if _coords(b)]
    images = [(scaled(_coords(i)), i) for i in (getattr(page, "images", None) or []) if _coords(i)]

    def is_label(block, pattern):
        text = (getattr(block, "content", "") or "").strip()
        return bool(text) and len(text) <= _MAX_LABEL_LEN and bool(pattern.search(text)) \
            and getattr(block, "type", "text") == "text"

    found = {"photo": None, "signature": None}

    # Signature: OCR's own signature block, else whatever sits at the label.
    native = [scaled(_coords(b)) for b in blocks if getattr(b, "type", None) == "signature"]
    sig_labels = [b for b in blocks if is_label(b, _SIG_LABEL)]
    if native:
        found["signature"] = native[0]
    elif sig_labels:
        candidates = []
        for b in blocks:
            text = (getattr(b, "content", "") or "").strip()
            if (b in sig_labels or getattr(b, "type", None) in _NON_CONTENT_BLOCKS
                    or text.endswith(":") or _DATE_VALUE.search(text) or _PHOTO_LABEL.search(text)):
                continue
            box = scaled(_coords(b))
            # An embedded image is listed both as a block and in page.images;
            # the images list decides below which of them is the photo.
            candidates.append(box)
        for label in sig_labels:
            lbox = scaled(_coords(label))
            box = _nearest_to_label(lbox, candidates, img_h)
            if box:
                # Handwriting strays outside the OCR box — pad it, but never
                # into the label it was found from.
                x1, y1, x2, y2 = box
                px, py = round((x2 - x1) * 0.04), round((y2 - y1) * 0.15)
                x1, y1, x2, y2 = x1 - px, y1 - py, x2 + px, y2 + py
                if box[1] >= lbox[3] - 1:      # found below the label
                    y1 = max(y1, lbox[3])
                elif box[0] >= lbox[2] - 1:    # found right of the label
                    x1 = max(x1, lbox[2])
                elif box[3] <= lbox[1] + 1:    # found above the label
                    y2 = min(y2, lbox[1])
                found["signature"] = (x1, y1, x2, y2)
                break

    # Photo: an embedded image — the one OCR tagged as a photo, else the one at
    # a "photo" label, else the only portrait-shaped image of a sensible size.
    sig = found["signature"]
    photos = [(box, i) for box, i in images if not (sig and box == sig)]
    tagged = [box for box, i in photos if _annotation_type(i) == "photo"]
    if tagged:
        found["photo"] = tagged[0]
    elif photos:
        photo_labels = [scaled(_coords(b)) for b in blocks if is_label(b, _PHOTO_LABEL)]
        for lbox in photo_labels:
            box = _nearest_to_label(lbox, [b for b, _ in photos], img_h)
            if box:
                found["photo"] = box
                break
        if not found["photo"]:
            def portrait(b):
                w, h = b[2] - b[0], b[3] - b[1]
                return w > 0 and 0.8 <= h / w <= 2.0 and w * h >= 0.005 * img_w * img_h
            shaped = [b for b, _ in photos if portrait(b)]
            if len(shaped) == 1:
                found["photo"] = shaped[0]
    return found


def _pct_box_to_px(pct: dict, width: int, height: int) -> tuple:
    """
    A template box in percent of the image (0-100, as drawn in the Templates
    page) → pixel box on this image. Rounded outward so the drawn area is never
    trimmed; _crop_region clamps to the image.
    """
    x1, y1, x2, y2 = (float(pct[k]) for k in ("x1", "y1", "x2", "y2"))
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    return (
        math.floor(x1 / 100.0 * width), math.floor(y1 / 100.0 * height),
        math.ceil(x2 / 100.0 * width), math.ceil(y2 / 100.0 * height),
    )


def _store_crop(result: dict, kind: str, img, box: tuple, output_dir: str, document_id: str, how: str) -> bool:
    """Crop `box` from `img` into result[...] for kind = "photo" | "signature"."""
    cropped = _crop_region(img, *box)
    if not cropped or _is_blank(cropped):
        logger.warning(f"[Document {document_id}] {how} {kind} box {box} is empty/blank; discarding.")
        return False
    path = os.path.join(output_dir, f"{kind}.png")
    cropped.save(path)
    x1, y1, x2, y2 = box
    result[f"has_{kind}"] = True
    result[f"{kind}_bbox"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    result[f"{kind}_crop_path"] = os.path.abspath(path)
    result[f"{kind}_base64"] = _image_to_base64(cropped)
    if kind == "signature":
        result["confidence"] = "high"
    logger.info(f"[Document {document_id}] {kind.capitalize()} located from {how}: {box}")
    return True


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
        # Reasoning models return content as [ThinkChunk, TextChunk], not a str.
        d = _parse_json_response(response.choices[0].message.content)
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


def extract_signature_and_photo(
    file_path: str,
    document_id: str,
    output_dir: str = None,
    kyc_boxes: dict = None,
    prefer_layout: bool = False,
) -> dict:
    """
    KYC image extraction with optional template-level manual coordinates.

    `prefer_layout` (application forms): locate the photo and signature from the
    OCR layout — the embedded image and the block at the "Signature" label —
    before trying annotations or the vision model. ID documents leave it off.

    If `kyc_boxes` is provided (e.g. {"signature": {"x1":40,"y1":80,"x2":95,"y2":95}, ...}),
    coordinates are treated as percentages (0-100) of the image dimensions. The image is
    cropped directly — no Mistral API calls needed. This gives 100% reliable extraction.

    If `kyc_boxes` is None, falls back to the two-pass approach:
      Pass 1: mistral-ocr-latest with document_annotation → detect signature + get OCR landmarks
      Pass 2: BBOX_VISION_MODEL → pixel-precise bboxes for signature AND photo
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
    from PIL import Image

    client = get_mistral_client()

    # Default output dir
    if output_dir is None:
        output_dir = os.path.join(settings.STORAGE_DIR, "crops", document_id)
    os.makedirs(output_dir, exist_ok=True)

    result = {
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

    # ── Prepare Image ────────────────────────────────────────────────────
    try:
        target_file_path = _resolve_raw_file_path(file_path)
        img, resolved_url = _prepare_image_and_url(target_file_path)
        width, height = img.size
    except Exception as e:
        logger.error(f"[Document {document_id}] Failed to prepare image: {e}")
        return result

    # ══════════════════════════════════════════════════════════════════════
    # PATH 1: Template-level manual coordinates (HIGHEST PRIORITY)
    # When the user explicitly defines signature/photo boundaries on the
    # template, always honour them first — no API calls needed.
    # ══════════════════════════════════════════════════════════════════════
    if kyc_boxes:
        logger.info(
            f"[Document {document_id}] Using MANUAL template coordinates on the "
            f"{width}x{height} image: {kyc_boxes}"
        )
        for kind in ("signature", "photo"):
            pct = kyc_boxes.get(kind)
            if not pct:
                continue
            try:
                box = _pct_box_to_px(pct, width, height)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"[Document {document_id}] Ignoring malformed template {kind} box {pct}: {e}")
                continue
            # Exactly what was drawn — no blank check: an unsigned form must give
            # an empty signature crop, not a guess somewhere else on the page.
            cropped = _crop_region(img, *box)
            if not cropped:
                logger.warning(f"[Document {document_id}] Template {kind} box {pct} -> {box} is outside the image")
                continue
            path = os.path.join(output_dir, f"{kind}.png")
            cropped.save(path)
            x1, y1, x2, y2 = box
            result[f"has_{kind}"] = True
            result[f"{kind}_bbox"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            result[f"{kind}_crop_path"] = os.path.abspath(path)
            result[f"{kind}_base64"] = _image_to_base64(cropped)
            if kind == "signature":
                result["confidence"] = "high"
            logger.info(f"[Document {document_id}] {kind.capitalize()} cropped at template box {box} (from {pct}%)")

        # Both drawn → done, no API calls. A form with only one region drawn
        # goes on to locate the other; the drawn one is never overridden.
        if (result["has_signature"] and result["has_photo"]) or not prefer_layout:
            return result
        logger.info(
            f"[Document {document_id}] Template has no box for "
            f"{[k for k in ('signature', 'photo') if not result['has_' + k]]} — locating it from the layout."
        )

    # ══════════════════════════════════════════════════════════════════════
    # PATH 2: Mistral OCR 4 Block & Image Annotation Extraction
    # (Reached when no manual kyc_boxes are defined on the template, or — for a
    # form — to find the one region the template does not cover)
    # ══════════════════════════════════════════════════════════════════════
    logger.info(f"[Document {document_id}] KYC Path 2: Running Mistral OCR 4 Block Extraction...")
    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": resolved_url
            },
            include_blocks=True,
            include_image_base64=True,
            bbox_annotation_format=_schema(BboxAnnotation)
        )
        
        for page in getattr(ocr_response, "pages", []) or []:
            if prefer_layout:
                layout = _locate_from_layout(page, width, height)
                for kind in ("photo", "signature"):
                    if layout[kind] and not result[f"has_{kind}"]:
                        _store_crop(result, kind, img, layout[kind], output_dir, document_id, "OCR layout")
            # Whatever the layout pass found is final for a form — the passes
            # below only fill what it could not.
            skip_sig = prefer_layout and result["has_signature"]
            skip_photo = prefer_layout and result["has_photo"]

            # Native signature blocks first: OCR tags signatures it recognises
            # as block.type == "signature" even when they aren't raster images
            # (e.g. vector / script-font signatures on generated PDFs), which
            # the image search below can never find.
            for block in ([] if skip_sig else (getattr(page, "blocks", []) or [])):
                if getattr(block, "type", None) != "signature":
                    continue
                coords = tuple(getattr(block, a, None) for a in ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"))
                if None in coords:
                    continue
                cropped_sig = _crop_region(img, *coords)
                if cropped_sig:
                    sx1, sy1, sx2, sy2 = coords
                    result["has_signature"] = True
                    result["signature_bbox"] = {"x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2}
                    sig_path = os.path.join(output_dir, "signature.png")
                    cropped_sig.save(sig_path)
                    result["signature_crop_path"] = os.path.abspath(sig_path)
                    result["signature_base64"] = _image_to_base64(cropped_sig)
                    result["confidence"] = "high"
                    logger.info(f"[Document {document_id}] Path 2: Signature extracted from OCR signature block: ({sx1}, {sy1})->({sx2}, {sy2})")
                    break

            # Search images for signature (via image_annotation.block_type)
            # NOTE: Mistral OCR stores the custom BboxAnnotation in
            # image_annotation, NOT as the native block `.type` attribute.
            # This mirrors the same pattern used for photo detection below.
            images_for_sig = [] if result["has_signature"] else (getattr(page, "images", []) or [])
            for img_obj in images_for_sig:
                annotation = getattr(img_obj, "image_annotation", None)
                is_signature = False
                if annotation:
                    if isinstance(annotation, str):
                        try:
                            ann_data = json.loads(annotation)
                            if ann_data.get("block_type") == "signature":
                                is_signature = True
                        except Exception:
                            pass
                    elif isinstance(annotation, dict):
                        if annotation.get("block_type") == "signature":
                            is_signature = True

                if is_signature:
                    sx1 = getattr(img_obj, "top_left_x", None)
                    sy1 = getattr(img_obj, "top_left_y", None)
                    sx2 = getattr(img_obj, "bottom_right_x", None)
                    sy2 = getattr(img_obj, "bottom_right_y", None)
                    if None not in (sx1, sy1, sx2, sy2):
                        cropped_sig = _crop_region(img, sx1, sy1, sx2, sy2)
                        if cropped_sig:
                            result["has_signature"] = True
                            result["signature_bbox"] = {"x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2}
                            sig_path = os.path.join(output_dir, "signature.png")
                            cropped_sig.save(sig_path)
                            result["signature_crop_path"] = os.path.abspath(sig_path)
                            result["signature_base64"] = _image_to_base64(cropped_sig)
                            result["confidence"] = "high"
                            logger.info(f"[Document {document_id}] Path 2: Signature extracted from annotated image: ({sx1}, {sy1})->({sx2}, {sy2})")
                            break
            
            # Search images for photo
            images = [] if skip_photo else (getattr(page, "images", []) or [])
            for img_obj in images:
                annotation = getattr(img_obj, "image_annotation", None)
                is_photo = False
                if annotation:
                    if isinstance(annotation, str):
                        try:
                            ann_data = json.loads(annotation)
                            if ann_data.get("block_type") == "photo":
                                is_photo = True
                        except Exception:
                            pass
                    elif isinstance(annotation, dict):
                        if annotation.get("block_type") == "photo":
                            is_photo = True
                
                if is_photo:
                    px1 = getattr(img_obj, "top_left_x", None)
                    py1 = getattr(img_obj, "top_left_y", None)
                    px2 = getattr(img_obj, "bottom_right_x", None)
                    py2 = getattr(img_obj, "bottom_right_y", None)
                    if None not in (px1, py1, px2, py2):
                        cropped_photo = _crop_region(img, px1, py1, px2, py2)
                        if cropped_photo:
                            result["has_photo"] = True
                            result["photo_bbox"] = {"x1": px1, "y1": py1, "x2": px2, "y2": py2}
                            photo_path = os.path.join(output_dir, "photo.png")
                            cropped_photo.save(photo_path)
                            result["photo_crop_path"] = os.path.abspath(photo_path)
                            result["photo_base64"] = _image_to_base64(cropped_photo)
                            logger.info(f"[Document {document_id}] Path 2: Photo successfully extracted from annotated image: ({px1}, {py1})->({px2}, {py2})")
                            break

        if result["has_signature"] and result["has_photo"]:
            logger.info(f"[Document {document_id}] Path 2 found both signature and photo. Returning result.")
            return result
        # ID cards often yield the photo here but not the signature (or vice
        # versa) — fall back for whatever is missing, keeping what was found.
        logger.info(
            f"[Document {document_id}] Path 2 partial (signature={result['has_signature']}, "
            f"photo={result['has_photo']}). Falling back for the missing region(s)..."
        )
            
    except Exception as e:
        if prefer_layout:
            # A form keeps what is already exact — template boxes or the
            # layout — and falls back only for what is still missing.
            logger.error(f"[Document {document_id}] Path 2 failed: {e}. Falling back for what is missing...")
        else:
            logger.error(f"[Document {document_id}] Path 2 failed: {e}. Resetting result and falling back...")
            result.update({
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
            })

    # ══════════════════════════════════════════════════════════════════════
    # FALLBACK PATH: Two-pass Pixtral approach (when no manual coords)
    # ══════════════════════════════════════════════════════════════════════

    # ── Pass 1: Document annotation via Mistral OCR ──────────────────────
    logger.info(f"[Document {document_id}] KYC Pass 1: Running document_annotation...")

    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": resolved_url
            },
            include_image_base64=False,
            include_blocks=True,
            document_annotation_format=_schema(DocumentSignatureAnnotation),
        )
    except Exception as e:
        logger.error(f"[Document {document_id}] OCR document_annotation failed: {e}")
        return result

    # Collect OCR-detected image region bboxes as landmarks
    ocr_bboxes = []
    for page in getattr(ocr_response, "pages", []) or []:
        ocr_bboxes.extend(getattr(page, "images", []) or [])
        # Labelled text blocks give the vision model far better coordinate
        # anchors than image regions alone (e.g. "SIGNATURE OF ACCOUNT HOLDER").
        ocr_bboxes.extend(
            b for b in (getattr(page, "blocks", []) or [])
            if (getattr(b, "content", "") or "").strip()
        )
    logger.info(f"[Document {document_id}] OCR detected {len(ocr_bboxes)} image region(s).")

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
            f"[Document {document_id}] Annotation: has_signature={annotation.has_signature}, "
            f"confidence={annotation.confidence}, location={annotation.signature_location}"
        )

    # ── Pass 2: Pixtral-Large for pixel-precise bboxes ───────────────────
    logger.info(f"[Document {document_id}] KYC Pass 2: Calling {BBOX_VISION_MODEL}...")

    # Build landmark strings from OCR bboxes
    landmarks = []
    for idx, item in enumerate(ocr_bboxes):
        x1 = getattr(item, "top_left_x", None)
        y1 = getattr(item, "top_left_y", None)
        x2 = getattr(item, "bottom_right_x", None)
        y2 = getattr(item, "bottom_right_y", None)
        bid = getattr(item, "id", "")
        text = " ".join((getattr(item, "content", "") or "").split())[:60]
        label = f'text "{text}"' if text else (bid or f"Region {idx+1}")
        if None not in (x1, y1, x2, y2):
            landmarks.append(f"- {label}: ({x1}, {y1}) to ({x2}, {y2})")

    location_hint = annotation.signature_location if annotation else None

    bboxes = _locate_kyc_bboxes(
        client, resolved_url, width, height,
        location_hint=location_hint,
        landmarks=landmarks,
    )

    if not bboxes:
        logger.warning(f"[Document {document_id}] Vision bbox call returned no results.")
        return result

    # ── Crop signature ────────────────────────────────────────────────────
    if not result["has_signature"] and bboxes.signature_found and all(
        v is not None for v in (bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)
    ):
        cropped = _crop_region(img, bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)
        if cropped and _is_blank(cropped):
            # Vision-model pixel boxes can land on empty space — a blank crop
            # would be compared as if it were the real signature, so drop it.
            logger.warning(f"[Document {document_id}] Vision signature bbox is blank; discarding.")
        elif cropped:
            result["has_signature"] = True
            result["signature_bbox"] = {
                "x1": bboxes.sig_x1, "y1": bboxes.sig_y1,
                "x2": bboxes.sig_x2, "y2": bboxes.sig_y2,
            }
            sig_path = os.path.join(output_dir, "signature.png")
            cropped.save(sig_path)
            result["signature_crop_path"] = os.path.abspath(sig_path)
            result["signature_base64"] = _image_to_base64(cropped)
            logger.info(f"[Document {document_id}] Signature crop saved: {sig_path}")

    # ── Crop photo ────────────────────────────────────────────────────────
    if not result["has_photo"] and bboxes.photo_found and all(
        v is not None for v in (bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)
    ):
        cropped = _crop_region(img, bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)
        if cropped and _is_blank(cropped):
            # Vision-model pixel boxes can land on empty space — a blank crop
            # would be compared as if it were the real photo, so drop it.
            logger.warning(f"[Document {document_id}] Vision photo bbox is blank; discarding.")
        elif cropped:
            result["has_photo"] = True
            result["photo_bbox"] = {
                "x1": bboxes.photo_x1, "y1": bboxes.photo_y1,
                "x2": bboxes.photo_x2, "y2": bboxes.photo_y2,
            }
            photo_path = os.path.join(output_dir, "photo.png")
            cropped.save(photo_path)
            result["photo_crop_path"] = os.path.abspath(photo_path)
            result["photo_base64"] = _image_to_base64(cropped)
            logger.info(f"[Document {document_id}] Photo crop saved: {photo_path}")

    return result

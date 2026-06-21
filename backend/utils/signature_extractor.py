"""
signature_extractor.py

KYC Signature & Photo Extraction Module for DocuMind AI.

Two-pass approach:
  Pass 1: mistral-ocr-latest  → document_annotation (detect signature + OCR region landmarks)
  Pass 2: pixtral-large-latest → pixel-precise bounding boxes for signature AND photo

Adapted from the standalone signature_extractor.py shared by the team.
"""

import base64
import io
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

from mistralai.client import Mistral
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentSignatureAnnotation(BaseModel):
    """Applied to the full page to detect signature presence."""
    has_signature: bool = Field(..., description="True if a signature is present anywhere in the document.")
    confidence: str = Field(..., description="'high', 'medium', or 'low'.")
    signer_name: Optional[str] = Field(None, description="Name near the signature, if visible.")
    signed_date: Optional[str] = Field(None, description="Date near the signature, if present.")
    signature_location: Optional[str] = Field(
        None, description="Text description of where the signature is located."
    )
    additional_notes: Optional[str] = Field(None, description="Any other relevant notes.")


class KycImageBboxes(BaseModel):
    """
    Pixel-precise bounding boxes for BOTH signature and photo,
    returned by pixtral-large-latest in a single vision call.
    """
    step_by_step_analysis: str = Field(
        ...,
        description=(
            "Detailed step-by-step visual search and coordinate analysis. "
            "Locate the handwritten signature strokes and the cardholder photograph "
            "relative to the OCR reference region coordinates."
        ),
    )
    # -- Signature fields --
    signature_found: bool = Field(
        ..., description="True if a handwritten signature was located in the image."
    )
    sig_x1: Optional[int] = Field(None, description="LEFT edge of signature bounding box (px).")
    sig_y1: Optional[int] = Field(None, description="TOP edge of signature bounding box (px).")
    sig_x2: Optional[int] = Field(None, description="RIGHT edge of signature bounding box (px).")
    sig_y2: Optional[int] = Field(None, description="BOTTOM edge of signature bounding box (px).")
    signature_notes: Optional[str] = Field(None, description="Brief note on the identified signature.")

    # -- Photo fields --
    photo_found: bool = Field(
        ..., description="True if a cardholder face photograph was located in the image."
    )
    photo_x1: Optional[int] = Field(None, description="LEFT edge of photo bounding box (px).")
    photo_y1: Optional[int] = Field(None, description="TOP edge of photo bounding box (px).")
    photo_x2: Optional[int] = Field(None, description="RIGHT edge of photo bounding box (px).")
    photo_y2: Optional[int] = Field(None, description="BOTTOM edge of photo bounding box (px).")
    photo_notes: Optional[str] = Field(None, description="Brief note on the identified photograph.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schema(model_cls) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model_cls.__name__,
            "schema": model_cls.model_json_schema(),
            "strict": True,
        },
    }


def _resolve_image_url(file_path: str) -> str:
    """Base64-encode a local file as a data URI for Mistral API."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _open_image(source: str):
    """Open a PIL Image from a local file path or base64 data URI."""
    from PIL import Image
    if source.startswith("data:"):
        _, b64 = source.split(",", 1)
        return Image.open(io.BytesIO(base64.b64decode(b64)))
    return Image.open(source)

def _prepare_image_and_url(file_path: str):
    """
    Returns a Pillow Image and a data URI string. 
    If the file is a PDF, it rasterizes the first page to ensure consistent 
    coordinate systems for both Mistral OCR and Pixtral Vision.
    """
    from PIL import Image
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    mime, _ = mimetypes.guess_type(str(path))
    if mime == 'application/pdf' or file_path.lower().endswith('.pdf'):
        import fitz
        doc = fitz.open(str(path))
        page = doc[0]
        # Rasterize at 150 DPI for good OCR/Vision balance
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Encode to base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"
        return img, data_uri
    else:
        img = Image.open(file_path)
        # Ensure image is in a format suitable for saving as PNG
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        
        # Encode natively to PNG base64 to avoid MIME type errors with Mistral
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"
        return img, data_uri


def _crop_region(img, x1, y1, x2, y2):
    """Crop a region from a PIL Image, clamping to image bounds."""
    W, H = img.size
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(W, x2)
    y2 = min(H, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return img.crop((x1, y1, x2, y2))


def _image_to_base64(img) -> str:
    """Convert a PIL Image to a base64-encoded PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# Pass 2: Pixtral-Large vision call for pixel-precise bboxes
# ---------------------------------------------------------------------------

def _locate_kyc_bboxes(
    client: Mistral,
    resolved_url: str,
    width: int,
    height: int,
    location_hint: Optional[str] = None,
    landmarks: Optional[list] = None,
) -> Optional[KycImageBboxes]:
    """
    Second-pass vision call to pixtral-large-latest.
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
        f"You are a precise KYC document analysis assistant. "
        f"Look at this image carefully. "
        f"The image dimensions are {width}x{height} pixels (width={width}, height={height}).\n"
        f"{landmarks_str}"
        f"{hint_str}\n"
        f"Your task: locate TWO regions in this KYC document image:\n\n"
        f"1. **SIGNATURE** — the handwritten cursive name, mark, or scribble "
        f"(typically written in blue or black ink). It is NOT printed text, NOT a logo, "
        f"NOT a photograph. The signature is usually written directly above or next to "
        f"the printed 'हस्ताक्षर / Signature' label. Do not include the printed label "
        f"in your bounding box. Capture the full span of all handwriting strokes.\n\n"
        f"2. **PHOTO** — the cardholder's passport-style face photograph. This is usually "
        f"a rectangular region containing a person's head and shoulders. It is NOT an emblem, "
        f"NOT a QR code, NOT text. Typically located on the right side or bottom-right of the card.\n\n"
        f"Guidelines:\n"
        f"- Use the OCR detected region coordinates listed above to calibrate your coordinate system.\n"
        f"- Return x1 (left), y1 (top), x2 (right), y2 (bottom) as integer pixel coordinates "
        f"on the original {width}x{height} image.\n"
        f"- Be extremely precise and crop tightly around each region.\n"
        f"- If a region is not found, set its _found field to false and leave coordinates as null."
    )

    try:
        response = client.chat.complete(
            model="pixtral-large-latest",
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
        )
        raw = response.choices[0].message.content
        d = json.loads(raw) if isinstance(raw, str) else dict(raw)
        bboxes = KycImageBboxes(**d)

        logger.info(
            f"  Pixtral result: signature_found={bboxes.signature_found} "
            f"({bboxes.sig_x1},{bboxes.sig_y1})->({bboxes.sig_x2},{bboxes.sig_y2}) | "
            f"photo_found={bboxes.photo_found} "
            f"({bboxes.photo_x1},{bboxes.photo_y1})->({bboxes.photo_x2},{bboxes.photo_y2})"
        )
        if bboxes.step_by_step_analysis:
            logger.debug(f"  Pixtral analysis: {bboxes.step_by_step_analysis}")

        return bboxes
    except Exception as e:
        logger.error(f"  Pixtral vision call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

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

    If `kyc_boxes` is None, falls back to the two-pass approach:
      Pass 1: mistral-ocr-latest with document_annotation → detect signature + get OCR landmarks
      Pass 2: pixtral-large-latest → pixel-precise bboxes for signature AND photo
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

    client = Mistral(api_key=settings.MISTRAL_API_KEY)

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
        img, resolved_url = _prepare_image_and_url(file_path)
        width, height = img.size
    except Exception as e:
        logger.error(f"[Document {document_id}] Failed to prepare image: {e}")
        return result

    # ══════════════════════════════════════════════════════════════════════
    # FAST PATH: Template-level manual coordinates (skip Pixtral entirely)
    # ══════════════════════════════════════════════════════════════════════
    if kyc_boxes:
        logger.info(f"[Document {document_id}] Using MANUAL template coordinates for extraction (no API calls)")

        # --- Crop signature from percentage coordinates ---
        sig_box = kyc_boxes.get("signature")
        if sig_box:
            sx1 = int(sig_box["x1"] / 100.0 * width)
            sy1 = int(sig_box["y1"] / 100.0 * height)
            sx2 = int(sig_box["x2"] / 100.0 * width)
            sy2 = int(sig_box["y2"] / 100.0 * height)
            logger.info(f"[Document {document_id}] Signature manual bbox: ({sx1},{sy1})->({sx2},{sy2}) from pct ({sig_box})")

            cropped = _crop_region(img, sx1, sy1, sx2, sy2)
            if cropped:
                result["has_signature"] = True
                result["signature_bbox"] = {"x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2}
                sig_path = os.path.join(output_dir, "signature.png")
                cropped.save(sig_path)
                result["signature_crop_path"] = os.path.abspath(sig_path)
                result["signature_base64"] = _image_to_base64(cropped)
                result["confidence"] = "high"
                logger.info(f"[Document {document_id}] Signature crop saved (manual): {sig_path}")
            else:
                logger.warning(f"[Document {document_id}] Signature crop returned empty region")

        # --- Crop photo from percentage coordinates ---
        photo_box = kyc_boxes.get("photo")
        if photo_box:
            px1 = int(photo_box["x1"] / 100.0 * width)
            py1 = int(photo_box["y1"] / 100.0 * height)
            px2 = int(photo_box["x2"] / 100.0 * width)
            py2 = int(photo_box["y2"] / 100.0 * height)
            logger.info(f"[Document {document_id}] Photo manual bbox: ({px1},{py1})->({px2},{py2}) from pct ({photo_box})")

            cropped = _crop_region(img, px1, py1, px2, py2)
            if cropped:
                result["has_photo"] = True
                result["photo_bbox"] = {"x1": px1, "y1": py1, "x2": px2, "y2": py2}
                photo_path = os.path.join(output_dir, "photo.png")
                cropped.save(photo_path)
                result["photo_crop_path"] = os.path.abspath(photo_path)
                result["photo_base64"] = _image_to_base64(cropped)
                logger.info(f"[Document {document_id}] Photo crop saved (manual): {photo_path}")
            else:
                logger.warning(f"[Document {document_id}] Photo crop returned empty region")

        return result

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
            document_annotation_format=_schema(DocumentSignatureAnnotation),
        )
    except Exception as e:
        logger.error(f"[Document {document_id}] OCR document_annotation failed: {e}")
        return result

    # Collect OCR-detected image region bboxes as landmarks
    ocr_bboxes = []
    for page in getattr(ocr_response, "pages", []) or []:
        ocr_bboxes.extend(getattr(page, "images", []) or [])
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
        result["confidence"] = annotation.confidence
        result["signer_name"] = annotation.signer_name
        logger.info(
            f"[Document {document_id}] Annotation: has_signature={annotation.has_signature}, "
            f"confidence={annotation.confidence}, location={annotation.signature_location}"
        )

    # ── Pass 2: Pixtral-Large for pixel-precise bboxes ───────────────────
    logger.info(f"[Document {document_id}] KYC Pass 2: Calling pixtral-large-latest...")

    # Build landmark strings from OCR bboxes
    landmarks = []
    for idx, item in enumerate(ocr_bboxes):
        x1 = getattr(item, "top_left_x", None)
        y1 = getattr(item, "top_left_y", None)
        x2 = getattr(item, "bottom_right_x", None)
        y2 = getattr(item, "bottom_right_y", None)
        bid = getattr(item, "id", "")
        if None not in (x1, y1, x2, y2):
            landmarks.append(f"- {bid or f'Region {idx+1}'}: ({x1}, {y1}) to ({x2}, {y2})")

    location_hint = annotation.signature_location if annotation else None

    bboxes = _locate_kyc_bboxes(
        client, resolved_url, width, height,
        location_hint=location_hint,
        landmarks=landmarks,
    )

    if not bboxes:
        logger.warning(f"[Document {document_id}] Pixtral returned no results.")
        return result

    # ── Crop signature ────────────────────────────────────────────────────
    if bboxes.signature_found and all(
        v is not None for v in (bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)
    ):
        result["has_signature"] = True
        result["signature_bbox"] = {
            "x1": bboxes.sig_x1, "y1": bboxes.sig_y1,
            "x2": bboxes.sig_x2, "y2": bboxes.sig_y2,
        }
        cropped = _crop_region(img, bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)
        if cropped:
            sig_path = os.path.join(output_dir, "signature.png")
            cropped.save(sig_path)
            result["signature_crop_path"] = os.path.abspath(sig_path)
            result["signature_base64"] = _image_to_base64(cropped)
            logger.info(f"[Document {document_id}] Signature crop saved: {sig_path}")

    # ── Crop photo ────────────────────────────────────────────────────────
    if bboxes.photo_found and all(
        v is not None for v in (bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)
    ):
        result["has_photo"] = True
        result["photo_bbox"] = {
            "x1": bboxes.photo_x1, "y1": bboxes.photo_y1,
            "x2": bboxes.photo_x2, "y2": bboxes.photo_y2,
        }
        cropped = _crop_region(img, bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)
        if cropped:
            photo_path = os.path.join(output_dir, "photo.png")
            cropped.save(photo_path)
            result["photo_crop_path"] = os.path.abspath(photo_path)
            result["photo_base64"] = _image_to_base64(cropped)
            logger.info(f"[Document {document_id}] Photo crop saved: {photo_path}")

    return result

"""
signature_extractor.py

KYC Signature & Photo Extraction Module for DocuMind AI.

Two-pass approach:
  Pass 1: OCRProvider  → document_annotation (detect signature + OCR region landmarks)
  Pass 2: VisionProvider → pixel-precise bounding boxes for signature AND photo

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

from pydantic import BaseModel, Field

from config import settings
from platform_core.registry import ProviderRegistry

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


class BboxAnnotation(BaseModel):
    """Used for annotating bounding boxes inside the document."""
    block_type: str = Field(
        ...,
        description="The type of block: 'photo' (face/passport photograph of the cardholder), 'signature' (handwritten signature), or 'other'."
    )


class KycImageBboxes(BaseModel):
    """
    Pixel-precise bounding boxes for BOTH signature and photo.
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
    """Base64-encode a local file as a data URI."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _prepare_image_and_url(file_path: str):
    """
    Returns a Pillow Image and a data URI string. 
    If the file is a PDF, it rasterizes the first page.
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
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"
        return img, data_uri
    else:
        img = Image.open(file_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        
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
# Pass 2: VisionProvider call for pixel-precise bboxes
# ---------------------------------------------------------------------------

async def _locate_kyc_bboxes(
    resolved_url: str,
    width: int,
    height: int,
    location_hint: Optional[str] = None,
    landmarks: Optional[list] = None,
) -> Optional[KycImageBboxes]:
    """
    Second-pass vision call using ProviderRegistry VisionProvider.
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
        registry = ProviderRegistry.get()
        vision = registry.get_vision()

        response = await vision.analyze(
            images=[resolved_url],
            prompt=prompt,
            response_format=_schema(KycImageBboxes),
        )
        raw = response.content
        d = json.loads(raw) if isinstance(raw, str) else dict(raw)
        bboxes = KycImageBboxes(**d)

        logger.info(
            f"  Vision result: signature_found={bboxes.signature_found} "
            f"({bboxes.sig_x1},{bboxes.sig_y1})->({bboxes.sig_x2},{bboxes.sig_y2}) | "
            f"photo_found={bboxes.photo_found} "
            f"({bboxes.photo_x1},{bboxes.photo_y1})->({bboxes.photo_x2},{bboxes.photo_y2})"
        )
        return bboxes
    except Exception as e:
        logger.error(f"  Vision provider call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

async def extract_signature_and_photo(
    file_path: str,
    document_id: str,
    output_dir: str = None,
    kyc_boxes: dict = None,
) -> dict:
    """
    KYC image extraction using OCRProvider and VisionProvider.
    """
    registry = ProviderRegistry.get()

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

    try:
        img, resolved_url = _prepare_image_and_url(file_path)
        width, height = img.size
    except Exception as e:
        logger.error(f"[Document {document_id}] Failed to prepare image: {e}")
        return result

    # ══════════════════════════════════════════════════════════════════════
    # PATH 0: Template-level manual coordinates (highest priority)
    # ══════════════════════════════════════════════════════════════════════
    # Regions drawn by hand on the template's sample document are ground truth
    # for that document layout — they must win over anything the OCR block
    # annotator or the vision model guesses. Auto-detection below only fills in
    # a region the template did not define.
    if kyc_boxes:
        logger.info(f"[Document {document_id}] KYC Path 0: Using MANUAL template coordinates: {kyc_boxes}")

        sig_box = kyc_boxes.get("signature")
        if sig_box:
            sx1 = int(sig_box["x1"] / 100.0 * width)
            sy1 = int(sig_box["y1"] / 100.0 * height)
            sx2 = int(sig_box["x2"] / 100.0 * width)
            sy2 = int(sig_box["y2"] / 100.0 * height)
            cropped = _crop_region(img, sx1, sy1, sx2, sy2)
            if cropped:
                result["has_signature"] = True
                result["signature_bbox"] = {"x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2}
                sig_path = os.path.join(output_dir, "signature.png")
                cropped.save(sig_path)
                result["signature_crop_path"] = os.path.abspath(sig_path)
                result["signature_base64"] = _image_to_base64(cropped)
                result["confidence"] = "high"
                logger.info(f"[Document {document_id}] Path 0: Signature cropped from template region")
            else:
                logger.warning(f"[Document {document_id}] Path 0: Signature region is empty after clamping")

        photo_box = kyc_boxes.get("photo")
        if photo_box:
            px1 = int(photo_box["x1"] / 100.0 * width)
            py1 = int(photo_box["y1"] / 100.0 * height)
            px2 = int(photo_box["x2"] / 100.0 * width)
            py2 = int(photo_box["y2"] / 100.0 * height)
            cropped = _crop_region(img, px1, py1, px2, py2)
            if cropped:
                result["has_photo"] = True
                result["photo_bbox"] = {"x1": px1, "y1": py1, "x2": px2, "y2": py2}
                photo_path = os.path.join(output_dir, "photo.png")
                cropped.save(photo_path)
                result["photo_crop_path"] = os.path.abspath(photo_path)
                result["photo_base64"] = _image_to_base64(cropped)
                logger.info(f"[Document {document_id}] Path 0: Photo cropped from template region")
            else:
                logger.warning(f"[Document {document_id}] Path 0: Photo region is empty after clamping")

        if result["has_signature"] and result["has_photo"]:
            return result

    # Regions already satisfied by the template must survive the auto paths below.
    manual_signature = result["has_signature"]
    manual_photo = result["has_photo"]

    # ══════════════════════════════════════════════════════════════════════
    # PATH 1: OCRProvider 4 Block & Image Annotation Extraction
    # ══════════════════════════════════════════════════════════════════════
    logger.info(f"[Document {document_id}] KYC Path 1: Running OCR Extraction with block annotations...")
    try:
        ocr = registry.get_ocr()
        ocr_response = await ocr.extract(
            file_path=file_path,
            include_blocks=True,
            bbox_annotation_format=_schema(BboxAnnotation),
            include_image_base64=True, # Custom kwargs handled by provider
        )
        
        # Searching blocks for signature and photo is no longer perfectly mapped to our OCRResponse
        # structure because Mistral OCR returns pages with images directly, which we flatten.
        # But we can check blocks to see if signature/photo is there.
        for b in ocr_response.blocks:
            if b.get("type") == "signature" and not result["has_signature"]:
                sx1 = b.get("top_left_x")
                sy1 = b.get("top_left_y")
                sx2 = b.get("bottom_right_x")
                sy2 = b.get("bottom_right_y")
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
                        logger.info(f"[Document {document_id}] Path 1: Signature successfully extracted")

            elif b.get("type") == "photo" and not result["has_photo"]:
                px1 = b.get("top_left_x")
                py1 = b.get("top_left_y")
                px2 = b.get("bottom_right_x")
                py2 = b.get("bottom_right_y")
                if None not in (px1, py1, px2, py2):
                    cropped_photo = _crop_region(img, px1, py1, px2, py2)
                    if cropped_photo:
                        result["has_photo"] = True
                        result["photo_bbox"] = {"x1": px1, "y1": py1, "x2": px2, "y2": py2}
                        photo_path = os.path.join(output_dir, "photo.png")
                        cropped_photo.save(photo_path)
                        result["photo_crop_path"] = os.path.abspath(photo_path)
                        result["photo_base64"] = _image_to_base64(cropped_photo)
                        logger.info(f"[Document {document_id}] Path 1: Photo successfully extracted")

        if result["has_signature"] and result["has_photo"]:
            logger.info(f"[Document {document_id}] Path 1 succeeded.")
            return result

        # Partial results from the block annotator are unreliable on their own,
        # so drop them — but never drop a crop that came from the template.
        logger.info(f"[Document {document_id}] Path 1 did not extract both. Discarding partial auto-detections...")
        if not manual_signature:
            result.update({
                "has_signature": False, "signature_crop_path": None,
                "signature_base64": None, "signature_bbox": None,
                "signer_name": None,
            })
        if not manual_photo:
            result.update({
                "has_photo": False, "photo_crop_path": None,
                "photo_base64": None, "photo_bbox": None,
            })
        if not (manual_signature or manual_photo):
            result["confidence"] = "low"

    except Exception as e:
        logger.error(f"[Document {document_id}] Path 1 failed: {e}. Falling back...")

    # ══════════════════════════════════════════════════════════════════════
    # FALLBACK PATH: Two-pass Vision approach
    # ══════════════════════════════════════════════════════════════════════

    logger.info(f"[Document {document_id}] KYC Pass 1: Running document_annotation...")
    try:
        ocr = registry.get_ocr()
        ocr_response = await ocr.extract(
            file_path=file_path,
            include_image_base64=False,
            document_annotation_format=_schema(DocumentSignatureAnnotation),
        )
    except Exception as e:
        logger.error(f"[Document {document_id}] OCR document_annotation failed: {e}")
        return result

    ocr_bboxes = ocr_response.blocks
    annotation = None
    if ocr_response.document_annotation:
        try:
            d = ocr_response.document_annotation
            annotation = DocumentSignatureAnnotation(**d)
        except Exception as e:
            logger.warning(f"[Document {document_id}] Failed to parse document_annotation: {e}")

    if annotation:
        if not (manual_signature or manual_photo):
            result["confidence"] = annotation.confidence
        result["signer_name"] = annotation.signer_name

    logger.info(f"[Document {document_id}] KYC Pass 2: Calling VisionProvider...")
    landmarks = []
    for idx, item in enumerate(ocr_bboxes):
        x1 = item.get("top_left_x")
        y1 = item.get("top_left_y")
        x2 = item.get("bottom_right_x")
        y2 = item.get("bottom_right_y")
        if None not in (x1, y1, x2, y2):
            landmarks.append(f"- Region {idx+1}: ({x1}, {y1}) to ({x2}, {y2})")

    location_hint = annotation.signature_location if annotation else None

    bboxes = await _locate_kyc_bboxes(
        resolved_url, width, height,
        location_hint=location_hint,
        landmarks=landmarks,
    )

    if not bboxes:
        return result

    if not manual_signature and bboxes.signature_found and all(v is not None for v in (bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)):
        result["has_signature"] = True
        result["signature_bbox"] = {"x1": bboxes.sig_x1, "y1": bboxes.sig_y1, "x2": bboxes.sig_x2, "y2": bboxes.sig_y2}
        cropped = _crop_region(img, bboxes.sig_x1, bboxes.sig_y1, bboxes.sig_x2, bboxes.sig_y2)
        if cropped:
            sig_path = os.path.join(output_dir, "signature.png")
            cropped.save(sig_path)
            result["signature_crop_path"] = os.path.abspath(sig_path)
            result["signature_base64"] = _image_to_base64(cropped)

    if not manual_photo and bboxes.photo_found and all(v is not None for v in (bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)):
        result["has_photo"] = True
        result["photo_bbox"] = {"x1": bboxes.photo_x1, "y1": bboxes.photo_y1, "x2": bboxes.photo_x2, "y2": bboxes.photo_y2}
        cropped = _crop_region(img, bboxes.photo_x1, bboxes.photo_y1, bboxes.photo_x2, bboxes.photo_y2)
        if cropped:
            photo_path = os.path.join(output_dir, "photo.png")
            cropped.save(photo_path)
            result["photo_crop_path"] = os.path.abspath(photo_path)
            result["photo_base64"] = _image_to_base64(cropped)

    return result

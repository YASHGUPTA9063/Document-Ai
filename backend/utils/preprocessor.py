"""
preprocessor.py

Document Image Preprocessing Utility for Document-AI.

Applies 4 enhancement steps to improve OCR accuracy:
  1. Resolution Normalization  — upscale low-res images to minimum 1000px short-side
  2. Brightness / CLAHE       — adaptive histogram equalization on LAB L-channel
  3. Noise Removal            — light Gaussian blur to reduce scanner grain / JPEG artifacts
  4. Skew Correction          — detect and rotate page tilt via Hough line analysis

Supported inputs: .jpg, .jpeg, .png, .webp, .pdf (PDF only when preprocess_pdf=True)
Always skipped:   .docx (no pixel representation)
"""

import io
import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

MIN_SHORT_SIDE = 1000       # px — upscale if below this
MAX_SCALE_FACTOR = 3.0      # safety cap on upscaling
SKEW_SKIP_THRESHOLD = 0.5   # degrees — skip rotation below this angle
SKEW_MAX_ANGLE = 45.0       # degrees — ignore lines outside ±45°
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)
GAUSSIAN_KERNEL = (3, 3)
PDF_DPI = 150               # rasterization DPI for PDFs


# ─── Individual Processing Steps ─────────────────────────────────────────────

def normalize_resolution(img: Image.Image) -> tuple[Image.Image, bool]:
    """
    Upscale image if its shorter side is below MIN_SHORT_SIDE px.
    Uses high-quality LANCZOS resampling.

    Returns (processed_image, was_applied).
    """
    w, h = img.size
    short_side = min(w, h)
    if short_side >= MIN_SHORT_SIDE:
        return img, False

    scale = min(MIN_SHORT_SIDE / short_side, MAX_SCALE_FACTOR)
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    logger.debug(f"  [preprocess] Resolution normalized: {w}x{h} → {new_w}x{new_h} (scale={scale:.2f}x)")
    return img, True


def correct_brightness(img: Image.Image) -> tuple[Image.Image, bool]:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) on the L-channel
    of the LAB color space. Improves locally dark/bright regions without blowing out
    already-bright areas.

    Returns (processed_image, was_applied).
    """
    # PIL RGB → NumPy BGR (OpenCV convention)
    img_np = np.array(img.convert("RGB"))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Convert to LAB and apply CLAHE on L only
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    l_eq = clahe.apply(l_ch)

    lab_eq = cv2.merge([l_eq, a_ch, b_ch])
    img_bgr_eq = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)
    img_rgb_eq = cv2.cvtColor(img_bgr_eq, cv2.COLOR_BGR2RGB)

    logger.debug("  [preprocess] Brightness corrected via CLAHE (LAB L-channel)")
    return Image.fromarray(img_rgb_eq), True


def remove_noise(img: Image.Image) -> tuple[Image.Image, bool]:
    """
    Apply a light 3×3 Gaussian blur to reduce scanner grain and JPEG artifacts.
    The small kernel preserves text sharpness while smoothing background noise.

    Returns (processed_image, was_applied).
    """
    img_np = np.array(img.convert("RGB"))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    blurred = cv2.GaussianBlur(img_bgr, GAUSSIAN_KERNEL, 0)
    img_rgb = cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB)

    logger.debug("  [preprocess] Noise removed via Gaussian blur (3×3 kernel)")
    return Image.fromarray(img_rgb), True


def correct_skew(img: Image.Image) -> tuple[Image.Image, bool]:
    """
    Detect page tilt using Hough line transform and rotate to level.

    Algorithm:
      1. Grayscale → Canny edge detection
      2. HoughLinesP to detect line segments
      3. Compute angle of each line, filter to ±45°
      4. Take the median angle across all detected lines
      5. Rotate if |angle| > SKEW_SKIP_THRESHOLD

    Returns (processed_image, was_applied).
    """
    img_np = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, threshold1=50, threshold2=150, apertureSize=3)

    # Hough line detection
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=100,
        maxLineGap=10
    )

    if lines is None or len(lines) == 0:
        logger.debug("  [preprocess] Skew: no lines detected, skipping rotation")
        return img, False

    # Compute angles for each detected line segment
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 == 0:
            continue  # vertical line — skip
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Filter to ±45° to avoid false positives from vertical text / borders
        if -SKEW_MAX_ANGLE <= angle <= SKEW_MAX_ANGLE:
            angles.append(angle)

    if not angles:
        logger.debug("  [preprocess] Skew: no qualifying line angles, skipping rotation")
        return img, False

    median_angle = float(np.median(angles))
    logger.debug(f"  [preprocess] Skew angle detected: {median_angle:.2f}°")

    if abs(median_angle) < SKEW_SKIP_THRESHOLD:
        logger.debug(f"  [preprocess] Skew angle {median_angle:.2f}° below threshold — no rotation needed")
        return img, False

    # Rotate image (negative because PIL rotates counter-clockwise)
    rotated = img.rotate(-median_angle, expand=True, fillcolor=(255, 255, 255))
    logger.debug(f"  [preprocess] Image rotated by -{median_angle:.2f}°")
    return rotated, True


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def _process_single_image(img: Image.Image) -> tuple[Image.Image, list[str]]:
    """
    Apply all 4 preprocessing steps in the correct order to a single PIL image.
    Returns (processed_image, list_of_applied_step_names).
    """
    applied = []

    img, applied_res = normalize_resolution(img)
    if applied_res:
        applied.append("resolution")

    img, applied_bright = correct_brightness(img)
    if applied_bright:
        applied.append("brightness")

    img, applied_noise = remove_noise(img)
    if applied_noise:
        applied.append("noise_removal")

    img, applied_skew = correct_skew(img)
    if applied_skew:
        applied.append("skew_correction")

    return img, applied


def preprocess_image(
    file_path: str,
    output_path: str,
    preprocess_pdf: bool = False,
) -> dict:
    """
    Main entry point. Load the file, apply preprocessing, save to output_path.

    Args:
        file_path:      Absolute path to the original input file.
        output_path:    Absolute path where the preprocessed file will be saved.
        preprocess_pdf: If True, rasterize PDF pages, preprocess each, and
                        reassemble into a new PDF. If False, PDF files are skipped.

    Returns:
        {
            "preprocessed_path": str,   # output_path if processed, file_path if skipped
            "original_path":     str,   # always the original file_path
            "applied_steps":     list,  # names of steps that made changes
            "skipped":           bool,  # True if file type was skipped
        }
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    base_result = {
        "preprocessed_path": file_path,
        "original_path": file_path,
        "applied_steps": [],
        "skipped": False,
    }

    # ── DOCX: always skip ────────────────────────────────────────────────────
    if ext == ".docx":
        logger.info(f"  [preprocess] DOCX detected — skipping preprocessing (no pixel data)")
        base_result["skipped"] = True
        return base_result

    # ── PDF: skip unless preprocess_pdf=True ─────────────────────────────────
    if ext == ".pdf":
        if not preprocess_pdf:
            logger.info(f"  [preprocess] PDF detected and ENABLE_PREPROCESSING_PDF=false — skipping")
            base_result["skipped"] = True
            return base_result

        logger.info(f"  [preprocess] PDF detected — rasterizing and preprocessing each page")
        return _preprocess_pdf(file_path, output_path, base_result)

    # ── Image files (.jpg, .jpeg, .png, .webp) ────────────────────────────────
    return _preprocess_image_file(file_path, output_path, ext, base_result)


def _preprocess_image_file(
    file_path: str,
    output_path: str,
    ext: str,
    base_result: dict,
) -> dict:
    """Handle preprocessing for raster image files."""
    try:
        img = Image.open(file_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            # Flatten transparency onto white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background

        img, applied_steps = _process_single_image(img)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, format="PNG")

        logger.info(f"  [preprocess] Image preprocessed. Steps applied: {applied_steps}. Saved → {output_path}")
        return {
            "preprocessed_path": output_path,
            "original_path": file_path,
            "applied_steps": applied_steps,
            "skipped": False,
        }
    except Exception as e:
        logger.error(f"  [preprocess] Failed to preprocess image '{file_path}': {e}")
        raise


def _preprocess_pdf(
    file_path: str,
    output_path: str,
    base_result: dict,
) -> dict:
    """
    Rasterize each PDF page at PDF_DPI, apply preprocessing to each page,
    then reassemble into a new multi-page PDF.
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        processed_pages: list[Image.Image] = []
        all_applied: set[str] = set()

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=PDF_DPI)
            page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            page_img, applied = _process_single_image(page_img)
            all_applied.update(applied)
            processed_pages.append(page_img)
            logger.debug(f"  [preprocess] PDF page {page_idx + 1}/{len(doc)} preprocessed. Steps: {applied}")

        doc.close()

        if not processed_pages:
            logger.warning(f"  [preprocess] PDF had no pages to process")
            base_result["skipped"] = True
            return base_result

        # Save as multi-page PDF using PIL
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # PIL saves multi-page PDFs by passing append_images
        processed_pages[0].save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=processed_pages[1:],
        )

        logger.info(f"  [preprocess] PDF preprocessed ({len(processed_pages)} pages). Steps: {list(all_applied)}. Saved → {output_path}")
        return {
            "preprocessed_path": output_path,
            "original_path": file_path,
            "applied_steps": sorted(all_applied),
            "skipped": False,
        }
    except ImportError:
        logger.warning("  [preprocess] PyMuPDF (fitz) not available — skipping PDF preprocessing")
        base_result["skipped"] = True
        return base_result
    except Exception as e:
        logger.error(f"  [preprocess] Failed to preprocess PDF '{file_path}': {e}")
        raise

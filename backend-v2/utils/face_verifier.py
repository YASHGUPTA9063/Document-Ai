"""
Face Verification Pipeline
============================
Multi-agent forensic face comparison using Mistral AI Agents API.

Runs three analysis agents in parallel:
  1. Morphology Part 1 — upper/mid-face structure (face shape, eyes, nose)
  2. Morphology Part 2 — lower-face features (mouth, ears, jaw, marks)
  3. Age Variation — cross-age analysis (separates aging from identity mismatch)

After all three complete, a Judge agent receives their outputs and returns a verdict:
  1 = DIFFERENT PERSON, 3 = NEEDS HUMAN REVIEW, 5 = SAME PERSON

Adapted from the standalone agentic_face_match.py shared by the team.

Requires:
    - MISTRAL_API_KEY environment variable
    - pip install mistralai opencv-python-headless pillow numpy
"""

import os
import json
import asyncio
import base64
import logging
import re
import mimetypes
from typing import Optional

import cv2
import numpy as np

from mistralai.client import Mistral  # retained for type annotations only
from platform_core.adapters.resilient_mistral import get_mistral_client

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. IMAGE PREPROCESSING
# ---------------------------------------------------------------------------

def preprocess_face_image(image_path: str, out_path: str) -> str:
    """
    Lightweight face-image preprocessing using OpenCV.
    Applies CLAHE contrast enhancement, gamma correction, and mild sharpening.
    Falls back to raw copy if OpenCV encounters issues.
    Returns the path of the processed image.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"cv2 could not read: {image_path}")

        # ── Resize to consistent resolution ──────────────────
        target = 512
        h, w = img.shape[:2]
        if max(h, w) > target:
            scale = target / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_AREA)

        # ── CLAHE on L channel (LAB) ──────────────────────────
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

        # ── Gamma correction if underexposed ─────────────────
        mean_l = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[:, :, 0].mean()
        if mean_l < 80:
            gamma = 0.7
            table = np.array([(i / 255.0) ** gamma * 255
                              for i in range(256)], dtype=np.uint8)
            img = cv2.LUT(img, table)

        # ── Mild sharpening via unsharp mask ─────────────────
        blur = cv2.GaussianBlur(img, (0, 0), 3)
        img = cv2.addWeighted(img, 1.4, blur, -0.4, 0)

        cv2.imwrite(out_path, img)
        return out_path

    except Exception as e:
        logger.warning(f"Face preprocessing warning ({image_path}): {e} — using original")
        import shutil
        shutil.copy2(image_path, out_path)
        return out_path


# ---------------------------------------------------------------------------
# 2. IMAGE UTILITIES
# ---------------------------------------------------------------------------

def encode_image_base64(image_path: str) -> tuple:
    """Return (base64_string, mime_type) for an image file."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, mime_type


# ---------------------------------------------------------------------------
# 3. RESPONSE PARSING
# ---------------------------------------------------------------------------

def _extract_text(response) -> str:
    """Pull assistant text from a Mistral conversation response object."""
    if hasattr(response, "outputs"):
        parts = []
        for output in response.outputs:
            if hasattr(output, "content"):
                if isinstance(output.content, str):
                    parts.append(output.content)
                elif isinstance(output.content, list):
                    for item in output.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(item["text"])
                        elif hasattr(item, "text"):
                            parts.append(item.text)
            elif hasattr(output, "text"):
                parts.append(output.text)
        if parts:
            return "\n".join(parts)
    return str(response)


def _parse_json_response(raw: str, agent_name: str) -> dict:
    """
    Attempt to parse agent JSON output.
    Strips markdown fences if present.
    Returns parsed dict or error dict on failure.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for {agent_name}: {e}")
        return {
            "agent": agent_name,
            "parse_error": str(e),
            "raw_response": raw[:500],
            "signal": "inconclusive"
        }


# ---------------------------------------------------------------------------
# 4. AGENT EXECUTION
# ---------------------------------------------------------------------------

async def run_face_analysis_agent(
    client: Mistral,
    agent_id: str,
    b64_a: str, mime_a: str,
    b64_b: str, mime_b: str,
    label: str
) -> dict:
    """
    Send both face images to a morphology/age analysis agent.
    Returns parsed JSON dict.
    """
    logger.info(f"[FaceVerify] {label} started...")

    response = await client.beta.conversations.start_async(
        agent_id=agent_id,
        inputs=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Image A is the first image. Image B is the second image. "
                            "Perform your full analysis. Return JSON only."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_a};base64,{b64_a}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_b};base64,{b64_b}"},
                    },
                ],
            }
        ],
    )

    raw = _extract_text(response)
    result = _parse_json_response(raw, label)
    logger.info(f"[FaceVerify] {label} complete.")
    return result


async def run_face_judge_agent(
    client: Mistral,
    agent_id: str,
    mod1: dict, mod2: dict, mod3: dict
) -> str:
    """
    Send the three module JSON outputs (text only, no images) to the judge.
    Returns raw string — expected to be exactly '1', '3', or '5'.
    """
    logger.info("[FaceVerify] Final Judge started...")

    judge_input = (
        "MODULE 1 — Morphology Part 1 (Geometry, Eyes, Nose):\n"
        f"{json.dumps(mod1, indent=2)}\n\n"
        "MODULE 2 — Morphology Part 2 (Mouth, Ears, Jaw, Secondary):\n"
        f"{json.dumps(mod2, indent=2)}\n\n"
        "MODULE 3 — Age Variation Analysis:\n"
        f"{json.dumps(mod3, indent=2)}\n\n"
        "Based on the above three module outputs, return only 1, 3, or 5."
    )

    response = await client.beta.conversations.start_async(
        agent_id=agent_id,
        inputs=[
            {
                "role": "user",
                "content": [{"type": "text", "text": judge_input}],
            }
        ],
    )

    raw = _extract_text(response).strip()
    logger.info(f"[FaceVerify] Final Judge complete: {raw}")
    return raw


def extract_final_score(judge_response: str) -> int:
    """
    Parse the verdict integer from the judge's response.
    Primary: look for a lone 1/3/5 token.
    Fallback: keyword detection.
    Default: 3 (human review).
    """
    stripped = judge_response.strip()
    if stripped in ("1", "3", "5"):
        return int(stripped)

    match = re.search(r"\b([135])\b", stripped)
    if match:
        return int(match.group(1))

    lower = stripped.lower()
    if "different" in lower:
        return 1
    if "same" in lower:
        return 5

    return 3


# ---------------------------------------------------------------------------
# 5. ORCHESTRATOR — runs 3 agents in parallel, then Judge
# ---------------------------------------------------------------------------

async def run_face_verification_pipeline(
    doc_path: str,
    ref_path: str,
    debug_dir: Optional[str] = None
) -> dict:
    """
    Main face verification pipeline:
      Preprocess → Encode → 3 Agents ∥ → Judge → Verdict

    Args:
        doc_path: Path to the photo extracted from the document.
        ref_path: Path to the reference photo uploaded by the user.
        debug_dir: Optional directory for debug images.

    Returns:
        {
            "module1": {...},
            "module2": {...},
            "module3": {...},
            "judge_raw": "1|3|5",
            "output_code": 1|3|5,
            "verdict": "same_person"|"different_person"|"needs_review",
            "verdict_label": "SAME PERSON"|"DIFFERENT PERSON"|"NEEDS REVIEW"
        }
    """
    import tempfile

    client = get_mistral_client()

    # ── Step 1: Preprocess images ──────────────────────────────
    logger.info("[FaceVerify] Preprocessing images...")
    tmp_dir = debug_dir or tempfile.mkdtemp(prefix="face_verify_pp_")

    proc_a = preprocess_face_image(doc_path, os.path.join(tmp_dir, "preprocessed_a.jpg"))
    proc_b = preprocess_face_image(ref_path, os.path.join(tmp_dir, "preprocessed_b.jpg"))

    # ── Step 2: Encode to base64 ───────────────────────────────
    logger.info("[FaceVerify] Encoding images...")
    b64_a, mime_a = encode_image_base64(proc_a)
    b64_b, mime_b = encode_image_base64(proc_b)
    logger.info(f"[FaceVerify] Image A: {len(b64_a) // 1024} KB, Image B: {len(b64_b) // 1024} KB")

    # ── Step 3: Run three agents in parallel ───────────────────
    logger.info("[FaceVerify] Running 3 analysis agents in parallel...")

    mod1_task = run_face_analysis_agent(
        client,
        settings.FACE_MORPHOLOGY1_AGENT_ID,
        b64_a, mime_a, b64_b, mime_b,
        "Module 1 — Morphology Part 1 (Geometry/Eyes/Nose)"
    )

    mod2_task = run_face_analysis_agent(
        client,
        settings.FACE_MORPHOLOGY2_AGENT_ID,
        b64_a, mime_a, b64_b, mime_b,
        "Module 2 — Morphology Part 2 (Mouth/Ears/Secondary)"
    )

    mod3_task = run_face_analysis_agent(
        client,
        settings.FACE_AGE_AGENT_ID,
        b64_a, mime_a, b64_b, mime_b,
        "Module 3 — Age Variation"
    )

    results = await asyncio.gather(mod1_task, mod2_task, mod3_task, return_exceptions=True)

    module_results = {}
    module_keys = ["module1", "module2", "module3"]
    for key, result in zip(module_keys, results):
        if isinstance(result, Exception):
            logger.error(f"[FaceVerify] {key} failed: {result}")
            module_results[key] = {
                "agent": key,
                "error": str(result),
                "signal": "inconclusive"
            }
        else:
            module_results[key] = result

    logger.info("[FaceVerify] All 3 analysis agents finished.")

    # ── Step 4: Run Judge ──────────────────────────────────────
    logger.info("[FaceVerify] Running final arbitration judge...")
    judge_raw = await run_face_judge_agent(
        client,
        settings.FACE_JUDGE_AGENT_ID,
        module_results["module1"],
        module_results["module2"],
        module_results["module3"],
    )

    # ── Step 5: Extract verdict ────────────────────────────────
    score = extract_final_score(judge_raw)
    verdicts = {
        1: ("different_person", "DIFFERENT PERSON"),
        3: ("needs_review", "NEEDS REVIEW"),
        5: ("same_person", "SAME PERSON"),
    }
    verdict, verdict_label = verdicts.get(score, ("needs_review", "NEEDS REVIEW"))

    logger.info(f"[FaceVerify] FINAL RESULT → {score} ({verdict_label})")

    # Cleanup preprocessed files if we created a temp dir
    if not debug_dir:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "module1": module_results["module1"],
        "module2": module_results["module2"],
        "module3": module_results["module3"],
        "judge_raw": judge_raw,
        "output_code": score,
        "verdict": verdict,
        "verdict_label": verdict_label,
    }

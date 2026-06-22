"""
Signature Verification Pipeline
================================
Runs two parallel processes:
  1. DINO Process  – Preprocesses both images and compares DINOv2 embeddings.
     DINOv2 Preprocessing: Load Image -> Grayscale -> Binarization (Otsu/Sauvola)
     -> Tight Crop -> Resize & Pad (224x224) -> RGB Stack -> PyTorch Normalize
  2. Mistral Vision Process – Sends both raw images to a Mistral Agent (mistral-small-latest)
     for a visual similarity assessment (no preprocessing).

After both finish, a Mistral Judge Agent receives both outputs and returns a final JSON verdict.

Adapted from the standalone advanced_latest_signature_verifier.py shared by the team.

Requires:
    - MISTRAL_API_KEY environment variable
    - pip install mistralai torch torchvision transformers opencv-python-headless pillow scikit-image numpy
"""

import os
import json
import asyncio
import base64
import logging
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from skimage.filters import threshold_sauvola
from torchvision import transforms
import torch
from transformers import AutoModel
from mistralai.client import Mistral

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. DINO PROCESS — Singleton Model
# ---------------------------------------------------------------------------

class DinoVerifier:
    """Wraps the DINOv2-based signature comparison pipeline.
    
    Uses a singleton pattern — call DinoVerifier.get_instance() to reuse the 
    model across requests, or DinoVerifier.preload() at startup.
    """

    _instance: Optional["DinoVerifier"] = None

    def __init__(self, debug_dir=None, fast_mode=True):
        self.debug_dir = debug_dir
        self.fast_mode = fast_mode
        if self.debug_dir:
            os.makedirs(self.debug_dir, exist_ok=True)

        # Load DINOv2 model once
        logger.info("[DinoVerifier] Loading DINOv2 model (facebook/dinov2-small)...")
        self.model = AutoModel.from_pretrained("facebook/dinov2-small")
        self.model.eval()
        logger.info("[DinoVerifier] DINOv2 model loaded successfully.")

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    @classmethod
    def get_instance(cls) -> "DinoVerifier":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def preload(cls) -> "DinoVerifier":
        """Eagerly load the model (call at server startup)."""
        logger.info("[DinoVerifier] Preloading model at startup...")
        cls._instance = cls()
        return cls._instance

    # -- helpers -------------------------------------------------------------

    def _save_debug(self, img, step, prefix=""):
        if self.debug_dir:
            cv2.imwrite(os.path.join(self.debug_dir, f"{prefix}_{step}.png"), img)

    def _preprocess(self, path: str, prefix: str = ""):
        """Load, binarise, crop, resize → 224×224 RGB tensor."""
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot load image: {path}")
        self._save_debug(img, "original", prefix)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if self.fast_mode:
            _, clean = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            bg = cv2.medianBlur(gray, 51)
            fg = cv2.subtract(bg, gray)
            fg_norm = cv2.normalize(fg, None, 0, 255, cv2.NORM_MINMAX)
            thresh = threshold_sauvola(fg_norm, window_size=25, k=0.2)
            binary = (fg_norm > thresh).astype(np.uint8) * 255
            inverted = cv2.bitwise_not(binary)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inverted)
            clean = np.zeros_like(inverted)
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] >= 50:
                    clean[labels == i] = 255

        # Tight crop
        coords = cv2.findNonZero(clean)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            pad = 10
            cropped = clean[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
            aspect_ratio = w / max(h, 1)
        else:
            cropped = clean
            aspect_ratio = 1.0

        # Resize + pad to 224×224
        target = 224
        h, w = cropped.shape[:2]
        if h == 0 or w == 0:
            resized = cropped
        else:
            scale = min(target / w, target / h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(cropped, (max(new_w, 1), max(new_h, 1)), interpolation=cv2.INTER_AREA)

        canvas = np.zeros((target, target), dtype=np.uint8)
        if resized.shape[0] <= target and resized.shape[1] <= target:
            y_off = (target - resized.shape[0]) // 2
            x_off = (target - resized.shape[1]) // 2
            canvas[y_off:y_off + resized.shape[0], x_off:x_off + resized.shape[1]] = resized

        rgb = np.stack([canvas] * 3, axis=-1)
        tensor = self.transform(Image.fromarray(rgb))
        return tensor, aspect_ratio

    # -- public API ----------------------------------------------------------

    def verify(self, doc_path: str, ref_path: str,
               t_match: float = 0.75, t_reject: float = 0.55) -> dict:
        """Compare two signature images and return score + decision."""
        tensor_doc, ar_doc = self._preprocess(doc_path, prefix="doc")
        tensor_ref, ar_ref = self._preprocess(ref_path, prefix="ref")

        with torch.no_grad():
            batch = torch.stack([tensor_doc, tensor_ref])
            embeddings = self.model(batch).last_hidden_state[:, 0, :]
            embeddings = torch.nn.functional.normalize(embeddings, dim=1)

        score = torch.nn.functional.cosine_similarity(
            embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)
        ).item()

        ar_diff = abs(ar_doc - ar_ref)
        if ar_diff > 1.5:
            score -= 0.05

        if score >= t_match:
            decision = "MATCH"
        elif score >= t_reject:
            decision = "REVIEW"
        else:
            decision = "MISMATCH"

        return {"score": round(score, 4), "decision": decision, "ar_diff": round(ar_diff, 4)}


# ---------------------------------------------------------------------------
# 2. MISTRAL VISION PROCESS
# ---------------------------------------------------------------------------

def _encode_image_base64(path: str) -> tuple:
    """Return (base64_data, mime_type) for a local image file."""
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        mime = "image/png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, mime


async def run_mistral_vision(client: Mistral, doc_path: str, ref_path: str) -> dict:
    """
    Create a Mistral Agent, start a conversation with both images,
    and return the agent's similarity assessment.
    """
    # Create the vision agent
    vision_agent = await client.beta.agents.create_async(
        model="mistral-small-latest",
        name="Signature Vision Agent",
        description="Compares two signature images visually and returns a similarity assessment.",
        instructions=(
            """You are a forensic signature analysis expert. You will be given two signature images:
- Image 1: REFERENCE signature (known genuine)
- Image 2: TEST signature (to be verified)

Your task is to perform a detailed visual comparison across all forensic dimensions and return a structured JSON analysis.

ANALYSIS INSTRUCTIONS:

Examine the following dimensions carefully for each dimension assign a score from 0 to 100
where 100 = perfect match, 0 = completely different.

1. STROKE FLOW
   - Is the pen movement natural and continuous in both?
   - Does the rhythm and speed of strokes appear consistent?
   - Are curves smooth or do they show signs of slow tracing?

2. STROKE THICKNESS VARIATION
   - Compare pressure patterns — thick downstrokes, thin upstrokes
   - Is the ink weight distribution consistent between both signatures?

3. LOOP MORPHOLOGY
   - Compare shape, size, and openness of all loops
   - Look at letters like: l, b, p, g, f, or any looped flourish

4. CONNECTIVITY PATTERN
   - Identify where pen lifts occur in the reference
   - Do the same pen lift positions appear in the test signature?

5. ENTRY AND EXIT STROKES
   - How does the signature begin? (hook, lead-in stroke, direct start)
   - How does it end? (flourish, tail, abrupt stop)
   - Do both match?

6. SLANT ANGLE
   - Estimate the dominant slant angle in both
   - Note: consistent rightward/leftward lean, or mixed?

7. BASELINE ALIGNMENT
   - Does the signature follow the same imaginary baseline?
   - Is there any upward or downward drift in the test sample?

8. PROPORTIONS
   - Compare height-to-width ratio of the overall signature
   - Compare relative sizes of individual components

9. SPACING
   - Are gaps between connected elements consistent?

10. AUTHENTICITY FLAGS — Look specifically for:
    - Tremor or shakiness in strokes (indicates slow drawing / nervous hand)
    - Retouching: strokes drawn twice or corrected
    - Hesitation marks: tiny pauses mid-stroke visible as ink pools or blobs
    - Unnatural slowness: curves that are too perfect / deliberate
    - Pen lift mismatches: lifts where reference has none, or vice versa

11. UNIQUE IDIOSYNCRATIC FEATURES
    - Identify any unique marks in the reference: underlines, dots, flourishes, abbreviations, symbols
    - Are they present and matching in the test signature?

OUTPUT FORMAT:
Return ONLY valid JSON. No explanation text outside the JSON.

{
  "llm_visual_score": <number 0-100>,
  "structural_analysis": {
    "stroke_flow": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "stroke_thickness": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "loop_morphology": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "connectivity_pattern": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "entry_exit_strokes": { "score": <0-100>, "observation": "<1-2 sentences>" }
  },
  "spatial_analysis": {
    "slant_angle": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "baseline_alignment": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "proportions": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "spacing": { "score": <0-100>, "observation": "<1-2 sentences>" }
  },
  "authenticity_flags": {
    "tremor_detected": <true|false>,
    "retouching_detected": <true|false>,
    "hesitation_marks": <true|false>,
    "unnatural_slowness": <true|false>,
    "pen_lift_mismatch": <true|false>,
    "flag_details": "<describe any detected flags or write 'No anomalies detected'>"
  },
  "unique_features": {
    "idiosyncratic_marks_present": <true|false>,
    "marks_match": <true|false>,
    "details": "<describe the unique marks found and whether they match>"
  },
  "agent1_summary": "<3-4 sentence forensic summary of your overall visual finding>"
}"""
        ),
    )

    # Encode both images as base64 data URLs
    doc_b64, doc_mime = _encode_image_base64(doc_path)
    ref_b64, ref_mime = _encode_image_base64(ref_path)

    # Build multimodal input
    inputs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Compare these two signatures:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{doc_mime};base64,{doc_b64}"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{ref_mime};base64,{ref_b64}"},
                },
            ],
        }
    ]

    # Start a conversation with the agent
    response = await client.beta.conversations.start_async(
        agent_id=vision_agent.id,
        inputs=inputs,
    )

    # Extract assistant reply
    raw_text = ""
    for entry in (response.outputs or []):
        if hasattr(entry, "content") and entry.content:
            raw_text = entry.content
            break
        if hasattr(entry, "text") and entry.text:
            raw_text = entry.text
            break

    # Try to parse JSON from the response
    try:
        # Strip markdown code fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        result = json.loads(cleaned.strip())
    except (json.JSONDecodeError, TypeError):
        result = {"raw_response": raw_text}

    # Cleanup: delete the agent
    try:
        await client.beta.agents.delete_async(agent_id=vision_agent.id)
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# 3. MISTRAL JUDGE PROCESS
# ---------------------------------------------------------------------------

async def run_judge(client: Mistral, dino_result: dict, mistral_result: dict) -> dict:
    """
    Create a Judge Agent that receives both DINO and Mistral Vision outputs
    and returns a final JSON verdict.
    """
    judge_agent = await client.beta.agents.create_async(
        model="mistral-small-latest",
        name="Signature Judge Agent",
        description="Judges signature verification results from two independent systems.",
        instructions=(
            """You are a senior signature verification judge. You will receive two inputs:

1. EMBEDDING SCORE: A cosine similarity score (0.0 to 1.0) computed using DINOv2 
   visual embeddings between the reference and test signature images.

2. VISUAL ANALYSIS: A structured forensic analysis JSON produced by a vision LLM 
   that compared the two signature images across structural, spatial, and 
   authenticity dimensions.

Your task is to synthesize both inputs and produce a final authoritative verdict JSON.

---

INPUTS YOU WILL RECEIVE:

Embedding Cosine Score: {embedding_cosine_score}

Visual Analysis JSON: {agent1_output}

---

SCORING RULES:

Compute the combined_weighted_score as:
  combined_weighted_score = (embedding_cosine_score * 100 * 0.40) + (llm_visual_score * 0.60)

OVERRIDE RULES — Apply these strictly:
- If ANY of these flags are true: tremor_detected, retouching_detected, hesitation_marks
  → Reduce combined_weighted_score by 15 points (apply once, not per flag)
  → Set risk_level to at least "high"
  → Set verdict to "forged" if combined_weighted_score drops below 60 after reduction

- If pen_lift_mismatch is true AND unnatural_slowness is true
  → Additional -10 point penalty
  → Escalate risk_level by one level

- If unique_features.idiosyncratic_marks_present is true AND unique_features.marks_match is false
  → Hard override: set verdict to "forged" regardless of score
  → Set confidence to max 40
  → Set risk_level to "critical"

VERDICT THRESHOLDS (after all overrides):
  combined_weighted_score >= 80 → verdict: "genuine"
  combined_weighted_score 60-79 → verdict: "uncertain"
  combined_weighted_score < 60 → verdict: "forged"

RISK LEVEL:
  score >= 85 → "low"
  score 70-84 → "medium"
  score 55-69 → "high"
  score < 55 → "critical"

CONFIDENCE:
  Reflect your certainty in the verdict (0-100).
  Reduce confidence if: embedding and visual scores diverge by more than 20 points,
  or if multiple flags are true but score is still borderline.

---

RECOMMENDATION RULES:
  verdict = "genuine" → "Accept"
  verdict = "uncertain" → "Manual Review Required"
  verdict = "forged" → "Reject — Escalate to Fraud Team"

---

OUTPUT FORMAT:
Return ONLY valid JSON. No explanation text outside the JSON. No markdown. 
Do not wrap in code blocks. Start directly with the opening brace.

{
  "verdict": "<genuine|forged|uncertain>",
  "risk_level": "<low|medium|high|critical>",
  "confidence": <0-100>,

  "scores": {
    "embedding_cosine_score": <float from input>,
    "llm_visual_score": <from agent1 output>,
    "combined_weighted_score": <computed value>,
    "penalties_applied": <number>,
    "penalty_reasons": ["<reason1>", "<reason2>"]
  },

  "structural_analysis": <copy structural_analysis object from agent1 output>,
  "spatial_analysis": <copy spatial_analysis object from agent1 output>,

  "authenticity_flags": <copy authenticity_flags object from agent1 output>,
  "unique_features": <copy unique_features object from agent1 output>,

  "override_applied": <true|false>,
  "override_reason": "<describe which override rule triggered, or null if none>",

  "summary": "<4-5 sentence final verdict summary explaining the decision, key evidence, and any flags>",
  "recommendation": "<Accept|Manual Review Required|Reject — Escalate to Fraud Team>",

  "metadata": {
    "embedding_model": "dinov2-small",
    "preprocessing": ["grayscale", "invert", "binarize"],
    "scoring_weights": { "embedding": 0.40, "llm_visual": 0.60 },
    "analysis_timestamp": "<ISO 8601 timestamp>"
  }
}"""
        ),
    )

    # Build the judge prompt with both results
    judge_input = (
        f"## DINO System Result\n```json\n{json.dumps(dino_result, indent=2)}\n```\n\n"
        f"## Mistral Vision Agent Result\n```json\n{json.dumps(mistral_result, indent=2)}\n```\n\n"
        "Based on these two assessments, provide your final verdict."
    )

    response = await client.beta.conversations.start_async(
        agent_id=judge_agent.id,
        inputs=judge_input,
    )

    # Extract assistant reply
    raw_text = ""
    for entry in (response.outputs or []):
        if hasattr(entry, "content") and entry.content:
            raw_text = entry.content
            break
        if hasattr(entry, "text") and entry.text:
            raw_text = entry.text
            break

    # Parse JSON
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        result = json.loads(cleaned.strip())
    except (json.JSONDecodeError, TypeError):
        result = {"raw_response": raw_text}

    # Cleanup
    try:
        await client.beta.agents.delete_async(agent_id=judge_agent.id)
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# 4. ORCHESTRATOR — runs DINO & Mistral Vision in parallel, then Judge
# ---------------------------------------------------------------------------

async def run_verification_pipeline(doc_path: str, ref_path: str, debug_dir: str = None) -> dict:
    """
    Main pipeline: DINO ∥ Mistral Vision → Judge.
    
    Args:
        doc_path: Path to the signature extracted from the document (test signature).
        ref_path: Path to the reference signature uploaded by the user.
        debug_dir: Optional directory for DINO debug images.
    
    Returns:
        {
            "dino": {...},
            "mistral_vision": {...},
            "judge": {...},
            "output_code": 1|3|5,
            "verdict": "genuine"|"forged"|"uncertain"
        }
    """
    client = Mistral(api_key=settings.MISTRAL_API_KEY)

    # -- Run DINO in a thread (it's CPU-bound / synchronous) ----------------
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    def _dino_work():
        verifier = DinoVerifier.get_instance()
        return verifier.verify(doc_path, ref_path)

    dino_task = loop.run_in_executor(executor, _dino_work)

    # -- Run Mistral Vision as an async coroutine ---------------------------
    logger.info("[Verification] Starting DINO ∥ Mistral Vision parallel processes...")
    mistral_task = asyncio.ensure_future(run_mistral_vision(client, doc_path, ref_path))

    # -- Await both concurrently --------------------------------------------
    dino_result, mistral_result = await asyncio.gather(dino_task, mistral_task)

    logger.info(f"[Verification] DINO result: {json.dumps(dino_result)}")
    logger.info(f"[Verification] Mistral Vision result keys: {list(mistral_result.keys())}")

    # -- Run Judge (only after both are done) --------------------------------
    logger.info("[Verification] Both processes complete. Running Judge agent...")
    judge_result = await run_judge(client, dino_result, mistral_result)

    logger.info(f"[Verification] Judge verdict: {judge_result.get('verdict', 'unknown')}")

    # Determine simple output code for clients
    # 1 = rejected (forged), 3 = review (uncertain), 5 = matching (genuine)
    verdict = judge_result.get("verdict", "").lower()
    if "genuine" in verdict:
        output_code = 5
    elif "uncertain" in verdict:
        output_code = 3
    elif "forged" in verdict:
        output_code = 1
    else:
        # Fallback to recommendation or dino decision
        rec = judge_result.get("recommendation", "").lower()
        if "accept" in rec:
            output_code = 5
        elif "review" in rec or "uncertain" in rec:
            output_code = 3
        elif "reject" in rec or "forged" in rec:
            output_code = 1
        else:
            dino_decision = dino_result.get("decision", "").lower()
            if dino_decision == "match":
                output_code = 5
            elif dino_decision == "review":
                output_code = 3
            else:
                output_code = 1

    return {
        "dino": dino_result,
        "mistral_vision": mistral_result,
        "judge": judge_result,
        "output_code": output_code,
        "verdict": verdict or "unknown",
    }

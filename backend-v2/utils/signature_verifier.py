"""
Signature Verification Pipeline
================================
Runs two parallel processes:
  1. DINO Process  – Preprocesses both images and compares DINOv2 embeddings.
  2. Vision LLM Process – Sends both raw images to a VisionProvider
     for a visual similarity assessment (no preprocessing).

After both finish, a Judge LLM receives both outputs and returns a final JSON verdict.

MIGRATED from direct Mistral SDK to provider-agnostic ProviderRegistry.
- client.beta.conversations.start_async() → registry.get_vision().analyze()
- Mistral Judge Agent → registry.get_llm().chat() with signature_judge prompt
"""

import os
import json
import asyncio
import base64
import logging
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import _parse_json_response, run_simple_completion

logger = logging.getLogger(__name__)
prompts = PromptManager()


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
        from transformers import AutoModel
        from torchvision import transforms
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
            import cv2
            cv2.imwrite(os.path.join(self.debug_dir, f"{prefix}_{step}.png"), img)

    def _preprocess(self, path: str, prefix: str = ""):
        """Load, binarise, crop, resize → 224×224 RGB tensor."""
        import cv2
        import numpy as np
        from skimage.filters import threshold_sauvola
        from PIL import Image

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

        import torch
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
# 2. VISION LLM PROCESS (provider-agnostic)
# ---------------------------------------------------------------------------

def _encode_image_base64(path: str) -> tuple:
    """Return (base64_data, mime_type) for a local image file."""
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        mime = "image/png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, mime


async def run_vision_analysis(doc_path: str, ref_path: str) -> dict:
    """
    Send both raw images to the VisionProvider for a visual similarity assessment.
    Replaces: client.beta.conversations.start_async(agent_id=SIGNATURE_VISION_AGENT_ID, ...)
    """
    registry = ProviderRegistry.get()
    vision = registry.get_vision()
    system_prompt = prompts.get("signature_vision")

    doc_b64, doc_mime = _encode_image_base64(doc_path)
    ref_b64, ref_mime = _encode_image_base64(ref_path)

    response = await vision.analyze(
        images=[
            f"data:{ref_mime};base64,{ref_b64}",
            f"data:{doc_mime};base64,{doc_b64}",
        ],
        prompt=f"Compare these two signatures:\n\n{system_prompt}",
        response_format={"type": "json_object"},
    )

    try:
        result = _parse_json_response(response.content)
    except (ValueError, Exception):
        result = {"raw_response": response.content}

    return result


# ---------------------------------------------------------------------------
# 3. JUDGE PROCESS (provider-agnostic)
# ---------------------------------------------------------------------------

async def run_judge(dino_result: dict, vision_result: dict) -> dict:
    """
    Send both DINO and Vision outputs to the LLM for a final JSON verdict.
    Replaces: client.beta.conversations.start_async(agent_id=SIGNATURE_JUDGE_AGENT_ID, ...)
    """
    registry = ProviderRegistry.get()
    llm = registry.get_llm()
    system_prompt = prompts.get("signature_judge")

    judge_input = (
        f"## DINO System Result\n```json\n{json.dumps(dino_result, indent=2)}\n```\n\n"
        f"## Vision Agent Result\n```json\n{json.dumps(vision_result, indent=2)}\n```\n\n"
        "Based on these two assessments, provide your final verdict."
    )

    result = await run_simple_completion(
        llm=llm,
        system_prompt=system_prompt,
        user_message=judge_input,
        temperature=0.2,
    )

    return result


# ---------------------------------------------------------------------------
# 4. ORCHESTRATOR — runs DINO & Vision in parallel, then Judge
# ---------------------------------------------------------------------------

async def run_verification_pipeline(doc_path: str, ref_path: str, debug_dir: str = None) -> dict:
    """
    Main pipeline: DINO ∥ Vision LLM → Judge.
    
    Args:
        doc_path: Path to the signature extracted from the document (test signature).
        ref_path: Path to the reference signature uploaded by the user.
        debug_dir: Optional directory for DINO debug images.
    
    Returns:
        {
            "dino": {...},
            "vision_analysis": {...},
            "judge": {...},
            "output_code": 1|3|5,
            "verdict": "genuine"|"forged"|"uncertain"
        }
    """
    # -- Run DINO in a thread (it's CPU-bound / synchronous) ----------------
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    def _dino_work():
        verifier = DinoVerifier.get_instance()
        return verifier.verify(doc_path, ref_path)

    dino_task = loop.run_in_executor(executor, _dino_work)

    # -- Run Vision LLM as an async coroutine ---------------------------
    logger.info("[Verification] Starting DINO ∥ Vision LLM parallel processes...")
    vision_task = asyncio.ensure_future(run_vision_analysis(doc_path, ref_path))

    # -- Await both concurrently --------------------------------------------
    dino_result, vision_result = await asyncio.gather(dino_task, vision_task)

    logger.info(f"[Verification] DINO result: {json.dumps(dino_result)}")
    logger.info(f"[Verification] Vision result keys: {list(vision_result.keys())}")

    # -- Run Judge (only after both are done) --------------------------------
    logger.info("[Verification] Both processes complete. Running Judge...")
    judge_result = await run_judge(dino_result, vision_result)

    logger.info(f"[Verification] Judge verdict: {judge_result.get('verdict', 'unknown')}")

    # Determine simple output code
    verdict = judge_result.get("verdict", "").lower()
    if "genuine" in verdict:
        output_code = 5
    elif "uncertain" in verdict:
        output_code = 3
    elif "forged" in verdict:
        output_code = 1
    else:
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
        "vision_analysis": vision_result,
        "judge": judge_result,
        "output_code": output_code,
        "verdict": verdict or "unknown",
    }

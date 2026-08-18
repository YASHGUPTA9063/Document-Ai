"""
DINOv2 Embedding Provider
==========================
Implements EmbeddingProvider interface using Facebook's DINOv2 model
for visual similarity comparison (signature/face verification).

Derived from utils/signature_verifier.py DinoVerifier class which:
    - Loads 'facebook/dinov2-small' model at startup
    - Preprocesses images: grayscale → binary → crop → resize 224×224 → normalize
    - Computes cosine similarity between CLS token embeddings
"""

import os
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from platform_core.providers.interfaces import (
    EmbeddingProvider,
    EmbeddingResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)


class DINOv2Embedding(EmbeddingProvider):
    """
    DINOv2-based embedding provider for image comparison.

    Source reference:
        - utils/signature_verifier.py:47-179 — DinoVerifier class
        - Uses singleton pattern — model loaded once, reused across requests

    This provider replaces the DinoVerifier singleton with a proper
    provider interface that the ProviderRegistry manages.
    """

    def __init__(
        self,
        model: str = "facebook/dinov2-small",
        device: str = "cpu",
        fast_mode: bool = True,
    ):
        self._model_name = model
        self._device = device
        self._fast_mode = fast_mode
        self._executor = ThreadPoolExecutor(max_workers=2)

        # Load model (current code: signature_verifier.py:63-66)
        logger.info(f"[DINOv2] Loading model: {model}")
        from transformers import AutoModel
        from torchvision import transforms
        self._model = AutoModel.from_pretrained(model)
        self._model.eval()
        self._model.to(device)
        logger.info(f"[DINOv2] Model loaded on {device}")

        # ImageNet normalization (current code: signature_verifier.py:68-74)
        self._transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

    @property
    def name(self) -> str:
        return "dinov2"

    async def embed(self, inputs: list[str] | list[bytes]) -> EmbeddingResponse:
        """
        Generate embeddings for text strings or raw bytes.
        For DINOv2, inputs should be image file paths.
        """
        return await self.embed_images(inputs)

    async def embed_images(self, image_paths: list[str]) -> EmbeddingResponse:
        """
        Generate DINOv2 CLS token embeddings for image files.

        Each image goes through the preprocessing pipeline from
        signature_verifier.py:96-149:
            Load → Grayscale → Binarize → Crop → Resize 224×224 → RGB → Normalize

        Returns normalized embeddings that can be compared with cosine similarity.
        """
        import asyncio

        # Run the compute-heavy preprocessing + inference in a thread
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            self._executor, self._compute_embeddings, image_paths
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self._model_name,
            provider="dinov2",
        )

    def _compute_embeddings(self, image_paths: list[str]) -> list[list[float]]:
        """Synchronous embedding computation (runs in thread pool)."""
        import torch
        tensors = []
        for path in image_paths:
            tensor = self._preprocess(path)
            tensors.append(tensor)

        batch = torch.stack(tensors).to(self._device)

        with torch.no_grad():
            output = self._model(batch).last_hidden_state[:, 0, :]  # CLS token
            embeddings = torch.nn.functional.normalize(output, dim=1)

        return embeddings.cpu().tolist()

    def _preprocess(self, path: str) -> "torch.Tensor":
        """
        Full preprocessing pipeline from signature_verifier.py:96-149.

        Load → Grayscale → Binarize (Otsu or Sauvola) → Tight crop
        → Resize + pad to 224×224 → RGB stack → PyTorch normalize
        """
        import cv2
        import numpy as np
        from PIL import Image
        import torch
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot load image: {path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Binarization (current code: signature_verifier.py:105-118)
        if self._fast_mode:
            _, clean = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
        else:
            from skimage.filters import threshold_sauvola

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

        # Tight crop (current code: signature_verifier.py:120-129)
        coords = cv2.findNonZero(clean)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            pad = 10
            cropped = clean[
                max(0, y - pad) : y + h + pad, max(0, x - pad) : x + w + pad
            ]
        else:
            cropped = clean

        # Resize + pad to 224×224 (current code: signature_verifier.py:131-148)
        target = 224
        h, w = cropped.shape[:2]
        if h == 0 or w == 0:
            resized = cropped
        else:
            scale = min(target / w, target / h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(
                cropped, (max(new_w, 1), max(new_h, 1)), interpolation=cv2.INTER_AREA
            )

        canvas = np.zeros((target, target), dtype=np.uint8)
        if resized.shape[0] <= target and resized.shape[1] <= target:
            y_off = (target - resized.shape[0]) // 2
            x_off = (target - resized.shape[1]) // 2
            canvas[y_off : y_off + resized.shape[0], x_off : x_off + resized.shape[1]] = resized

        rgb = np.stack([canvas] * 3, axis=-1)
        tensor = self._transform(Image.fromarray(rgb))
        return tensor

    # ─── Convenience: Signature comparison ───────────────────────────────

    async def compare(
        self,
        doc_path: str,
        ref_path: str,
        t_match: float = 0.75,
        t_reject: float = 0.55,
    ) -> dict:
        """
        Compare two images and return score + decision.

        Maps: signature_verifier.py:153-179 (DinoVerifier.verify)

        Returns:
            {"score": 0.85, "decision": "MATCH"|"REVIEW"|"MISMATCH"}
        """
        result = await self.embed_images([doc_path, ref_path])
        emb = result.embeddings

        # Cosine similarity (already normalized)
        score = sum(a * b for a, b in zip(emb[0], emb[1]))

        if score >= t_match:
            decision = "MATCH"
        elif score >= t_reject:
            decision = "REVIEW"
        else:
            decision = "MISMATCH"

        return {"score": round(score, 4), "decision": decision}

    async def health_check(self) -> ProviderStatus:
        """Verify model is loaded and functional."""
        try:
            import torch
            dummy = torch.randn(1, 3, 224, 224).to(self._device)
            with torch.no_grad():
                self._model(dummy)
            return ProviderStatus.HEALTHY
        except Exception as e:
            logger.warning(f"[DINOv2] Health check failed: {e}")
            return ProviderStatus.DOWN

"""
Mistral OCR Provider
====================
Implements OCRProvider interface using Mistral's OCR API.

Derived from the current implementation in utils/ocr.py which calls:
    client.ocr.process(model="mistral-ocr-latest", document=..., ...)

Handles PDF and image files. DOCX files should be handled upstream
(pure text extraction, no OCR needed).
"""

import os
import time
import logging
from mistralai.client import Mistral
from platform_core.providers.interfaces import OCRProvider, OCRResponse, ProviderStatus

logger = logging.getLogger(__name__)


class MistralOCR(OCRProvider):
    """
    Mistral OCR provider.

    Source reference:
        - utils/ocr.py:69-90 — OCR argument construction
        - utils/ocr.py:100-145 — Response parsing (pages, blocks, confidence)
    """

    def __init__(self, api_key: str, model: str = "mistral-ocr-latest"):
        self._client = Mistral(api_key=api_key)
        self._model = model
        logger.info(f"[MistralOCR] Initialized with model={model}")

    @property
    def name(self) -> str:
        return "mistral_ocr"

    async def extract(
        self,
        file_path: str,
        pages: list[int] | None = None,
        include_blocks: bool = True,
    ) -> OCRResponse:
        """
        Extract text from a document using Mistral OCR.

        Directly maps the current utils/ocr.py logic:
        - Reads file as base64
        - Builds data URL with correct MIME type
        - Calls Mistral OCR with confidence scoring + bounding blocks
        - Parses pages, word confidences, and block coordinates
        """
        from utils.file_handler import get_file_as_base64

        _, ext = os.path.splitext(file_path.lower())

        # Determine MIME type (current code: utils/ocr.py lines 43-49)
        mime_map = {
            ".pdf": "application/pdf",
            ".jpeg": "image/jpeg",
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "application/pdf")

        base64_data = get_file_as_base64(file_path)
        document_url = f"data:{mime_type};base64,{base64_data}"

        # Validate page range for PDFs (current code: utils/ocr.py lines 56-67)
        actual_pages = pages
        if ext == ".pdf" and pages is not None:
            try:
                import pypdf

                reader = pypdf.PdfReader(file_path)
                total_pages = len(reader.pages)
                actual_pages = [p for p in pages if 0 <= p < total_pages]
                if not actual_pages:
                    actual_pages = [0]
                logger.info(
                    f"[MistralOCR] PDF page range: requested={pages}, "
                    f"valid={actual_pages}, total={total_pages}"
                )
            except Exception as e:
                logger.warning(f"[MistralOCR] Could not validate PDF pages: {e}")
                actual_pages = pages

        # Build OCR arguments (current code: utils/ocr.py lines 70-87)
        ocr_args = {
            "model": self._model,
            "document": {"type": "document_url", "document_url": document_url},
            "confidence_scores_granularity": "word",
            "include_blocks": include_blocks,
        }
        if actual_pages is not None:
            ocr_args["pages"] = actual_pages

        start = time.monotonic()
        try:
            ocr_response = self._client.ocr.process(**ocr_args)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(f"[MistralOCR] OCR failed after {elapsed:.0f}ms: {e}")
            raise
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[MistralOCR] Extracted text in {elapsed:.0f}ms")

        # Parse response (current code: utils/ocr.py lines 100-145)
        raw_text = ""
        pages_list = []
        total_confidence = 0.0
        valid_pages_count = 0
        all_word_confidences = []
        all_blocks = []
        document_annotation = None

        for page in ocr_response.pages:
            page_index = getattr(page, "index", 0)
            raw_text += page.markdown + "\n\n"
            pages_list.append({"markdown": page.markdown, "index": page_index})

            # Confidence scores
            if hasattr(page, "confidence_scores") and page.confidence_scores:
                if hasattr(page.confidence_scores, "average_page_confidence_score"):
                    total_confidence += (
                        page.confidence_scores.average_page_confidence_score
                    )
                    valid_pages_count += 1
                if getattr(page.confidence_scores, "word_confidence_scores", None):
                    for w in page.confidence_scores.word_confidence_scores:
                        all_word_confidences.append(
                            {
                                "text": w.text,
                                "confidence": w.confidence,
                                "start_index": w.start_index,
                            }
                        )

            # Bounding box blocks for citation highlighting
            dims = getattr(page, "dimensions", None)
            page_w = getattr(dims, "width", None)
            page_h = getattr(dims, "height", None)
            for block in getattr(page, "blocks", []) or []:
                b_type = getattr(block, "type", "text")
                if b_type == "image":
                    continue  # Skip image placeholder blocks
                top_left_x = getattr(block, "top_left_x", None)
                bottom_right_x = getattr(block, "bottom_right_x", None)
                if top_left_x is None or bottom_right_x is None:
                    continue  # Block has no spatial data
                all_blocks.append(
                    {
                        "page": page_index,
                        "content": getattr(block, "content", "") or "",
                        "type": b_type,
                        "top_left_x": top_left_x,
                        "top_left_y": getattr(block, "top_left_y", None),
                        "bottom_right_x": bottom_right_x,
                        "bottom_right_y": getattr(block, "bottom_right_y", None),
                        "page_width": page_w,
                        "page_height": page_h,
                    }
                )

        avg_confidence = (
            (total_confidence / valid_pages_count) if valid_pages_count > 0 else 0.0
        )

        # Extract document annotation if present (utils/ocr.py lines 150-163)
        if hasattr(ocr_response, "document_annotation") and ocr_response.document_annotation:
            import json
            annotation = ocr_response.document_annotation
            if isinstance(annotation, str):
                try:
                    document_annotation = json.loads(annotation)
                except Exception:
                    document_annotation = annotation
            elif hasattr(annotation, "model_dump"):
                document_annotation = annotation.model_dump()
            elif hasattr(annotation, "to_dict"):
                document_annotation = annotation.to_dict()
            else:
                document_annotation = annotation

        return OCRResponse(
            raw_text=raw_text.strip(),
            confidence=avg_confidence,
            pages=pages_list,
            blocks=all_blocks,
            word_confidences=all_word_confidences,
            document_annotation=document_annotation,
            provider="mistral_ocr",
        )

    async def health_check(self) -> ProviderStatus:
        """Verify Mistral API is reachable."""
        try:
            await self._client.chat.complete_async(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return ProviderStatus.HEALTHY
        except Exception as e:
            logger.warning(f"[MistralOCR] Health check failed: {e}")
            return ProviderStatus.DOWN

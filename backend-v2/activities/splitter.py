"""
Step 1.5 — Packet Split Detection
=================================
OCRs an uploaded file once, asks the Splitter Agent to classify every page, and
turns the page verdicts into document segments.

This activity only *decides*. Writing the child PDFs, creating their rows and
launching their workflows is `activities/split_fanout.py`, so a failure in the
expensive decision half can be retried without half-creating children.

The document types offered to the agent come from the live classification config
(`tools/splitter.py::build_type_catalogue`), never from a hardcoded list.
"""

import json
import asyncio
import logging

import mistralai.workflows as workflows

from platform_core.adapters.resilient_mistral import get_mistral_client
from config import settings
from utils.ocr import extract_with_ocr
from utils.split_config import load_split_config
from tools.classifier import get_supported_doc_types
from tools.splitter import (
    build_type_catalogue,
    format_type_catalogue,
    is_splittable,
    merge_orphans,
    parse_page_classifications,
    segment_pages,
    verify_segments,
)

logger = logging.getLogger(__name__)
client = get_mistral_client()

# Page markdown is truncated before it goes into the prompt. Boundary evidence
# (headers, page numbers, a fresh account number) lives at the top and bottom of
# a page, so a long middle section costs tokens without adding signal.
MAX_PAGE_CHARS = 4000


def _extract_text(content) -> str:
    """Safely extract text from the various Mistral response content shapes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif hasattr(chunk, "text") and chunk.text:
                parts.append(chunk.text)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _truncate(markdown: str) -> str:
    if len(markdown) <= MAX_PAGE_CHARS:
        return markdown
    head = MAX_PAGE_CHARS * 2 // 3
    tail = MAX_PAGE_CHARS - head
    return f"{markdown[:head]}\n\n[… page truncated …]\n\n{markdown[-tail:]}"


def _build_batches(page_indexes: list[int], batch_size: int) -> list[list[int]]:
    return [page_indexes[i:i + batch_size] for i in range(0, len(page_indexes), batch_size)]


def _build_batch_prompt(batch: list[int], pages_md: dict[int, str],
                        catalogue_text: str, total_pages: int,
                        lookback: int | None) -> str:
    """One user message: the type catalogue, optional context page, then the batch."""
    sections = [
        "SUPPORTED DOCUMENT TYPES:",
        catalogue_text,
        "",
        f"The uploaded file has {total_pages} page(s) in total.",
    ]

    if lookback is not None:
        sections += [
            "",
            f"CONTEXT — page {lookback} (already classified, do NOT return a verdict for it):",
            "--- BEGIN CONTEXT ---",
            _truncate(pages_md.get(lookback, "")),
            "--- END CONTEXT ---",
        ]

    sections += ["", f"Classify these {len(batch)} page(s):"]
    for index in batch:
        sections += [
            "",
            f"--- BEGIN PAGE {index} ---",
            _truncate(pages_md.get(index, "")) or "[no text extracted from this page]",
            f"--- END PAGE {index} ---",
        ]

    sections += [
        "",
        f"Return one entry per page for page_index {batch} — no entry for the context page.",
    ]
    return "\n".join(sections)


async def _classify_batch(document_id: str, batch: list[int], pages_md: dict[int, str],
                          catalogue_text: str, total_pages: int,
                          lookback: int | None, allowed_types: dict) -> list:
    """Classify one batch of pages; a failed batch degrades instead of raising."""
    prompt = _build_batch_prompt(batch, pages_md, catalogue_text, total_pages, lookback)
    try:
        response = await client.agents.complete_async(
            agent_id=settings.SPLITTER_AGENT_ID,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(_extract_text(response.choices[0].message.content).strip())
    except Exception as e:
        # An empty parse makes parse_page_classifications backfill the whole batch
        # at confidence 0.0, which trips the review gate rather than guessing.
        logger.error(f"[Document {document_id}] Splitter batch {batch} failed: {e}")
        raw = {}

    return parse_page_classifications(raw, batch, allowed_types)


@workflows.activity()
async def splitter_activity(document_id: str, file_path: str) -> dict:
    """
    Step 1.5 — decide whether this upload is a packet, and where it breaks.

    Returns either:
      {"split": False, "reason": "single_page" | "not_a_pdf" | ...}
      {"split": True, "segments": [...], "pages": [...], "needs_review": bool,
       "page_count": int}
    """
    logger.info(f"[Document {document_id}] Starting split detection")

    config = load_split_config()
    threshold = config["confidence_threshold"]

    try:
        if not config["enabled"]:
            logger.info(f"[Document {document_id}] Splitting disabled in settings — skipping.")
            return {"split": False, "reason": "disabled"}

        if not settings.SPLITTER_AGENT_ID:
            logger.warning(
                f"[Document {document_id}] SPLITTER_AGENT_ID is not configured — "
                f"processing as a single document."
            )
            return {"split": False, "reason": "agent_not_configured"}

        ok, reason, page_count = is_splittable(file_path, config["max_pages"])
        if not ok:
            logger.info(f"[Document {document_id}] Not a split candidate: {reason}")
            return {"split": False, "reason": reason, "page_count": page_count}

        # ── One OCR pass over the whole packet ──
        ocr_result = await asyncio.to_thread(extract_with_ocr, file_path, "unknown")
        pages_md = {
            page.get("index", position): page.get("markdown", "") or ""
            for position, page in enumerate(ocr_result.get("pages", []))
        }

        # A misaligned page index would cut the PDF in the wrong place, which is
        # strictly worse than not splitting. Bail rather than guess.
        if len(pages_md) != page_count:
            logger.error(
                f"[Document {document_id}] OCR returned {len(pages_md)} pages but the PDF "
                f"has {page_count} — skipping the split."
            )
            return {"split": False, "reason": "ocr_page_mismatch", "page_count": page_count}

        page_indexes = sorted(pages_md.keys())

        # ── Per-page classification, batched and concurrent ──
        allowed_types = get_supported_doc_types()
        catalogue_text = format_type_catalogue(build_type_catalogue())
        batches = _build_batches(page_indexes, config["page_batch_size"])

        results = await asyncio.gather(*[
            _classify_batch(
                document_id, batch, pages_md, catalogue_text, page_count,
                # Every batch after the first carries the preceding page as context
                # so the agent can tell "continuation" from "new document".
                batches[position - 1][-1] if position > 0 else None,
                allowed_types,
            )
            for position, batch in enumerate(batches)
        ])
        classifications = [pc for batch_result in results for pc in batch_result]
        classifications.sort(key=lambda pc: pc.page_index)

        for pc in classifications:
            logger.info(
                f"[Document {document_id}]   page {pc.page_index:>3}: {pc.doc_type:<22} "
                f"first={str(pc.is_first_page):<5} conf={pc.confidence:.2f}"
            )

        # ── Boundaries ──
        segments = segment_pages(classifications)
        if config["merge_orphans"]:
            segments = merge_orphans(segments, threshold)
        segments = verify_segments(segments, pages_md)

        if len(segments) < 2:
            logger.info(f"[Document {document_id}] Single document detected — no split.")
            return {"split": False, "reason": "single_document", "page_count": page_count}

        low_confidence = [pc.page_index for pc in classifications if pc.confidence < threshold]
        failed_markers = [s.page_range_label for s in segments if s.verified is False]
        needs_review = bool(config["require_review"] and (low_confidence or failed_markers))

        logger.info(
            f"[Document {document_id}] Split into {len(segments)} documents: "
            + ", ".join(f"{s.doc_type} p{s.page_range_label}" for s in segments)
            + (f" — review needed (low-confidence pages {low_confidence}, "
               f"failed markers {failed_markers})" if needs_review else "")
        )

        return {
            "split": True,
            "reason": "",
            "page_count": page_count,
            "segments": [s.model_dump() for s in segments],
            "pages": [pc.model_dump() for pc in classifications],
            "needs_review": needs_review,
            "low_confidence_pages": low_confidence,
        }

    except Exception as e:
        # Deliberately no db.update_error() here: the workflow degrades a splitter
        # failure into "process the packet whole", so marking the document failed
        # would contradict the run that is about to continue successfully.
        logger.error(f"[Document {document_id}] Split detection failed: {e}")
        raise

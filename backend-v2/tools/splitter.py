"""
Document Packet Splitting — Core Engine
=======================================
Pure helpers for finding document boundaries inside a multi-document PDF packet
and physically splitting it.

Nothing in this module talks to the Mistral API. `activities/splitter.py` owns
the OCR and agent calls and hands the raw JSON in here, which keeps the boundary
logic — the part where accuracy actually lives — unit-testable with zero network
access. See `tests/test_splitter.py`.

Document types are NOT hardcoded. They come from
`utils/classification_config.py` at call time, the same catalogue the classifier
agent is handed, so a type added in the Settings UI immediately teaches the
splitter about it.
"""

import os
import re
import logging

import pypdf
from pydantic import BaseModel, Field

from utils.templates import load_templates

logger = logging.getLogger(__name__)

# The catch-all bucket. Matches the fallback `activities/classifier.py` uses when
# the agent's answer does not map onto a configured type.
OTHERS_KEY = "others"

# Per-type prompt cues are drawn from the template field labels, capped so a
# 40-field template cannot crowd out the page text in the prompt.
MAX_CUES_PER_TYPE = 8

# Blank-page detection thresholds.  A page that passes all checks is blank.
BLANK_TEXT_CHAR_THRESHOLD = 20       # fewer stripped chars in OCR markdown → blank
BLANK_IMAGE_COUNT_THRESHOLD = 0      # no embedded images
BLANK_DRAWING_COUNT_THRESHOLD = 0    # no vector drawings (lines, shapes)


# ─── Models ──────────────────────────────────────────────────────────────────

class PageClassification(BaseModel):
    """One page's verdict from the splitter agent."""

    page_index: int                      # 0-based; aligns with pypdf and OCR page.index
    doc_type: str                        # snake_case key from the live catalogue, or "others"
    is_first_page: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    is_blank: bool = False               # deterministic blank detection, set pre-LLM


class Segment(BaseModel):
    """A run of consecutive pages that form one document."""

    doc_type: str
    start: int                           # 0-based, inclusive
    end: int                             # 0-based, inclusive
    pages: list[int] = Field(default_factory=list)
    min_confidence: float = 1.0
    verified: bool | None = None         # id_marker check: True/False, None = no rule
    output_file: str | None = None
    child_document_id: str | None = None

    @property
    def page_range_label(self) -> str:
        """1-based inclusive label for humans, e.g. "3-5" or "7"."""
        return f"{self.start + 1}-{self.end + 1}" if self.end > self.start else f"{self.start + 1}"


# ─── Eligibility ─────────────────────────────────────────────────────────────

def is_splittable(file_path: str, max_pages: int) -> tuple[bool, str, int]:
    """
    Can this file hold more than one document?

    Returns (ok, reason, page_count). Only multi-page, readable, unencrypted PDFs
    are candidates — an image is one page by definition, and DOCX has no page
    model we can cut on.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext != ".pdf":
        return False, "not_a_pdf", 0

    try:
        reader = pypdf.PdfReader(file_path)
        if reader.is_encrypted:
            # An empty-password decrypt is the same probe pre_validator uses.
            try:
                if reader.decrypt("") == 0:
                    return False, "encrypted", 0
            except Exception:
                return False, "encrypted", 0
        page_count = len(reader.pages)
    except Exception as e:
        logger.warning(f"Cannot read PDF for split eligibility ({file_path}): {e}")
        return False, "unreadable", 0

    if page_count < 2:
        return False, "single_page", page_count
    if page_count > max_pages:
        return False, "too_many_pages", page_count
    return True, "", page_count


# ─── Type catalogue (the replacement for the PoC's hardcoded DocType enum) ────

def build_type_catalogue() -> list[dict]:
    """
    The live document types, each with cues drawn from its extraction template.

    The cues are template field labels the team already maintains in the
    Templates UI — that is what makes the splitter prompt type-aware without
    anyone hand-writing "aadhaar has a 12-digit UID" into a prompt.
    """
    # Imported lazily: tools.classifier pulls in the OCR stack and instantiates a
    # Mistral client at import time, which the boundary-logic unit tests must not need.
    from tools.classifier import get_supported_doc_types

    types_map = get_supported_doc_types()
    try:
        templates = load_templates()
    except Exception as e:
        logger.warning(f"Could not load templates for split cues: {e}")
        templates = {}

    catalogue = []
    for key, display in types_map.items():
        tpl = templates.get(key) or {}
        cues = []
        for field in (tpl.get("fields") or [])[:MAX_CUES_PER_TYPE]:
            label = (field.get("label") or field.get("key") or "").strip()
            if label:
                cues.append(label)
        catalogue.append({"key": key, "display": display, "cues": cues})
    return catalogue


def format_type_catalogue(catalogue: list[dict]) -> str:
    """Render the catalogue as prompt text."""
    lines = []
    for entry in catalogue:
        line = f"- {entry['key']} ({entry['display']})"
        if entry.get("cues"):
            line += f" — expected fields: {', '.join(entry['cues'])}"
        lines.append(line)
    lines.append(f'- {OTHERS_KEY} (Others) — matches none of the above')
    return "\n".join(lines)


def normalize_doc_type(value, allowed_types: dict) -> str | None:
    """
    Map whatever the agent said onto a configured type key.

    Accepts the key, the display name, or a spaced variant — the same tolerance
    `activities/classifier.py` applies to its own agent's answer. Returns None
    when nothing matches, which the caller turns into `others`.
    """
    if not value or not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if candidate in (OTHERS_KEY, "other"):
        return OTHERS_KEY
    underscored = candidate.replace(" ", "_").replace("-", "_")
    for key, display in allowed_types.items():
        if underscored == key.lower() or candidate in (display.lower(), key.replace("_", " ").lower()):
            return key
    return None


# ─── Parsing the agent response ──────────────────────────────────────────────

def _coerce_confidence(value) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, conf))


def parse_page_classifications(raw, page_indexes: list[int],
                               allowed_types: dict) -> list[PageClassification]:
    """
    Turn one batch of agent JSON into `PageClassification`s, one per requested page.

    Defensive on every axis, because a malformed answer here would cut a PDF in
    the wrong place:
      * an unrecognised doc_type degrades to `others` at confidence 0.0, which
        trips the review gate rather than inventing a boundary;
      * a page the agent skipped is backfilled as a zero-confidence continuation
        of the preceding page, never as a new document;
      * a page the agent invented (not in `page_indexes`) is dropped.
    """
    entries = []
    if isinstance(raw, dict):
        for key in ("pages", "results", "classifications"):
            if isinstance(raw.get(key), list):
                entries = raw[key]
                break
        else:
            # A single-page answer returned bare.
            if "doc_type" in raw:
                entries = [raw]
    elif isinstance(raw, list):
        entries = raw

    ordered = sorted(page_indexes)
    by_index: dict[int, PageClassification] = {}

    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue

        index = entry.get("page_index", entry.get("page", entry.get("index")))
        if index is None and position < len(ordered):
            index = ordered[position]          # positional fallback
        try:
            index = int(index)
        except (TypeError, ValueError):
            continue
        if index not in page_indexes:
            continue                            # hallucinated page number

        doc_type = normalize_doc_type(entry.get("doc_type"), allowed_types)
        confidence = _coerce_confidence(entry.get("confidence"))
        if doc_type is None:
            doc_type, confidence = OTHERS_KEY, 0.0

        by_index[index] = PageClassification(
            page_index=index,
            doc_type=doc_type,
            is_first_page=bool(entry.get("is_first_page", False)),
            confidence=confidence,
            reasoning=str(entry.get("reasoning", ""))[:500],
        )

    # Backfill anything the agent left out, inheriting the previous page's type so
    # the gap reads as a continuation instead of a spurious boundary.
    results: list[PageClassification] = []
    last_type = OTHERS_KEY
    for index in ordered:
        if index in by_index:
            results.append(by_index[index])
            last_type = by_index[index].doc_type
        else:
            logger.warning(f"Splitter agent returned no classification for page {index}")
            results.append(PageClassification(
                page_index=index,
                doc_type=last_type,
                is_first_page=False,
                confidence=0.0,
                reasoning="No classification returned for this page.",
            ))
    return results


# ─── Boundary detection ──────────────────────────────────────────────────────

def segment_pages(classifications: list[PageClassification]) -> list[Segment]:
    """
    Group ordered page classifications into document segments.

    A new document starts when it is the first page, when the agent flagged a
    fresh header (`is_first_page`), or when the type changed. Consecutive
    same-type pages stay together unless the agent explicitly flagged a new first
    page — that last clause is what separates two same-type documents sitting
    back to back (two salary slips, two invoices).
    """
    segments: list[Segment] = []
    current: Segment | None = None

    for i, pc in enumerate(classifications):
        prev_type = classifications[i - 1].doc_type if i > 0 else None

        start_new = (i == 0) or pc.is_first_page or (pc.doc_type != prev_type)

        # Same type and no fresh header => continuation. Never split here.
        if pc.doc_type == prev_type and not pc.is_first_page:
            start_new = False

        if start_new or current is None:
            if current is not None:
                segments.append(current)
            current = Segment(
                doc_type=pc.doc_type, start=i, end=i,
                pages=[i], min_confidence=pc.confidence,
            )
        else:
            current.end = i
            current.pages.append(i)
            current.min_confidence = min(current.min_confidence, pc.confidence)

    if current is not None:
        segments.append(current)
    return segments


def merge_orphans(segments: list[Segment], threshold: float) -> list[Segment]:
    """
    Absorb a low-confidence single-page outlier back into the document around it.

    Only fires when the pages either side belong to the *same* type — a page
    typed differently from both its neighbours, below the confidence threshold,
    sandwiched between two pages of one document, is a stray letterhead or a
    continuation sheet the agent misread, not a one-page document. Requiring the
    neighbours to match is what stops this from swallowing genuine single-page
    documents (a PAN card between a statement and a utility bill).
    """
    if len(segments) < 3:
        return segments

    merged: list[Segment] = [segments[0]]
    i = 1
    while i < len(segments):
        segment = segments[i]
        previous = merged[-1]
        following = segments[i + 1] if i + 1 < len(segments) else None

        is_orphan = (
            following is not None
            and len(segment.pages) == 1
            and segment.min_confidence < threshold
            and segment.doc_type != previous.doc_type
            and previous.doc_type == following.doc_type
        )

        if is_orphan:
            logger.info(
                f"Merging orphan page {segment.start} ({segment.doc_type}, "
                f"conf={segment.min_confidence:.2f}) into surrounding {previous.doc_type}"
            )
            previous.end = following.end
            previous.pages.extend(segment.pages + following.pages)
            previous.min_confidence = min(
                previous.min_confidence, segment.min_confidence, following.min_confidence
            )
            i += 2                              # previous, segment and following are now one
        else:
            merged.append(segment)
            i += 1

    return merged


def detect_blank_pages(
    pages_md: dict[int, str],
    file_path: str | None = None,
) -> set[int]:
    """
    Identify blank pages by combining OCR evidence and (optionally) PyMuPDF.

    Two layers:
    1. OCR markdown length — a true blank page produces "" or a few noise chars.
       This is always available because the splitter already ran OCR.
    2. PyMuPDF scan (if fitz is importable) — checks text, images, and drawings
       for pages that passed layer 1, to catch image-only blank pages the OCR
       might have returned a short spurious string for.

    Returns a set of 0-based page indexes that are blank.
    """
    candidates: set[int] = set()

    # Layer 1: OCR markdown is too short to carry any real content.
    for index, markdown in pages_md.items():
        stripped = (markdown or "").strip()
        if len(stripped) <= BLANK_TEXT_CHAR_THRESHOLD:
            candidates.add(index)

    if not candidates or not file_path:
        return candidates

    # Layer 2: Confirm with PyMuPDF's structural scan.
    confirmed: set[int] = set()
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        for index in candidates:
            if index >= len(doc):
                confirmed.add(index)     # out of range → treat as blank
                continue
            page = doc[index]
            text = page.get_text().strip()
            images = page.get_images()
            
            # Ignore tiny scanner artifacts (e.g., 1x1 pixels often used to anchor blank pages)
            real_images = [img for img in images if img[2] > 10 or img[3] > 10]
            
            drawings = page.get_drawings()
            if (
                not text
                and len(real_images) <= BLANK_IMAGE_COUNT_THRESHOLD
                and len(drawings) <= BLANK_DRAWING_COUNT_THRESHOLD
            ):
                confirmed.add(index)
        doc.close()
    except ImportError:
        # No PyMuPDF — trust the OCR layer alone.
        logger.warning("PyMuPDF (fitz) not available — blank detection uses OCR length only.")
        confirmed = candidates

    return confirmed


def stamp_blank_pages(
    classifications: list[PageClassification],
    blank_pages: set[int],
) -> list[PageClassification]:
    """
    Override the agent's verdict for pages that are deterministically blank.

    Confidence is set to 1.0 (certainty, not uncertainty) so blank pages never
    drag down min_confidence and trigger the review gate.
    """
    for pc in classifications:
        if pc.page_index in blank_pages:
            pc.is_blank = True
            pc.doc_type = OTHERS_KEY
            pc.is_first_page = False
            pc.confidence = 1.0
            pc.reasoning = "Blank page — no text, images, or drawings detected."
    return classifications


def merge_blanks(
    segments: list[Segment],
    classifications: list[PageClassification],
) -> list[Segment]:
    """
    Strip blank pages from every segment and drop blank-only segments.

    Rules:
    1. Blank pages are removed from every segment's page list — they are never
       included in child PDFs.  A blank page between Aadhaar front and back, for
       example, is physically stripped from the child document.
    2. A segment that becomes empty after stripping (was entirely blank) is
       dropped — no child document is created for it.
    3. ``start`` and ``end`` are updated to reflect the remaining pages.
    4. Adjacent segments of the same doc_type that were separated only by blank
       pages are re-merged into a single segment (e.g. Aadhaar front [0] and
       Aadhaar back [2] become one segment [0, 2] after blank page 1 is dropped).

    Runs BEFORE merge_orphans so orphan merging sees clean segments.
    """
    blank_set = {pc.page_index for pc in classifications if pc.is_blank}
    if not blank_set:
        return segments

    # Pass 1: strip blank pages from every segment, drop empty segments.
    stripped: list[Segment] = []
    for segment in segments:
        cleaned_pages = [p for p in segment.pages if p not in blank_set]
        stripped_count = len(segment.pages) - len(cleaned_pages)

        if not cleaned_pages:
            # Entirely blank segment — drop it, no child document.
            logger.info(
                f"Dropping blank-only segment at pages {segment.pages} "
                f"(doc_type={segment.doc_type})"
            )
            continue

        if stripped_count > 0:
            logger.info(
                f"Stripping {stripped_count} blank page(s) "
                f"{[p for p in segment.pages if p in blank_set]} from "
                f"{segment.doc_type} segment (keeping pages {cleaned_pages})"
            )
            segment.pages = cleaned_pages
            segment.start = cleaned_pages[0]
            segment.end = cleaned_pages[-1]

        stripped.append(segment)

    # Pass 2: re-merge adjacent segments of the same type that were separated
    # only by now-dropped blank pages (e.g. Aadhaar front + blank + Aadhaar back).
    if len(stripped) < 2:
        return stripped

    merged: list[Segment] = [stripped[0]]
    for segment in stripped[1:]:
        prev = merged[-1]
        if prev.doc_type == segment.doc_type:
            logger.info(
                f"Re-merging adjacent {prev.doc_type} segments "
                f"{prev.pages} + {segment.pages} (were separated by blank pages)"
            )
            prev.pages.extend(segment.pages)
            prev.end = segment.pages[-1]
            prev.min_confidence = min(prev.min_confidence, segment.min_confidence)
        else:
            merged.append(segment)
    return merged


def build_segments_from_overrides(overrides: list[dict], total_pages: int,
                                  allowed_types: dict) -> list[Segment]:
    """
    Rebuild segments from human-confirmed boundaries (the split review step).

    Validates that the submitted segments are ordered, contiguous and cover every
    page — a gap would silently drop pages from the output, an overlap would
    duplicate them. Confidence is 1.0 because a person confirmed these.
    """
    if not overrides:
        raise ValueError("No segments supplied.")

    segments: list[Segment] = []
    expected_start = 0
    for raw in overrides:
        start, end = int(raw["start"]), int(raw["end"])
        if start != expected_start:
            raise ValueError(
                f"Segments must be contiguous and ordered: expected a segment "
                f"starting at page {expected_start}, got {start}."
            )
        if end < start:
            raise ValueError(f"Segment end ({end}) precedes its start ({start}).")
        if end >= total_pages:
            raise ValueError(f"Segment end ({end}) is past the last page ({total_pages - 1}).")

        doc_type = normalize_doc_type(raw.get("doc_type"), allowed_types) or OTHERS_KEY
        segments.append(Segment(
            doc_type=doc_type, start=start, end=end,
            pages=list(range(start, end + 1)), min_confidence=1.0,
        ))
        expected_start = end + 1

    if expected_start != total_pages:
        raise ValueError(
            f"Segments must cover every page: {expected_start} of {total_pages} covered."
        )
    return segments


# ─── ID-marker verification (template-driven, not hardcoded) ─────────────────

def verify_segments(segments: list[Segment], pages_md: dict[int, str],
                    templates: dict | None = None) -> list[Segment]:
    """
    Advisory check that each segment carries its type's identifying marker.

    The marker is the optional `id_marker` regex on the extraction template, so
    the rules live in the Templates UI rather than in code. Types without one get
    `verified = None`. A failed check never blocks processing; it lands in the
    manifest and forces the review gate open.
    """
    if templates is None:
        try:
            templates = load_templates()
        except Exception as e:
            logger.warning(f"Could not load templates for marker verification: {e}")
            templates = {}

    for segment in segments:
        pattern_str = (templates.get(segment.doc_type) or {}).get("id_marker")
        if not pattern_str:
            segment.verified = None
            continue
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Invalid id_marker for '{segment.doc_type}', skipping check: {e}")
            segment.verified = None
            continue
        blob = "\n".join(pages_md.get(page, "") for page in segment.pages)
        segment.verified = bool(pattern.search(blob))
    return segments


# ─── Physical split ──────────────────────────────────────────────────────────

def split_pdf(input_path: str, segments: list[Segment], out_dir: str) -> list[Segment]:
    """
    Write one PDF per segment into `out_dir`, setting `output_file` on each.

    Page indexes are 0-based and index straight into `PdfReader.pages`, which is
    the same ordering the OCR page indexes use — the alignment the caller asserts
    before ever getting here.
    """
    os.makedirs(out_dir, exist_ok=True)
    reader = pypdf.PdfReader(input_path)
    total_pages = len(reader.pages)

    for position, segment in enumerate(segments, start=1):
        writer = pypdf.PdfWriter()
        for page in segment.pages:
            if not 0 <= page < total_pages:
                raise IndexError(f"Segment page {page} is outside the source PDF (0-{total_pages - 1}).")
            writer.add_page(reader.pages[page])

        filename = f"{position:02d}_{segment.doc_type}_p{segment.page_range_label}.pdf"
        path = os.path.join(out_dir, filename)
        with open(path, "wb") as fh:
            writer.write(fh)
        segment.output_file = os.path.abspath(path)

    return segments

"""
Packet splitter — boundary logic tests.

No network, no Mistral client: `tools/splitter.py` takes already-parsed agent
JSON, so every decision the splitter makes is testable offline. This is where
the standalone PoC's `_self_test()` fixture lives, promoted to real cases.
"""

import os
import tempfile

import pypdf
import pytest

from tools.splitter import (
    OTHERS_KEY,
    PageClassification,
    Segment,
    build_segments_from_overrides,
    is_splittable,
    merge_orphans,
    normalize_doc_type,
    parse_page_classifications,
    segment_pages,
    split_pdf,
    verify_segments,
)

# A stand-in for whatever `get_supported_doc_types()` returns at runtime. The
# splitter never hardcodes types, so the tests supply their own catalogue.
TYPES = {
    "bank_statement": "Bank Statement",
    "utility_bill":   "Utility Bill",
    "aadhaar_card":   "Aadhaar Card",
    "pan_card":       "Pan Card",
    "salary_slip":    "Salary Slip",
    "invoice":        "Invoice",
}


def pc(page_index, doc_type, is_first_page, confidence=0.95):
    return PageClassification(
        page_index=page_index, doc_type=doc_type,
        is_first_page=is_first_page, confidence=confidence, reasoning="test",
    )


def _make_pdf(path, page_count, text_prefix="page"):
    """A minimal multi-page PDF whose pages carry distinguishable text."""
    writer = pypdf.PdfWriter()
    for i in range(page_count):
        page = writer.add_blank_page(width=200, height=200)
        page.merge_page(page)  # no-op; keeps pypdf happy across versions
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


# ─── Boundary detection ──────────────────────────────────────────────────────

def test_multipage_and_back_to_back_same_type():
    """
    The PoC's own fixture: a 3-page statement, three single-page documents, then
    TWO salary slips back to back. The second slip must open its own segment —
    same type as its predecessor, so only `is_first_page` can separate them.
    """
    pages = [
        pc(0, "bank_statement", True), pc(1, "bank_statement", False), pc(2, "bank_statement", False),
        pc(3, "utility_bill", True),
        pc(4, "aadhaar_card", True),
        pc(5, "pan_card", True),
        pc(6, "salary_slip", True), pc(7, "salary_slip", True),
    ]
    got = [(s.doc_type, s.pages) for s in segment_pages(pages)]
    assert got == [
        ("bank_statement", [0, 1, 2]),
        ("utility_bill", [3]),
        ("aadhaar_card", [4]),
        ("pan_card", [5]),
        ("salary_slip", [6]),
        ("salary_slip", [7]),
    ]


def test_single_document_yields_one_segment():
    """A plain 3-page invoice must not be split at all."""
    pages = [pc(0, "invoice", True), pc(1, "invoice", False), pc(2, "invoice", False)]
    segments = segment_pages(pages)
    assert len(segments) == 1
    assert segments[0].pages == [0, 1, 2]


def test_continuation_never_splits_even_if_type_repeats():
    """Same type + is_first_page False is a continuation, whatever the confidence."""
    pages = [pc(0, "bank_statement", True), pc(1, "bank_statement", False, 0.2)]
    segments = segment_pages(pages)
    assert len(segments) == 1
    assert segments[0].min_confidence == pytest.approx(0.2)


def test_first_page_false_on_page_zero_does_not_crash():
    """
    The PoC could raise AttributeError here: page 0 with is_first_page False and
    no previous type. Reachable once a reviewer edits the first boundary.
    """
    pages = [pc(0, "invoice", False), pc(1, "invoice", False)]
    segments = segment_pages(pages)
    assert len(segments) == 1
    assert segments[0].pages == [0, 1]


# ─── Orphan merging ──────────────────────────────────────────────────────────

def test_orphan_page_is_merged_back_into_surrounding_document():
    """A low-confidence stray page between two pages of one statement is absorbed."""
    pages = [
        pc(0, "bank_statement", True), pc(1, "bank_statement", False),
        pc(2, "invoice", True, 0.4),
        pc(3, "bank_statement", True),
    ]
    segments = merge_orphans(segment_pages(pages), threshold=0.75)
    assert len(segments) == 1
    assert segments[0].doc_type == "bank_statement"
    assert segments[0].pages == [0, 1, 2, 3]
    assert segments[0].min_confidence == pytest.approx(0.4)


def test_orphan_merge_respects_the_threshold():
    """A confident single-page document between two statements is left alone."""
    pages = [
        pc(0, "bank_statement", True), pc(1, "bank_statement", False),
        pc(2, "pan_card", True, 0.97),
        pc(3, "bank_statement", True),
    ]
    segments = merge_orphans(segment_pages(pages), threshold=0.75)
    assert [s.doc_type for s in segments] == ["bank_statement", "pan_card", "bank_statement"]


def test_orphan_merge_requires_matching_neighbours():
    """Different types either side means it is a real boundary, not a stray page."""
    pages = [
        pc(0, "bank_statement", True),
        pc(1, "invoice", True, 0.3),
        pc(2, "utility_bill", True),
    ]
    segments = merge_orphans(segment_pages(pages), threshold=0.75)
    assert [s.doc_type for s in segments] == ["bank_statement", "invoice", "utility_bill"]


# ─── Parsing the agent response ──────────────────────────────────────────────

def test_unknown_doc_type_degrades_to_others_at_zero_confidence():
    raw = {"pages": [{"page_index": 0, "doc_type": "mortgage_deed", "is_first_page": True, "confidence": 0.99}]}
    result = parse_page_classifications(raw, [0], TYPES)
    assert result[0].doc_type == OTHERS_KEY
    assert result[0].confidence == 0.0


def test_display_name_and_spaced_variants_map_back_to_the_key():
    raw = {"pages": [
        {"page_index": 0, "doc_type": "Bank Statement", "is_first_page": True, "confidence": 0.9},
        {"page_index": 1, "doc_type": "pan card", "is_first_page": True, "confidence": 0.9},
    ]}
    result = parse_page_classifications(raw, [0, 1], TYPES)
    assert [r.doc_type for r in result] == ["bank_statement", "pan_card"]


def test_missing_page_is_backfilled_as_a_continuation():
    """A page the agent skipped must not become a new document."""
    raw = {"pages": [
        {"page_index": 0, "doc_type": "bank_statement", "is_first_page": True, "confidence": 0.9},
        {"page_index": 2, "doc_type": "bank_statement", "is_first_page": False, "confidence": 0.9},
    ]}
    result = parse_page_classifications(raw, [0, 1, 2], TYPES)
    assert len(result) == 3
    assert result[1].doc_type == "bank_statement"
    assert result[1].is_first_page is False
    assert result[1].confidence == 0.0
    assert len(segment_pages(result)) == 1


def test_hallucinated_page_index_is_dropped():
    raw = {"pages": [
        {"page_index": 0, "doc_type": "invoice", "is_first_page": True, "confidence": 0.9},
        {"page_index": 99, "doc_type": "invoice", "is_first_page": True, "confidence": 0.9},
    ]}
    result = parse_page_classifications(raw, [0, 1], TYPES)
    assert [r.page_index for r in result] == [0, 1]


def test_empty_response_backfills_the_whole_batch_for_review():
    """A failed agent call yields zero-confidence pages, which trips the gate."""
    result = parse_page_classifications({}, [0, 1, 2], TYPES)
    assert len(result) == 3
    assert all(r.confidence == 0.0 for r in result)
    assert all(r.is_first_page is False for r in result)


def test_out_of_range_confidence_is_clamped():
    raw = {"pages": [{"page_index": 0, "doc_type": "invoice", "is_first_page": True, "confidence": 4.2}]}
    assert parse_page_classifications(raw, [0], TYPES)[0].confidence == 1.0


def test_normalize_doc_type_rejects_nonsense():
    assert normalize_doc_type("", TYPES) is None
    assert normalize_doc_type(None, TYPES) is None
    assert normalize_doc_type("something_else", TYPES) is None
    assert normalize_doc_type("others", TYPES) == OTHERS_KEY


# ─── Reviewer overrides ──────────────────────────────────────────────────────

def test_reviewer_boundaries_rebuild_segments():
    overrides = [
        {"doc_type": "bank_statement", "start": 0, "end": 2},
        {"doc_type": "Pan Card", "start": 3, "end": 3},
    ]
    segments = build_segments_from_overrides(overrides, 4, TYPES)
    assert [(s.doc_type, s.pages) for s in segments] == [
        ("bank_statement", [0, 1, 2]),
        ("pan_card", [3]),
    ]
    assert all(s.min_confidence == 1.0 for s in segments)


def test_reviewer_boundaries_reject_gaps_overlaps_and_short_coverage():
    with pytest.raises(ValueError):   # gap between 0-1 and 3-4
        build_segments_from_overrides(
            [{"doc_type": "invoice", "start": 0, "end": 1},
             {"doc_type": "invoice", "start": 3, "end": 4}], 5, TYPES)

    with pytest.raises(ValueError):   # overlap
        build_segments_from_overrides(
            [{"doc_type": "invoice", "start": 0, "end": 2},
             {"doc_type": "invoice", "start": 2, "end": 3}], 4, TYPES)

    with pytest.raises(ValueError):   # last page uncovered
        build_segments_from_overrides([{"doc_type": "invoice", "start": 0, "end": 1}], 4, TYPES)

    with pytest.raises(ValueError):   # past the end of the document
        build_segments_from_overrides([{"doc_type": "invoice", "start": 0, "end": 9}], 4, TYPES)


def test_reviewer_unknown_type_falls_back_to_others():
    segments = build_segments_from_overrides(
        [{"doc_type": "not_a_configured_type", "start": 0, "end": 1}], 2, TYPES)
    assert segments[0].doc_type == OTHERS_KEY


# ─── ID-marker verification (template-driven) ────────────────────────────────

def test_id_marker_verification_passes_fails_and_skips():
    templates = {"pan_card": {"id_marker": r"\b[A-Z]{5}\d{4}[A-Z]\b"}}
    pages_md = {0: "Permanent Account Number ABCDE1234F", 1: "no identifier here"}

    good = Segment(doc_type="pan_card", start=0, end=0, pages=[0])
    bad = Segment(doc_type="pan_card", start=1, end=1, pages=[1])
    unruled = Segment(doc_type="invoice", start=1, end=1, pages=[1])

    verify_segments([good, bad, unruled], pages_md, templates)
    assert good.verified is True
    assert bad.verified is False
    assert unruled.verified is None     # no marker configured for this type


def test_invalid_id_marker_is_skipped_not_raised():
    """A bad regex must not take a document down mid-workflow."""
    templates = {"invoice": {"id_marker": "([unclosed"}}
    segment = Segment(doc_type="invoice", start=0, end=0, pages=[0])
    verify_segments([segment], {0: "anything"}, templates)
    assert segment.verified is None


# ─── Eligibility & physical split ────────────────────────────────────────────

def test_is_splittable_matrix():
    with tempfile.TemporaryDirectory() as tmp:
        multi = _make_pdf(os.path.join(tmp, "multi.pdf"), 3)
        single = _make_pdf(os.path.join(tmp, "single.pdf"), 1)
        image = os.path.join(tmp, "scan.png")
        open(image, "wb").write(b"not really a png")

        assert is_splittable(multi, 50) == (True, "", 3)
        assert is_splittable(single, 50)[:2] == (False, "single_page")
        assert is_splittable(image, 50)[:2] == (False, "not_a_pdf")
        assert is_splittable(multi, 2)[:2] == (False, "too_many_pages")
        assert is_splittable(os.path.join(tmp, "missing.pdf"), 50)[:2] == (False, "unreadable")


def test_split_pdf_preserves_every_page_exactly_once():
    with tempfile.TemporaryDirectory() as tmp:
        source = _make_pdf(os.path.join(tmp, "packet.pdf"), 5)
        segments = [
            Segment(doc_type="bank_statement", start=0, end=2, pages=[0, 1, 2]),
            Segment(doc_type="pan_card", start=3, end=4, pages=[3, 4]),
        ]
        out = split_pdf(source, segments, os.path.join(tmp, "out"))

        assert [os.path.basename(s.output_file) for s in out] == [
            "01_bank_statement_p1-3.pdf",
            "02_pan_card_p4-5.pdf",
        ]
        counts = [len(pypdf.PdfReader(s.output_file).pages) for s in out]
        assert counts == [3, 2]
        assert sum(counts) == len(pypdf.PdfReader(source).pages)


def test_split_pdf_rejects_a_page_outside_the_source():
    with tempfile.TemporaryDirectory() as tmp:
        source = _make_pdf(os.path.join(tmp, "packet.pdf"), 2)
        segments = [Segment(doc_type="invoice", start=0, end=5, pages=[0, 1, 5])]
        with pytest.raises(IndexError):
            split_pdf(source, segments, os.path.join(tmp, "out"))


def test_page_range_label_is_one_based():
    assert Segment(doc_type="invoice", start=0, end=0, pages=[0]).page_range_label == "1"
    assert Segment(doc_type="invoice", start=2, end=4, pages=[2, 3, 4]).page_range_label == "3-5"

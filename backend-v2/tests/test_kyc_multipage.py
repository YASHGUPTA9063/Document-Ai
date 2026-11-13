"""
Multi-page photo/signature extraction.

Application forms put the applicant's signature on the declaration page —
usually the last one. These check that every page of a PDF is searched, both
by the KYC extractor (utils/kyc_signature_extractor.py) and the pipeline's
shared one (utils/signature_extractor.py).

Self-contained: no database or Mistral calls.
Run with:  python -m pytest tests/test_kyc_multipage.py -v -p no:conftest
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _k, _v in {
    "MISTRAL_API_KEY": "test-key",
    "CLASSIFIER_AGENT_ID": "test-classifier",
    "VALIDATOR_AGENT_ID": "test-validator",
    "REVIEWER_AGENT_ID": "test-reviewer",
    "SIGNATURE_VISION_AGENT_ID": "test-sig-vision",
    "SIGNATURE_JUDGE_AGENT_ID": "test-sig-judge",
    "MISTRAL_WORKFLOW_ID": "test-workflow",
}.items():
    os.environ.setdefault(_k, _v)

from PIL import Image, ImageDraw  # noqa: E402

import utils.kyc_signature_extractor as kyc  # noqa: E402
import utils.signature_extractor as shared  # noqa: E402


def _page_img(colour):
    """A white page with a textured patch, so crops are never 'blank'."""
    img = Image.new("RGB", (200, 300), "white")
    d = ImageDraw.Draw(img)
    for x in range(100, 180, 4):
        d.line([(x, 220), (x + 2, 280)], fill=colour, width=2)
    return img


def _ocr_page(blocks=(), images=()):
    return SimpleNamespace(pages=[SimpleNamespace(blocks=list(blocks), images=list(images))],
                           document_annotation=None)


def _block(kind, coords):
    x1, y1, x2, y2 = coords
    return SimpleNamespace(type=kind, content="", top_left_x=x1, top_left_y=y1,
                           bottom_right_x=x2, bottom_right_y=y2)


def _annotated_image(kind, coords):
    x1, y1, x2, y2 = coords
    return SimpleNamespace(image_annotation=json.dumps({"block_type": kind}), top_left_x=x1,
                           top_left_y=y1, bottom_right_x=x2, bottom_right_y=y2)


def _vision_reply(signature=None, photo=None):
    s = signature or (None,) * 4
    p = photo or (None,) * 4
    content = json.dumps({
        "step_by_step_analysis": "",
        "signature_found": signature is not None,
        "sig_x1": s[0], "sig_y1": s[1], "sig_x2": s[2], "sig_y2": s[3], "signature_notes": None,
        "photo_found": photo is not None,
        "photo_x1": p[0], "photo_y1": p[1], "photo_x2": p[2], "photo_y2": p[3], "photo_notes": None,
    })
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def _annotation(has_signature):
    return SimpleNamespace(pages=[SimpleNamespace(blocks=[], images=[])], document_annotation=json.dumps({
        "has_signature": has_signature, "confidence": "medium", "signer_name": None,
        "signed_date": None, "signature_location": None, "additional_notes": None,
    }))


def _client(block_pass, annotation_pass=None, vision=None):
    """
    Mock Mistral client. OCR replies are keyed by page URL and by which OCR
    pass is calling (block pass vs document-annotation pass).
    """
    client = MagicMock()

    def ocr(**kw):
        url = kw["document"]["document_url"]
        if "bbox_annotation_format" in kw:
            return block_pass[url]
        return (annotation_pass or {}).get(url, _annotation(False))

    client.ocr.process.side_effect = ocr

    def chat(**kw):
        url = kw["messages"][0]["content"][0]["image_url"]["url"]
        return (vision or {}).get(url, _vision_reply())

    client.chat.complete.side_effect = chat
    return client


PAGES = None


def _two_pages():
    return [(_page_img("navy"), "data:page1"), (_page_img("blue"), "data:page2")]


# ─── Page rendering ─────────────────────────────────────────────────────────

def test_prepare_pages_renders_every_pdf_page(tmp_path):
    import fitz
    pdf = tmp_path / "form.pdf"
    doc = fitz.open()
    for text in ("page one", "page two", "page three"):
        doc.new_page().insert_text((72, 72), text)
    doc.save(str(pdf))
    doc.close()

    pages = shared._prepare_pages(str(pdf))

    assert len(pages) == 3
    assert all(url.startswith("data:image/png;base64,") for _, url in pages)
    assert len({url for _, url in pages}) == 3, "each page must be rendered separately"


def test_prepare_pages_caps_long_pdfs(tmp_path):
    import fitz
    pdf = tmp_path / "long.pdf"
    doc = fitz.open()
    for _ in range(shared.MAX_KYC_PAGES + 3):
        doc.new_page()
    doc.save(str(pdf))
    doc.close()

    assert len(shared._prepare_pages(str(pdf))) == shared.MAX_KYC_PAGES


# ─── KYC extractor ──────────────────────────────────────────────────────────

def test_kyc_signature_on_second_page_is_found(tmp_path):
    """The onboarding-form case: details on page 1, signature on page 2."""
    sig = (100, 220, 180, 280)
    client = _client(block_pass={
        "data:page1": _ocr_page(),
        "data:page2": _ocr_page(blocks=[_block("signature", sig)]),
    })
    with patch.object(kyc, "_prepare_pages", return_value=_two_pages()), \
         patch.object(kyc, "get_mistral_client", return_value=client):
        result = kyc.extract_signature_and_photo("form.pdf", "doc-1", output_dir=str(tmp_path))

    assert result["has_signature"] is True
    assert result["signature_bbox"] == {"x1": 100, "y1": 220, "x2": 180, "y2": 280}
    assert result["confidence"] == "high"
    assert os.path.exists(result["signature_crop_path"])
    assert Image.open(result["signature_crop_path"]).size == (80, 60)
    # The form has no photo; the fallback must still have tried every page for it.
    vision_urls = [c.kwargs["messages"][0]["content"][0]["image_url"]["url"]
                   for c in client.chat.complete.call_args_list]
    assert vision_urls == ["data:page1", "data:page2"]
    assert result["has_photo"] is False


def test_kyc_photo_on_page_one_and_signature_on_page_two(tmp_path):
    photo, sig = (100, 220, 180, 280), (100, 220, 170, 270)
    client = _client(block_pass={
        "data:page1": _ocr_page(images=[_annotated_image("photo", photo)]),
        "data:page2": _ocr_page(blocks=[_block("signature", sig)]),
    })
    with patch.object(kyc, "_prepare_pages", return_value=_two_pages()), \
         patch.object(kyc, "get_mistral_client", return_value=client):
        result = kyc.extract_signature_and_photo("id.pdf", "doc-2", output_dir=str(tmp_path))

    assert result["has_photo"] and result["has_signature"]
    assert result["photo_bbox"]["x2"] == 180 and result["signature_bbox"]["x2"] == 170
    client.chat.complete.assert_not_called()  # both found by OCR — no vision fallback


def test_kyc_vision_signature_ignored_on_page_ocr_ruled_out(tmp_path):
    """Script-font fields on page 1 must not be taken as the signature."""
    wrong, right = (100, 220, 150, 250), (110, 225, 175, 275)
    client = _client(
        block_pass={"data:page1": _ocr_page(), "data:page2": _ocr_page()},
        annotation_pass={"data:page1": _annotation(False), "data:page2": _annotation(True)},
        vision={"data:page1": _vision_reply(signature=wrong), "data:page2": _vision_reply(signature=right)},
    )
    with patch.object(kyc, "_prepare_pages", return_value=_two_pages()), \
         patch.object(kyc, "get_mistral_client", return_value=client):
        result = kyc.extract_signature_and_photo("form.pdf", "doc-3", output_dir=str(tmp_path))

    assert result["has_signature"] is True
    assert result["signature_bbox"] == {"x1": 110, "y1": 225, "x2": 175, "y2": 275}


def test_kyc_single_page_vision_signature_still_accepted(tmp_path):
    """Single-page documents keep the old behaviour: no annotation gating."""
    sig = (100, 220, 180, 280)
    client = _client(
        block_pass={"data:page1": _ocr_page()},
        annotation_pass={"data:page1": _annotation(False)},
        vision={"data:page1": _vision_reply(signature=sig)},
    )
    with patch.object(kyc, "_prepare_pages", return_value=_two_pages()[:1]), \
         patch.object(kyc, "get_mistral_client", return_value=client):
        result = kyc.extract_signature_and_photo("id.jpg", "doc-4", output_dir=str(tmp_path))

    assert result["has_signature"] is True


def test_kyc_block_pass_error_on_one_page_does_not_lose_others(tmp_path):
    sig = (100, 220, 180, 280)
    client = _client(block_pass={"data:page2": _ocr_page(blocks=[_block("signature", sig)])})
    original = client.ocr.process.side_effect

    def flaky(**kw):
        if kw["document"]["document_url"] == "data:page1" and "bbox_annotation_format" in kw:
            raise RuntimeError("OCR 500")
        return original(**kw)

    client.ocr.process.side_effect = flaky
    with patch.object(kyc, "_prepare_pages", return_value=_two_pages()), \
         patch.object(kyc, "get_mistral_client", return_value=client):
        result = kyc.extract_signature_and_photo("form.pdf", "doc-5", output_dir=str(tmp_path))

    assert result["has_signature"] is True


def test_kyc_manual_box_on_named_page(tmp_path):
    pages = [(Image.new("RGB", (200, 300), "white"), "data:page1"), (_page_img("navy"), "data:page2")]
    boxes = {"signature": {"x1": 50, "y1": 73, "x2": 90, "y2": 93, "page": 2}}
    with patch.object(kyc, "_prepare_pages", return_value=pages), \
         patch.object(kyc, "get_mistral_client", return_value=MagicMock()):
        result = kyc.extract_signature_and_photo("form.pdf", "doc-6", output_dir=str(tmp_path), kyc_boxes=boxes)

    assert result["has_signature"] is True
    assert not kyc._is_blank(Image.open(result["signature_crop_path"])), "crop must come from page 2"


# ─── Shared (pipeline) extractor ────────────────────────────────────────────

def test_shared_signature_on_second_page_is_found(tmp_path):
    sig = (100, 220, 180, 280)
    client = _client(block_pass={
        "data:page1": _ocr_page(),
        "data:page2": _ocr_page(images=[_annotated_image("signature", sig)]),
    })
    with patch.object(shared, "_prepare_pages", return_value=_two_pages()), \
         patch.object(shared, "get_mistral_client", return_value=client):
        result = shared.extract_signature_and_photo("form.pdf", "doc-7", output_dir=str(tmp_path))

    assert result["has_signature"] is True
    assert result["signature_bbox"] == {"x1": 100, "y1": 220, "x2": 180, "y2": 280}
    assert result["signature_base64"]
    # Later pages crop into their own folder so page 1's files are never overwritten.
    assert os.path.dirname(result["signature_crop_path"]) == os.path.abspath(tmp_path / "page_2")

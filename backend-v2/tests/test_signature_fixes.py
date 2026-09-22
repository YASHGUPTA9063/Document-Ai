"""
Tests for signature extraction fixes:
  Fix 1: Deterministic crop_kyc_images fallback in extractor_activity
  Fix 2: PATH 2 signature detection via image_annotation.block_type

These tests are self-contained and do NOT require a database or external services.
Run with:  venv\\Scripts\\python.exe -m pytest tests\\test_signature_fixes.py -v --override-ini="asyncio_mode=auto" -p no:conftest
"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace

# Ensure the backend-v2 directory is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set minimal environment so config.py doesn't blow up at import time
os.environ.setdefault("MISTRAL_API_KEY", "test-key")
os.environ.setdefault("CLASSIFIER_AGENT_ID", "test-classifier")
os.environ.setdefault("VALIDATOR_AGENT_ID", "test-validator")
os.environ.setdefault("REVIEWER_AGENT_ID", "test-reviewer")
os.environ.setdefault("SIGNATURE_VISION_AGENT_ID", "test-sig-vision")
os.environ.setdefault("SIGNATURE_JUDGE_AGENT_ID", "test-sig-judge")
os.environ.setdefault("MISTRAL_WORKFLOW_ID", "test-workflow")


# ─────────────────────────────────────────────────────────────────────
# Fix 2 Tests: PATH 2 signature detection via image_annotation
# ─────────────────────────────────────────────────────────────────────

class TestPath2SignatureDetection:
    """
    Verifies that PATH 2 in extract_signature_and_photo correctly checks
    image_annotation.block_type == 'signature' instead of the old
    broken b.type == 'signature'.
    """

    def _make_ocr_response(self, annotations):
        """
        Build a mock OCR response with images carrying image_annotation.
        annotations: list of dicts with "annotation" and "coords".
        """
        images = []
        for ann in annotations:
            img_obj = SimpleNamespace(
                image_annotation=json.dumps(ann.get("annotation", {})),
                top_left_x=ann["coords"][0],
                top_left_y=ann["coords"][1],
                bottom_right_x=ann["coords"][2],
                bottom_right_y=ann["coords"][3],
            )
            images.append(img_obj)

        page = SimpleNamespace(
            images=images,
            blocks=[],
        )
        return SimpleNamespace(
            pages=[page],
            document_annotation=None,
        )

    @patch("utils.signature_extractor.get_mistral_client")
    @patch("utils.signature_extractor._prepare_image_and_url")
    @patch("utils.signature_extractor._resolve_raw_file_path", side_effect=lambda p: p)
    def test_signature_found_via_annotation(self, mock_resolve, mock_prep, mock_client):
        """PATH 2 should find a signature when image_annotation.block_type == 'signature'."""
        from PIL import Image
        from utils.signature_extractor import extract_signature_and_photo

        test_img = Image.new("RGB", (100, 100), "white")
        mock_prep.return_value = (test_img, "data:image/png;base64,AAAA")

        ocr_resp = self._make_ocr_response([
            {
                "annotation": {"block_type": "signature"},
                "coords": (10, 70, 50, 90),
            }
        ])
        client_instance = MagicMock()
        client_instance.ocr.process.return_value = ocr_resp
        mock_client.return_value = client_instance

        out_dir = os.path.join(os.path.dirname(__file__), "scratch", "crops_001")
        result = extract_signature_and_photo(
            file_path="fake.jpg",
            document_id="test-doc-001",
            output_dir=out_dir,
            kyc_boxes=None,
        )

        assert result["has_signature"] is True, "Signature should be detected via image_annotation"
        assert result["signature_bbox"] == {"x1": 10, "y1": 70, "x2": 50, "y2": 90}
        assert result["signature_base64"] is not None
        assert result["confidence"] == "high"

    @patch("utils.signature_extractor.get_mistral_client")
    @patch("utils.signature_extractor._prepare_image_and_url")
    @patch("utils.signature_extractor._resolve_raw_file_path", side_effect=lambda p: p)
    def test_photo_and_signature_both_found(self, mock_resolve, mock_prep, mock_client):
        """PATH 2 should find both signature and photo from image_annotation."""
        from PIL import Image
        from utils.signature_extractor import extract_signature_and_photo

        test_img = Image.new("RGB", (200, 200), "white")
        mock_prep.return_value = (test_img, "data:image/png;base64,AAAA")

        ocr_resp = self._make_ocr_response([
            {
                "annotation": {"block_type": "signature"},
                "coords": (100, 150, 180, 190),
            },
            {
                "annotation": {"block_type": "photo"},
                "coords": (10, 20, 60, 100),
            },
        ])
        client_instance = MagicMock()
        client_instance.ocr.process.return_value = ocr_resp
        mock_client.return_value = client_instance

        out_dir = os.path.join(os.path.dirname(__file__), "scratch", "crops_002")
        result = extract_signature_and_photo(
            file_path="fake.jpg",
            document_id="test-doc-002",
            output_dir=out_dir,
            kyc_boxes=None,
        )

        assert result["has_signature"] is True
        assert result["has_photo"] is True

    @patch("utils.signature_extractor.get_mistral_client")
    @patch("utils.signature_extractor._prepare_image_and_url")
    @patch("utils.signature_extractor._resolve_raw_file_path", side_effect=lambda p: p)
    def test_other_annotation_not_matched(self, mock_resolve, mock_prep, mock_client):
        """Images annotated as 'other' should NOT be detected as signatures."""
        from PIL import Image
        from utils.signature_extractor import extract_signature_and_photo

        test_img = Image.new("RGB", (100, 100), "white")
        mock_prep.return_value = (test_img, "data:image/png;base64,AAAA")

        ocr_resp = self._make_ocr_response([
            {
                "annotation": {"block_type": "other"},
                "coords": (10, 70, 50, 90),
            }
        ])

        fallback_ocr = SimpleNamespace(
            pages=[SimpleNamespace(images=[], blocks=[])],
            document_annotation=json.dumps({
                "has_signature": False, "confidence": "low",
                "signer_name": None, "signed_date": None,
                "signature_location": None, "additional_notes": None,
            }),
        )

        client_instance = MagicMock()
        client_instance.ocr.process.side_effect = [ocr_resp, fallback_ocr]
        client_instance.chat.complete.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "step_by_step_analysis": "No signature found",
                "signature_found": False,
                "sig_x1": None, "sig_y1": None, "sig_x2": None, "sig_y2": None,
                "signature_notes": None,
                "photo_found": False,
                "photo_x1": None, "photo_y1": None, "photo_x2": None, "photo_y2": None,
                "photo_notes": None,
            })))]
        )
        mock_client.return_value = client_instance

        out_dir = os.path.join(os.path.dirname(__file__), "scratch", "crops_003")
        result = extract_signature_and_photo(
            file_path="fake.jpg",
            document_id="test-doc-003",
            output_dir=out_dir,
            kyc_boxes=None,
        )

        assert result["has_signature"] is False, "'other' block_type should not match as signature"

    @patch("utils.signature_extractor.get_mistral_client")
    @patch("utils.signature_extractor._prepare_image_and_url")
    @patch("utils.signature_extractor._resolve_raw_file_path", side_effect=lambda p: p)
    def test_dict_annotation_format(self, mock_resolve, mock_prep, mock_client):
        """annotation can also be a dict (not JSON string) — should still work."""
        from PIL import Image
        from utils.signature_extractor import extract_signature_and_photo

        test_img = Image.new("RGB", (100, 100), "white")
        mock_prep.return_value = (test_img, "data:image/png;base64,AAAA")

        img_obj = SimpleNamespace(
            image_annotation={"block_type": "signature"},  # dict, not JSON string
            top_left_x=20,
            top_left_y=60,
            bottom_right_x=80,
            bottom_right_y=95,
        )
        page = SimpleNamespace(images=[img_obj], blocks=[])
        ocr_resp = SimpleNamespace(pages=[page], document_annotation=None)

        client_instance = MagicMock()
        client_instance.ocr.process.return_value = ocr_resp
        mock_client.return_value = client_instance

        out_dir = os.path.join(os.path.dirname(__file__), "scratch", "crops_004")
        result = extract_signature_and_photo(
            file_path="fake.jpg",
            document_id="test-doc-004",
            output_dir=out_dir,
            kyc_boxes=None,
        )

        assert result["has_signature"] is True, "Dict annotation with block_type=signature should be found"


# ─────────────────────────────────────────────────────────────────────
# Fix 1 Tests: Deterministic crop_kyc_images fallback
# Tests are synchronous — they call the inner function directly.
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicCropFallback:
    """
    Verifies that when the LLM agent does NOT call crop_kyc_images,
    the deterministic fallback in extractor_activity kicks in for KYC docs.
    """

    def test_fallback_called_when_agent_skips_crop(self):
        """If the agent skips crop_kyc_images, the fallback should call it."""
        import asyncio

        mock_db = MagicMock()
        mock_db.update_error = AsyncMock()
        with patch("activities.extractor.db", mock_db), \
             patch("activities.extractor.client") as mock_client, \
             patch("activities.extractor.crop_kyc_images") as mock_crop, \
             patch("activities.extractor.extract_text_from_document") as mock_extract, \
             patch("tools.extractor.get_template_metadata") as mock_get_meta, \
             patch("tools.extractor.get_template_fields") as mock_get_fields, \
             patch("activities.extractor.settings") as mock_settings, \
             patch("activities.extractor._run_vllm_fallback", new_callable=AsyncMock, return_value={}):

            mock_settings.GENERAL_EXTRACTOR_AGENT_ID = "agent-123"
            mock_get_meta.return_value = {"is_kyc": True, "kyc_boxes": None, "use_vlm": False, "vlm_fields": []}
            mock_get_fields.return_value = [{"key": "name", "type": "Text", "required": True}]

            mock_extract.return_value = {
                "tool_output": {"raw_ocr_text": "text", "structured_ocr_extraction": {"name": "John"}, "vlm_field_confidences": {}},
                "raw_text": "text", "confidence": 0.95, "word_confidence_scores": [],
            }

            mock_crop.return_value = {
                "tool_output": {"has_signature": True, "has_photo": False, "signer_name": "John"},
                "kyc_image_result": {
                    "has_signature": True, "signature_base64": "dGVzdA==",
                    "has_photo": False, "photo_base64": None, "signer_name": "John",
                },
            }

            # Agent only calls extract_text, NOT crop_kyc_images
            tc = MagicMock()
            tc.id = "tc-1"
            tc.function.name = "extract_text_from_document"
            tc.function.arguments = json.dumps({"file_path": "/test.jpg", "doc_type": "driving_license"})

            first_msg = MagicMock()
            first_msg.tool_calls = [tc]
            first_msg.content = ""

            final_msg = MagicMock()
            final_msg.tool_calls = None
            final_msg.content = json.dumps({
                "raw_extracted": {"name": "John"},
                "normalized_extracted": {"name": "John"},
            })

            mock_client.agents.complete_async = AsyncMock(side_effect=[
                MagicMock(choices=[MagicMock(message=first_msg)]),
                MagicMock(choices=[MagicMock(message=final_msg)]),
            ])

            from activities.extractor import extractor_activity

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(extractor_activity.__wrapped__(
                    document_id="doc-001", file_path="/test.jpg", doc_type="driving_license",
                ))
            finally:
                loop.close()

            # Fallback should have called crop_kyc_images
            mock_crop.assert_called_once_with("/test.jpg", "driving_license", "doc-001")
            assert result["fields"].get("signature_detected") is True
            assert result["fields"].get("signature_image") == "dGVzdA=="

    def test_fallback_not_called_when_agent_already_called_crop(self):
        """If the agent DID call crop_kyc_images, the fallback should NOT run again."""
        import asyncio

        mock_db = MagicMock()
        mock_db.update_error = AsyncMock()
        with patch("activities.extractor.db", mock_db), \
             patch("activities.extractor.client") as mock_client, \
             patch("activities.extractor.crop_kyc_images") as mock_crop, \
             patch("activities.extractor.extract_text_from_document") as mock_extract, \
             patch("tools.extractor.get_template_metadata") as mock_get_meta, \
             patch("tools.extractor.get_template_fields") as mock_get_fields, \
             patch("activities.extractor.settings") as mock_settings, \
             patch("activities.extractor._run_vllm_fallback", new_callable=AsyncMock, return_value={}):

            mock_settings.GENERAL_EXTRACTOR_AGENT_ID = "agent-123"
            mock_get_meta.return_value = {"is_kyc": True, "kyc_boxes": None, "use_vlm": False, "vlm_fields": []}
            mock_get_fields.return_value = [{"key": "name", "type": "Text", "required": True}]

            mock_extract.return_value = {
                "tool_output": {"raw_ocr_text": "text", "structured_ocr_extraction": {"name": "Jane"}, "vlm_field_confidences": {}},
                "raw_text": "text", "confidence": 0.95, "word_confidence_scores": [],
            }

            mock_crop.return_value = {
                "tool_output": {"has_signature": True, "has_photo": True, "signer_name": "Jane"},
                "kyc_image_result": {
                    "has_signature": True, "signature_base64": "c2ln",
                    "has_photo": True, "photo_base64": "cGhvdG8=", "signer_name": "Jane",
                },
            }

            # Agent calls BOTH tools
            tc1 = MagicMock()
            tc1.id = "tc-1"
            tc1.function.name = "extract_text_from_document"
            tc1.function.arguments = json.dumps({"file_path": "/test.jpg", "doc_type": "driving_license"})

            tc2 = MagicMock()
            tc2.id = "tc-2"
            tc2.function.name = "crop_kyc_images"
            tc2.function.arguments = json.dumps({"file_path": "/test.jpg", "doc_type": "driving_license"})

            first_msg = MagicMock()
            first_msg.tool_calls = [tc1, tc2]
            first_msg.content = ""

            final_msg = MagicMock()
            final_msg.tool_calls = None
            final_msg.content = json.dumps({
                "raw_extracted": {"name": "Jane"},
                "normalized_extracted": {"name": "Jane"},
            })

            mock_client.agents.complete_async = AsyncMock(side_effect=[
                MagicMock(choices=[MagicMock(message=first_msg)]),
                MagicMock(choices=[MagicMock(message=final_msg)]),
            ])

            from activities.extractor import extractor_activity

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(extractor_activity.__wrapped__(
                    document_id="doc-002", file_path="/test.jpg", doc_type="driving_license",
                ))
            finally:
                loop.close()

            # crop_kyc_images called ONCE by the agent loop, NOT again by the fallback
            mock_crop.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--override-ini=asyncio_mode=auto", "-p", "no:conftest"])

import os
import sys
import unittest
import json
from dotenv import load_dotenv

# Load env variables from local .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Add app to path so we can import services
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))

from app.services.ai_service import AIService
from app.services.page_service import PageService

class TestDrillDownCore(unittest.TestCase):
    def test_extract_json_raw(self):
        """Test extraction of raw json."""
        raw_text = '{"object": "camera_lens", "materials": ["glass", "brass"]}'
        extracted = AIService._extract_json(raw_text)
        self.assertEqual(json.loads(extracted)["object"], "camera_lens")

    def test_extract_json_markdown(self):
        """Test extraction of json wrapped in markdown codeblocks."""
        raw_text = '```json\n{"object": "camera_lens", "materials": ["glass"]}\n```'
        extracted = AIService._extract_json(raw_text)
        self.assertEqual(json.loads(extracted)["object"], "camera_lens")

    def test_extract_json_messy(self):
        """Test repairing of unbalanced braces/quotes."""
        raw_text = 'Text before {"object": "camera_lens"'
        extracted = AIService._extract_json(raw_text)
        data = json.loads(extracted)
        self.assertEqual(data["object"], "camera_lens")

    def test_sanitize_coordinates_basic(self):
        """Test normalizing names and coordinate bounds."""
        messy_detail = {
            "name": "Lens Shutter",
            "bbox_2d": [100, 200, 200, 300] # y1, x1, y2, x2 -> center x=250, y=150 -> norm x=0.25, y=0.15
        }
        sanitized = AIService._sanitize_coordinates([messy_detail])
        details = sanitized.get("granular_details", [])
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["label"], "Lens Shutter")
        self.assertEqual(details[0]["point"], [0.25, 0.15])

    def test_sanitize_coordinates_scale(self):
        """Test coordinate values are scaled down if they exceed 1.0 (e.g., pixel space 0-1000)."""
        messy_detail = {
            "component": "Aperture Ring",
            "point": [450.0, 620.0]
        }
        sanitized = AIService._sanitize_coordinates([messy_detail])
        detail = sanitized["granular_details"][0]
        self.assertEqual(detail["label"], "Aperture Ring")
        self.assertEqual(detail["point"], [0.45, 0.62])

    def test_sanitize_coordinates_flattening(self):
        """Test robust flattening of dict headline/explainer metadata to flat strings."""
        data = {
            "editorial_headline": {"text": "Projector Mechanics"},
            "explainer_paragraph": {
                "sentence_1": "This is light.",
                "sentence_2": "It is focused."
            },
            "granular_details": []
        }
        sanitized = AIService._sanitize_coordinates(data)
        self.assertEqual(sanitized["editorial_headline"], "Projector Mechanics")
        self.assertEqual(sanitized["explainer_paragraph"], "This is light. It is focused.")
def test_generate_page_hash_consistency(self):
    """Test that get_or_create_page and stream_page page IDs are perfectly synchronized."""
    ps = PageService()
    parent_id = "parent123"
    x = 0.50001
    y = 0.25004
    vision_model = "qwen3.5"
    grounding_mode = "sam2"

    hash_val = ps.generate_page_hash(parent_id, x, y, vision_model, grounding_mode)

    # Verify that rounding is consistently 4 decimal places inside key generator
    rx = round(x, 4)
    ry = round(y, 4)
    expected_raw_key = f"drill_{parent_id}_{rx}_{ry}_{vision_model}_{grounding_mode}_inside"
    expected_hash = ps.get_hash(expected_raw_key)

    self.assertEqual(hash_val, expected_hash)

    # Test POV mode hashing as well
    hash_val_pov = ps.generate_page_hash(parent_id, x, y, vision_model, grounding_mode, drill_mode="pov")
    expected_raw_key_pov = f"drill_{parent_id}_{rx}_{ry}_{vision_model}_{grounding_mode}_pov"
    expected_hash_pov = ps.get_hash(expected_raw_key_pov)
    self.assertEqual(hash_val_pov, expected_hash_pov)

    def test_get_parent_path_standard(self):
        """Test that standard parent IDs resolve to the root static directory."""
        ps = PageService()
        path = ps._get_parent_path("my_parent_image")
        self.assertEqual(path, os.path.join("static", "my_parent_image.png"))

    def test_get_parent_path_document(self):
        """Test that document-based parent IDs resolve to their specific page subdirectory."""
        ps = PageService()
        path = ps._get_parent_path("doc_abc123_p5")
        self.assertEqual(path, os.path.join("static", "documents", "abc123", "page_5.png"))

if __name__ == "__main__":
    unittest.main()

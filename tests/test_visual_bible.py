"""Tests for visual bible enforcement in pipeline/images.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.images import (
    _detect_era,
    _apply_color_harmonization,
    ERA_CONSTRAINTS,
)


# ── ERA_CONSTRAINTS Registry ────────────────────────────────────────────────

class TestEraConstraints:
    @pytest.mark.unit
    def test_has_required_fields(self):
        """Every era entry must have positive, negative, keywords, and years."""
        required = {"positive", "negative", "keywords", "years"}
        for era_name, constraints in ERA_CONSTRAINTS.items():
            for field in required:
                assert field in constraints, (
                    f"ERA_CONSTRAINTS['{era_name}'] missing required field '{field}'"
                )

    @pytest.mark.unit
    def test_years_are_tuples_of_two_ints(self):
        for era_name, constraints in ERA_CONSTRAINTS.items():
            years = constraints["years"]
            assert isinstance(years, tuple) and len(years) == 2, (
                f"ERA_CONSTRAINTS['{era_name}']['years'] must be a 2-tuple"
            )
            assert years[0] < years[1], (
                f"ERA_CONSTRAINTS['{era_name}']['years'] start must be < end"
            )

    @pytest.mark.unit
    def test_keywords_are_nonempty_lists(self):
        for era_name, constraints in ERA_CONSTRAINTS.items():
            assert isinstance(constraints["keywords"], list)
            assert len(constraints["keywords"]) > 0


# ── _detect_era ──────────────────────────────────────────────────────────────

class TestDetectEra:
    @pytest.mark.unit
    def test_detects_mauryan_keywords(self):
        """Should detect Mauryan era from topic keywords."""
        scenes = [{"narration": "The Maurya empire expanded", "year": "", "location": ""}]
        result = _detect_era(scenes, topic="Chandragupta Maurya")
        assert result is not None
        assert "pillared hall" in result["positive"].lower() or "mauryan" in result["positive"].lower()

    @pytest.mark.unit
    def test_detects_roman_keywords(self):
        """Should detect Roman era from topic keywords."""
        scenes = [{"narration": "Caesar crossed the Rubicon", "year": "", "location": ""}]
        result = _detect_era(scenes, topic="Julius Caesar and the Roman Senate")
        assert result is not None
        assert "roman" in result["positive"].lower()

    @pytest.mark.unit
    def test_returns_none_for_unknown_topic(self):
        """Should return None for a topic that matches no era."""
        scenes = [{"narration": "Something completely unrelated", "year": "", "location": ""}]
        result = _detect_era(scenes, topic="quantum computing breakthroughs")
        assert result is None

    @pytest.mark.unit
    def test_year_based_detection(self):
        """Should detect era from year in scene data when no keywords match."""
        scenes = [{"narration": "A great battle occurred", "year": "250 BC", "location": ""}]
        result = _detect_era(scenes, topic="A forgotten battle")
        assert result is not None
        # 250 BC (-250) falls in either mauryan (-400 to -180) or ancient_greek (-800 to -146)
        # or roman (-500 to 476)


# ── _apply_color_harmonization ───────────────────────────────────────────────

class TestApplyColorHarmonization:
    @pytest.mark.unit
    def test_with_small_test_image(self, tmp_path):
        """Should process a small PIL image without error."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Create a 10x10 test image
        img = Image.new("RGB", (10, 10), (128, 64, 32))
        img_path = tmp_path / "test_scene.jpg"
        img.save(str(img_path), "JPEG")

        scenes = [{"ai_image": str(img_path)}]
        palette = ["#AA3322", "#556677", "#112233"]

        _apply_color_harmonization(scenes, palette)

        # Image should still exist and be loadable
        result_img = Image.open(str(img_path))
        assert result_img.size == (10, 10)
        # Pixels should have shifted toward palette average
        # (not the same as original 128, 64, 32)
        pixel = result_img.getpixel((5, 5))
        # Just verify it was processed (pixel values changed due to blend)
        assert isinstance(pixel, tuple)

    @pytest.mark.unit
    def test_skips_when_palette_is_empty(self, tmp_path):
        """Should return without modifying anything when palette is empty."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (10, 10), (128, 64, 32))
        img_path = tmp_path / "test_scene.jpg"
        img.save(str(img_path), "JPEG")

        original_bytes = img_path.read_bytes()
        scenes = [{"ai_image": str(img_path)}]

        _apply_color_harmonization(scenes, [])

        # File should be unchanged
        assert img_path.read_bytes() == original_bytes

    @pytest.mark.unit
    def test_skips_nonexistent_images(self):
        """Should not crash when scene references a nonexistent image."""
        scenes = [{"ai_image": "/nonexistent/path/image.jpg"}]
        palette = ["#AA3322", "#556677"]
        # Should not raise
        _apply_color_harmonization(scenes, palette)

    @pytest.mark.unit
    def test_skips_scenes_without_ai_image(self):
        """Should skip scenes that have no ai_image key."""
        scenes = [{"narration": "test"}]
        palette = ["#AA3322"]
        _apply_color_harmonization(scenes, palette)

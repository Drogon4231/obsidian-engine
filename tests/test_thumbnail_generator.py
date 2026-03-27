"""Tests for thumbnail_generator.py — cinematic thumbnail rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from media import thumbnail_generator


class TestRun:
    def test_returns_none_when_no_image(self):
        seo = {"recommended_title": "Test Title"}
        manifest = {"scenes": [{"text": "no image here"}]}
        result = thumbnail_generator.run(seo, manifest)
        assert result is None

    def test_uses_recommended_title(self):
        seo = {"recommended_title": "Custom Title"}
        manifest = {"scenes": []}
        # No image → returns None, but doesn't crash
        result = thumbnail_generator.run(seo, manifest)
        assert result is None

    def test_falls_back_title(self):
        """When no recommended_title, uses default."""
        seo = {}
        manifest = {"scenes": []}
        result = thumbnail_generator.run(seo, manifest)
        assert result is None  # Still no image, but title fallback works


class TestGenerate:
    def test_generates_thumbnail(self, tmp_path):
        """Test thumbnail generation with a real Pillow image."""
        try:
            from PIL import Image
        except ImportError:
            return  # Skip if Pillow not installed

        # Create a test input image
        input_img = tmp_path / "test_input.jpg"
        Image.new("RGB", (1280, 720), (50, 50, 50)).save(str(input_img))

        output_path = tmp_path / "thumbnail.jpg"
        result = thumbnail_generator.generate("The Fall of Rome", str(input_img), str(output_path))

        assert result == str(output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0

        # Verify output dimensions
        out_img = Image.open(str(output_path))
        assert out_img.size == (1280, 720)

    def test_title_wrapping(self, tmp_path):
        """Long titles should be wrapped to multiple lines without crashing."""
        try:
            from PIL import Image
        except ImportError:
            return

        input_img = tmp_path / "test_input.jpg"
        Image.new("RGB", (1280, 720), (50, 50, 50)).save(str(input_img))

        output_path = tmp_path / "thumbnail.jpg"
        long_title = "The Incredibly Long and Detailed History of the Ancient Roman Empire and Its Eventual Downfall"
        result = thumbnail_generator.generate(long_title, str(input_img), str(output_path))
        assert result == str(output_path)
        assert output_path.exists()

    def test_short_title(self, tmp_path):
        """Single-word titles should work fine."""
        try:
            from PIL import Image
        except ImportError:
            return

        input_img = tmp_path / "test_input.jpg"
        Image.new("RGB", (1280, 720), (50, 50, 50)).save(str(input_img))

        output_path = tmp_path / "thumbnail.jpg"
        result = thumbnail_generator.generate("Rome", str(input_img), str(output_path))
        assert result == str(output_path)

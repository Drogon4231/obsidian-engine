"""Tests for architectural ambient in scripts/setup_ambience.py."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.setup_ambience import (
    get_ambient_file,
    AMBIENT_TRACKS,
    ARCHITECTURE_TRACKS,
    AMBIENCE_DIR,
)


class TestArchitectureTracks:
    @pytest.mark.unit
    def test_has_required_fields(self):
        """Every architecture track must have file, url, desc, keywords."""
        required = {"file", "url", "desc", "keywords"}
        for key, info in ARCHITECTURE_TRACKS.items():
            for field in required:
                assert field in info, (
                    f"ARCHITECTURE_TRACKS['{key}'] missing required field '{field}'"
                )

    @pytest.mark.unit
    def test_keywords_are_nonempty_lists(self):
        for key, info in ARCHITECTURE_TRACKS.items():
            assert isinstance(info["keywords"], list)
            assert len(info["keywords"]) > 0


class TestGetAmbientFile:
    @pytest.mark.unit
    def test_returns_mood_based_when_no_location(self, tmp_path):
        """Should return mood-based ambient when no location is provided."""
        # Create the mood ambient file so get_ambient_file finds it
        with patch.object(
            sys.modules["scripts.setup_ambience"], "AMBIENCE_DIR", tmp_path
        ):
            mood_file = tmp_path / AMBIENT_TRACKS["dark"]["file"]
            mood_file.write_bytes(b"\x00" * 100)

            result = get_ambient_file("dark")
            assert result == f"ambience/{AMBIENT_TRACKS['dark']['file']}"

    @pytest.mark.unit
    def test_returns_architecture_based_when_location_matches(self, tmp_path):
        """Should return architecture-based ambient when location matches keywords."""
        with patch.object(
            sys.modules["scripts.setup_ambience"], "AMBIENCE_DIR", tmp_path
        ):
            # Create the architecture ambient file
            arch_info = ARCHITECTURE_TRACKS["stone_interior"]
            arch_file = tmp_path / arch_info["file"]
            arch_file.write_bytes(b"\x00" * 100)

            result = get_ambient_file("dark", location="throne chamber")
            assert result == f"ambience/{arch_info['file']}"

    @pytest.mark.unit
    def test_falls_back_to_mood_when_location_no_match(self, tmp_path):
        """Should fall back to mood-based when location doesn't match any architecture."""
        with patch.object(
            sys.modules["scripts.setup_ambience"], "AMBIENCE_DIR", tmp_path
        ):
            mood_file = tmp_path / AMBIENT_TRACKS["tense"]["file"]
            mood_file.write_bytes(b"\x00" * 100)

            result = get_ambient_file("tense", location="spaceship cockpit")
            assert result == f"ambience/{AMBIENT_TRACKS['tense']['file']}"

    @pytest.mark.unit
    def test_returns_empty_when_no_files_exist(self, tmp_path):
        """Should return empty string when no ambient files exist on disk."""
        with patch.object(
            sys.modules["scripts.setup_ambience"], "AMBIENCE_DIR", tmp_path
        ):
            result = get_ambient_file("dark")
            assert result == ""

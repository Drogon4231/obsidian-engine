"""Tests for TTS Format Agent — pronunciation guide."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.tts_format_agent import (
    _apply_pronunciation_guide,
    PRONUNCIATION_MAP,
)


class TestPronunciationMap:
    @pytest.mark.unit
    def test_map_is_not_empty(self):
        """PRONUNCIATION_MAP must contain entries."""
        assert len(PRONUNCIATION_MAP) > 0

    @pytest.mark.unit
    def test_map_has_known_entries(self):
        """Spot-check that well-known terms are present."""
        assert "Chanakya" in PRONUNCIATION_MAP
        assert "Tutankhamun" in PRONUNCIATION_MAP
        assert "Machiavelli" in PRONUNCIATION_MAP


class TestApplyPronunciationGuide:
    @pytest.mark.unit
    def test_replaces_first_occurrence_only(self):
        """Only the first occurrence of a term should be replaced."""
        text = "Chanakya was wise. Chanakya wrote the Arthashastra."
        result, count = _apply_pronunciation_guide(text)
        respelling = PRONUNCIATION_MAP["Chanakya"]
        # First occurrence replaced
        assert respelling in result
        # Second occurrence stays as original
        assert result.count(respelling) == 1
        assert "Chanakya" in result  # second occurrence still present

    @pytest.mark.unit
    def test_no_matching_terms_returns_unchanged(self):
        """Text with no matching terms should be returned unchanged."""
        text = "The quick brown fox jumps over the lazy dog."
        result, count = _apply_pronunciation_guide(text)
        assert result == text
        assert count == 0

    @pytest.mark.unit
    def test_multiple_terms_in_one_text(self):
        """Multiple different terms should each be replaced once."""
        text = "Chanakya advised Chandragupta on statecraft."
        result, count = _apply_pronunciation_guide(text)
        assert PRONUNCIATION_MAP["Chanakya"] in result
        assert PRONUNCIATION_MAP["Chandragupta"] in result
        assert count == 2

    @pytest.mark.unit
    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        text = "The writings of CHANAKYA are legendary. Also chanakya was smart."
        result, count = _apply_pronunciation_guide(text)
        respelling = PRONUNCIATION_MAP["Chanakya"]
        assert respelling in result
        assert count >= 1

    @pytest.mark.unit
    def test_returns_tuple(self):
        """Return value is a (str, int) tuple."""
        result = _apply_pronunciation_guide("Hello world")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)

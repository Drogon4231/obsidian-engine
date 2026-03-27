"""Tests for trend_detector.py — trend detection and relevance scoring."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from intel.trend_detector import _is_history_relevant, _relevance_score, HISTORY_KEYWORDS


class TestHistoryRelevance:
    def test_relevant_topics(self):
        assert _is_history_relevant("The Fall of the Roman Empire")
        assert _is_history_relevant("Ancient Egyptian Pyramid Construction")
        assert _is_history_relevant("Medieval Plague Doctors")
        assert _is_history_relevant("Viking Raid on Lindisfarne")

    def test_irrelevant_topics(self):
        assert not _is_history_relevant("Best iPhone Cases 2024")
        assert not _is_history_relevant("How to Cook Pasta")
        assert not _is_history_relevant("New JavaScript Framework")

    def test_case_insensitive(self):
        assert _is_history_relevant("ANCIENT ROME")
        assert _is_history_relevant("medieval CASTLE")


class TestRelevanceScore:
    def test_score_range(self):
        """Score should always be 0-1."""
        for topic in ["roman empire battle siege", "hello world", "", "ancient"]:
            score = _relevance_score(topic)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for '{topic}'"

    def test_more_keywords_higher_score(self):
        """More keyword matches should give higher scores."""
        low = _relevance_score("ancient temple")
        high = _relevance_score("ancient roman empire battle siege massacre")
        assert high > low

    def test_empty_string(self):
        assert _relevance_score("") == 0.0

    def test_max_score_capped(self):
        """Score should cap at 1.0 even with many matches."""
        all_keywords = " ".join(HISTORY_KEYWORDS)
        score = _relevance_score(all_keywords)
        assert score == 1.0

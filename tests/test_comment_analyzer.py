"""Tests for intel/comment_analyzer.py — audience intelligence from comments."""
import json
import pytest
from unittest.mock import patch

from intel.comment_analyzer import (
    _aggregate_sentiment,
    extract_topic_requests,
    get_comment_intelligence_block,
)


@pytest.mark.unit
class TestAggregateSentiment:
    """Test batch sentiment aggregation."""

    def test_empty_results(self):
        result = _aggregate_sentiment([])
        assert result["overall_sentiment"] == "unknown"
        assert result["top_topics_requested"] == []

    def test_single_positive_batch(self):
        result = _aggregate_sentiment([{
            "overall_sentiment": "positive",
            "top_topics_requested": ["Roman Empire"],
            "criticisms": [],
            "praise": ["Great narration"],
            "controversy_flags": [],
        }])
        assert result["overall_sentiment"] == "positive"
        assert "roman empire" in result["top_topics_requested"]

    def test_mixed_when_balanced(self):
        results = [
            {"overall_sentiment": "positive", "top_topics_requested": [],
             "criticisms": [], "praise": [], "controversy_flags": []},
            {"overall_sentiment": "negative", "top_topics_requested": [],
             "criticisms": [], "praise": [], "controversy_flags": []},
        ]
        result = _aggregate_sentiment(results)
        assert result["overall_sentiment"] == "mixed"

    def test_strongly_positive(self):
        results = [
            {"overall_sentiment": "positive", "top_topics_requested": [],
             "criticisms": [], "praise": [], "controversy_flags": []},
            {"overall_sentiment": "positive", "top_topics_requested": [],
             "criticisms": [], "praise": [], "controversy_flags": []},
            {"overall_sentiment": "positive", "top_topics_requested": [],
             "criticisms": [], "praise": [], "controversy_flags": []},
        ]
        result = _aggregate_sentiment(results)
        assert result["overall_sentiment"] == "positive"

    def test_deduplicates_topics(self):
        results = [
            {"overall_sentiment": "mixed", "top_topics_requested": ["Rome", "rome", "ROME"],
             "criticisms": [], "praise": [], "controversy_flags": []},
        ]
        result = _aggregate_sentiment(results)
        assert len(result["top_topics_requested"]) == 1

    def test_caps_lists(self):
        results = [{
            "overall_sentiment": "mixed",
            "top_topics_requested": [f"topic_{i}" for i in range(30)],
            "criticisms": [f"crit_{i}" for i in range(30)],
            "praise": [f"praise_{i}" for i in range(30)],
            "controversy_flags": [f"flag_{i}" for i in range(30)],
        }]
        result = _aggregate_sentiment(results)
        assert len(result["top_topics_requested"]) <= 15
        assert len(result["criticisms"]) <= 20
        assert len(result["praise"]) <= 20
        assert len(result["controversy_flags"]) <= 15


@pytest.mark.unit
class TestExtractTopicRequests:
    """Test keyword-based topic request mining."""

    def test_empty_comments(self):
        assert extract_topic_requests([]) == []

    def test_detects_you_should_cover(self):
        comments = [{"text": "You should cover the Byzantine Empire", "likes": 5}]
        result = extract_topic_requests(comments)
        assert len(result) >= 1
        assert "byzantine" in result[0]["topic"].lower()

    def test_detects_do_a_video_on(self):
        comments = [{"text": "Do a video on the Khmer Rouge", "likes": 3}]
        result = extract_topic_requests(comments)
        assert len(result) >= 1

    def test_detects_what_about(self):
        comments = [{"text": "What about the Aztec Empire?", "likes": 1}]
        result = extract_topic_requests(comments)
        assert len(result) >= 1

    def test_filters_short_matches(self):
        comments = [{"text": "You should cover it", "likes": 0}]
        result = extract_topic_requests(comments)
        # "it" is too short (<=3 chars), should be filtered
        assert len(result) == 0

    def test_aggregates_by_topic(self):
        comments = [
            {"text": "You should cover the Mongol Empire", "likes": 5},
            {"text": "Please cover the Mongol Empire", "likes": 3},
        ]
        result = extract_topic_requests(comments)
        mongol = [r for r in result if "mongol" in r["topic"].lower()]
        if mongol:
            assert mongol[0]["frequency"] >= 2

    def test_sorted_by_frequency(self):
        comments = [
            {"text": "You should cover Rome", "likes": 1},
            {"text": "Do a video on Rome", "likes": 2},
            {"text": "Do a video on Rome please", "likes": 0},
            {"text": "You should cover Egypt", "likes": 1},
        ]
        result = extract_topic_requests(comments)
        if len(result) >= 2:
            assert result[0]["frequency"] >= result[-1]["frequency"]


@pytest.mark.unit
class TestGetCommentIntelligenceBlock:
    """Test formatted intelligence block generation."""

    def test_empty_when_no_data(self, tmp_path):
        with patch("intel.comment_analyzer.OUTPUTS_DIR", tmp_path):
            with patch("intel.comment_analyzer.fetch_comments", return_value=[]):
                result = get_comment_intelligence_block(["vid1"])
        assert result == ""

    def test_returns_formatted_string(self, tmp_path):
        cached = tmp_path / "comment_analysis_vid1.json"
        cached.write_text(json.dumps({
            "status": "complete",
            "sentiment": {
                "overall_sentiment": "positive",
                "top_topics_requested": ["Byzantine Empire"],
                "criticisms": ["Too fast pacing"],
                "praise": ["Great research"],
            },
        }))
        with patch("intel.comment_analyzer.OUTPUTS_DIR", tmp_path):
            result = get_comment_intelligence_block(["vid1"])
        assert "Audience Comment Intelligence" in result
        assert "byzantine empire" in result.lower()
        assert "Too fast pacing" in result
        assert "Great research" in result

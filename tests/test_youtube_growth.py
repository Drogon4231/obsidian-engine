"""Tests for intel/youtube_growth.py — community engagement and scheduling."""
import pytest
from datetime import datetime

from intel.youtube_growth import (
    get_optimal_publish_time,
    add_seasonal_boost,
    generate_pinned_comment,
)


@pytest.mark.unit
class TestGetOptimalPublishTime:
    """Test publish time calculation."""

    def test_returns_iso_string(self):
        result = get_optimal_publish_time({})
        assert result.endswith("Z")
        # Should parse as valid datetime
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")

    def test_default_is_tuesday_17utc(self):
        result = get_optimal_publish_time({})
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.weekday() == 1  # Tuesday
        assert dt.hour == 17

    def test_respects_insights_day(self):
        insights = {"channel_health": {"best_publish_day": "friday", "best_publish_hour": 14}}
        result = get_optimal_publish_time(insights)
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.weekday() == 4  # Friday
        assert dt.hour == 14

    def test_clamps_invalid_hour(self):
        insights = {"channel_health": {"best_publish_day": "monday", "best_publish_hour": 99}}
        result = get_optimal_publish_time(insights)
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.hour == 23  # clamped to max

    def test_handles_invalid_day_gracefully(self):
        insights = {"channel_health": {"best_publish_day": "notaday"}}
        result = get_optimal_publish_time(insights)
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.weekday() == 1  # Falls back to Tuesday

    def test_empty_insights_uses_defaults(self):
        result = get_optimal_publish_time({})
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.weekday() == 1
        assert dt.hour == 17


@pytest.mark.unit
class TestAddSeasonalBoost:
    """Test seasonal topic score boosting."""

    def test_october_dark_history_boost(self):
        topics = [{"topic": "Medieval Torture Methods", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-10-15")
        assert result[0]["score"] > 0.5
        assert any("seasonal_boost" in adj for adj in result[0].get("adjustments", []))

    def test_march_roman_history_boost(self):
        topics = [{"topic": "The Roman Senate's Downfall", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-03-15")
        assert result[0]["score"] > 0.5

    def test_june_war_history_boost(self):
        topics = [{"topic": "The Battle of Normandy", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-06-06")
        assert result[0]["score"] > 0.5

    def test_november_colonial_boost(self):
        topics = [{"topic": "Colonial Rebellion in India", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-11-15")
        assert result[0]["score"] > 0.5

    def test_december_religious_boost(self):
        topics = [{"topic": "The Crusades and the Holy Land", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-12-25")
        assert result[0]["score"] > 0.5

    def test_no_boost_for_irrelevant_topic(self):
        topics = [{"topic": "Ancient Mathematics", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-10-15")
        assert result[0]["score"] == 0.5

    def test_score_capped_at_1(self):
        topics = [{"topic": "Dark Torture Execution Ritual", "score": 0.95}]
        result = add_seasonal_boost(topics, "2026-10-15")
        assert result[0]["score"] <= 1.0

    def test_handles_invalid_date(self):
        topics = [{"topic": "Test", "score": 0.5}]
        result = add_seasonal_boost(topics, "not-a-date")
        assert result[0]["score"] == 0.5

    def test_era_field_included_in_matching(self):
        topics = [{"topic": "The Conquest", "era": "colonial", "score": 0.5}]
        result = add_seasonal_boost(topics, "2026-11-15")
        assert result[0]["score"] > 0.5


@pytest.mark.unit
class TestGeneratePinnedComment:
    """Test pinned comment text generation."""

    def test_basic_structure(self):
        result = generate_pinned_comment(seo_data={}, verification_data={})
        assert "SOURCES" in result
        assert "Subscribe" in result
        assert "topic should we cover" in result
        assert "Obsidian Archive" in result

    def test_includes_sources(self):
        verification = {"source_list_for_description": ["Source A", "Source B"]}
        result = generate_pinned_comment(seo_data={}, verification_data=verification)
        assert "Source A" in result
        assert "Source B" in result

    def test_seo_sources_fallback(self):
        seo = {"sources": ["SEO Source 1"]}
        result = generate_pinned_comment(seo_data=seo, verification_data={})
        assert "SEO Source 1" in result

    def test_caps_at_10_sources(self):
        verification = {"source_list_for_description": [f"Source {i}" for i in range(20)]}
        result = generate_pinned_comment(seo_data={}, verification_data=verification)
        assert result.count("Source ") <= 10

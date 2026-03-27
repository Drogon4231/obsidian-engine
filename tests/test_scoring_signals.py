"""Tests for scoring signal functions in 00_topic_discovery.py."""
import sys
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock


sys.path.insert(0, str(Path(__file__).parent.parent))

# Import module with numeric prefix using importlib
_mod_spec = importlib.util.spec_from_file_location(
    "topic_discovery",
    str(Path(__file__).parent.parent / "agents" / "00_topic_discovery.py"),
    submodule_search_locations=[],
)
td = importlib.util.module_from_spec(_mod_spec)

# Patch heavy imports before executing the module
with patch.dict("sys.modules", {
    "clients.claude_client": MagicMock(),
    "clients.supabase_client": MagicMock(),
    "intel.dna_loader": MagicMock(),
    "intel.channel_insights": MagicMock(),
}):
    _mod_spec.loader.exec_module(td)


# ══════════════════════════════════════════════════════════════════════════════
# 1. _get_subscriber_conversion_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestSubscriberConversionBoost:
    def test_empty_insights(self):
        val, reason = td._get_subscriber_conversion_boost("Mughal Poison Plot", "medieval", {})
        assert val == 0.0
        assert reason == ""

    def test_missing_era_performance(self):
        val, reason = td._get_subscriber_conversion_boost("topic", "ancient", {"unrelated": 1})
        assert val == 0.0
        assert reason == ""

    def test_returns_boost_for_high_conversion_era(self):
        insights = {
            "era_performance": {
                "medieval": {"avg_views": 5000, "video_count": 3},
                "ancient": {"avg_views": 500, "video_count": 2},
            },
            "shorts_intelligence": {
                "era_performance": {
                    "medieval": {"sub_conversion_rate": 0.50, "short_count": 2},
                    "ancient": {"sub_conversion_rate": 0.01, "short_count": 1},
                }
            },
        }
        val, reason = td._get_subscriber_conversion_boost("Mughal Poison Plot", "medieval", insights)
        assert val > 0.0
        assert isinstance(reason, str) and len(reason) > 0

    def test_returns_tuple(self):
        insights = {
            "era_performance": {
                "colonial": {"avg_views": 1000, "video_count": 2},
            },
        }
        result = td._get_subscriber_conversion_boost("British Raj", "colonial", insights)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_value_within_expected_range(self):
        insights = {
            "era_performance": {
                "ancient": {"avg_views": 8000, "video_count": 5},
                "modern": {"avg_views": 200, "video_count": 1},
            },
            "shorts_intelligence": {
                "era_performance": {
                    "ancient": {"sub_conversion_rate": 0.1, "short_count": 3},
                }
            },
        }
        val, _ = td._get_subscriber_conversion_boost("Ancient Rome secret", "ancient", insights)
        assert 0.0 <= val <= 0.15


# ══════════════════════════════════════════════════════════════════════════════
# 2. _get_engagement_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestEngagementBoost:
    def test_empty_insights(self):
        val, reason = td._get_engagement_boost("topic", "medieval", {})
        assert val == 0.0
        assert reason == ""

    def test_missing_era_performance(self):
        val, reason = td._get_engagement_boost("topic", "ancient", {"other_key": True})
        assert val == 0.0
        assert reason == ""

    def test_boost_for_high_retention_era(self):
        insights = {
            "era_performance": {
                "medieval": {"avg_retention": 60, "video_count": 3},
                "ancient": {"avg_retention": 30, "video_count": 2},
            },
        }
        val, reason = td._get_engagement_boost("Medieval Wars", "medieval", insights)
        assert val > 0.0
        assert "retention" in reason.lower() or "engagement" in reason.lower()

    def test_no_boost_for_low_retention_era(self):
        insights = {
            "era_performance": {
                "medieval": {"avg_retention": 30, "video_count": 3},
                "ancient": {"avg_retention": 60, "video_count": 2},
            },
        }
        val, reason = td._get_engagement_boost("Medieval topic", "medieval", insights)
        assert val == 0.0

    def test_value_range(self):
        insights = {
            "era_performance": {
                "colonial": {"avg_retention": 80, "video_count": 5},
                "modern": {"avg_retention": 20, "video_count": 1},
            },
        }
        val, _ = td._get_engagement_boost("Colonial story", "colonial", insights)
        assert 0.0 <= val <= 0.10


# ══════════════════════════════════════════════════════════════════════════════
# 3. _get_search_demand_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchDemandBoost:
    def test_empty_insights(self):
        val, reason = td._get_search_demand_boost("Some topic", {})
        assert val == 0.0
        assert reason == ""

    def test_no_matching_terms(self):
        insights = {
            "search_intelligence": {
                "top_search_terms": ["mughal empire", "roman history"],
            },
        }
        val, reason = td._get_search_demand_boost("Viking Raids", insights)
        assert val == 0.0

    def test_boost_with_matching_search_terms(self):
        insights = {
            "search_intelligence": {
                "top_search_terms": ["mughal empire", "poison plots"],
            },
        }
        val, reason = td._get_search_demand_boost("The Mughal Poison Conspiracy", insights)
        assert val > 0.0
        assert "search" in reason.lower()

    def test_boost_uses_tag_performance(self):
        insights = {
            "traffic_sources": {},
            "tag_performance": {
                "high_performing_tags": ["ancient rome", "conspiracy theory"],
            },
        }
        val, reason = td._get_search_demand_boost("Ancient Rome Conspiracy Uncovered", insights)
        assert val > 0.0

    def test_value_range(self):
        insights = {
            "search_intelligence": {
                "top_search_terms": ["dark history india", "secret empire"],
            },
        }
        val, _ = td._get_search_demand_boost("The Dark Secret Empire of India", insights)
        assert 0.0 <= val <= 0.15

    def test_dict_format_search_terms(self):
        """Producer writes top_search_terms as list of dicts with 'term' and 'views' keys."""
        insights = {
            "search_intelligence": {
                "top_search_terms": [
                    {"term": "mughal empire", "views": 5000},
                    {"term": "poison conspiracy", "views": 3000},
                ],
            },
        }
        val, reason = td._get_search_demand_boost("The Mughal Poison Conspiracy", insights)
        assert val > 0.0
        assert "search" in reason.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 4. _get_traffic_source_adjustment
# ══════════════════════════════════════════════════════════════════════════════

class TestTrafficSourceAdjustment:
    def test_empty_insights(self):
        val, reason = td._get_traffic_source_adjustment("Topic", "medieval", {})
        assert val == 0.0
        assert reason == ""

    def test_missing_traffic_sources(self):
        val, reason = td._get_traffic_source_adjustment("Topic", "medieval", {"other": 1})
        assert val == 0.0
        assert reason == ""

    def test_search_dominant_with_specific_topic(self):
        insights = {
            "traffic_sources": {
                "search": {"pct": 60},
                "browse": {"pct": 20},
                "suggested": {"pct": 20},
            },
        }
        # Topic with proper noun + date = 2 specificity signals
        val, reason = td._get_traffic_source_adjustment(
            "Who Killed Emperor Nero in 68 AD", "ancient", insights
        )
        assert val > 0.0
        assert "search" in reason.lower()

    def test_browse_dominant_with_clickworthy_topic(self):
        insights = {
            "traffic_sources": {
                "search": {"pct": 10},
                "browse": {"pct": 60},
                "suggested": {"pct": 30},
            },
        }
        val, reason = td._get_traffic_source_adjustment(
            "The Dark Secret Conspiracy of Hidden Murders", "medieval", insights
        )
        assert val > 0.0
        assert "browse" in reason.lower() or "click" in reason.lower()

    def test_no_dominant_source(self):
        insights = {
            "traffic_sources": {
                "search": {"pct": 30},
                "browse": {"pct": 35},
                "suggested": {"pct": 35},
            },
        }
        val, reason = td._get_traffic_source_adjustment("Some Topic", "medieval", insights)
        assert val == 0.0

    def test_value_range(self):
        insights = {
            "traffic_sources": {
                "search": {"pct": 70},
                "browse": {"pct": 15},
                "suggested": {"pct": 15},
            },
        }
        val, _ = td._get_traffic_source_adjustment(
            "Who Was Ashoka 300 BC", "ancient", insights
        )
        assert 0.0 <= val <= 0.10


# ══════════════════════════════════════════════════════════════════════════════
# 5. _get_content_pattern_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestContentPatternBoost:
    def test_empty_insights(self):
        val, reason = td._get_content_pattern_boost("Some Topic", {})
        assert val == 0.0
        assert reason == ""

    def test_no_patterns_no_top_videos(self):
        insights = {"top_performing_videos": []}
        val, reason = td._get_content_pattern_boost("Some Topic", insights)
        assert val == 0.0

    def test_explicit_pattern_match(self):
        insights = {
            "top_performing_videos": [
                {"title": "The Secret Hidden Temple"},
                {"title": "Dark Deadly Curse of Egypt"},
            ],
        }
        val, reason = td._get_content_pattern_boost(
            "The Hidden Secret of the Pharaohs", insights
        )
        assert val > 0.0
        assert "pattern" in reason.lower()

    def test_inferred_pattern_from_top_videos(self):
        insights = {
            "top_performing_videos": [
                {"title": "The Secret Hidden Temple"},
                {"title": "Dark Deadly Curse of Egypt"},
            ],
        }
        # "dark" matches dark_theme which was inferred from top videos
        val, reason = td._get_content_pattern_boost(
            "The Dark Truth About Cleopatra", insights
        )
        assert val > 0.0

    def test_no_matching_pattern(self):
        insights = {
            "top_performing_videos": [
                {"title": "Rome vs Greece Comparison"},
            ],
        }
        # comparison pattern inferred, but topic has no comparison keywords
        val, reason = td._get_content_pattern_boost("Mughal Empire History", insights)
        assert val == 0.0

    def test_value_range(self):
        insights = {
            "top_performing_videos": [
                {"title": "The Secret Hidden Temple"},
            ],
        }
        val, _ = td._get_content_pattern_boost("The Secret Mystery of Rome", insights)
        assert 0.0 <= val <= 0.10


# ══════════════════════════════════════════════════════════════════════════════
# 6. _get_demographic_alignment_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestDemographicAlignmentBoost:
    def test_empty_insights(self):
        val, reason = td._get_demographic_alignment_boost("Topic", {})
        assert val == 0.0
        assert reason == ""

    def test_missing_demographics(self):
        val, reason = td._get_demographic_alignment_boost("Topic", {"audience_demographics": {}})
        assert val == 0.0
        assert reason == ""

    def test_boost_for_india_audience_with_india_topic(self):
        insights = {
            "audience_demographics": {
                "top_countries": [
                    {"country": "IN", "pct": 65.0},
                    {"country": "US", "pct": 20.0},
                ],
            },
        }
        val, reason = td._get_demographic_alignment_boost(
            "The Mughal Empire's Darkest Secret", insights
        )
        assert val > 0.0
        assert "IN" in reason

    def test_no_boost_for_unrelated_topic(self):
        insights = {
            "audience_demographics": {
                "top_countries": [
                    {"country": "IN", "pct": 60.0},
                ],
            },
        }
        val, reason = td._get_demographic_alignment_boost(
            "Viking Raids in Scandinavia", insights
        )
        assert val == 0.0

    def test_skip_low_percentage_countries(self):
        insights = {
            "audience_demographics": {
                "top_countries": [
                    {"country": "IN", "pct": 10.0},
                ],
            },
        }
        # IN is below 20% threshold, so no boost even for India topic
        val, reason = td._get_demographic_alignment_boost(
            "Mughal Empire Secrets", insights
        )
        assert val == 0.0

    def test_value_range(self):
        insights = {
            "audience_demographics": {
                "top_countries": [
                    {"country": "US", "pct": 50.0},
                    {"country": "GB", "pct": 30.0},
                ],
            },
        }
        val, _ = td._get_demographic_alignment_boost(
            "The British Empire's Hidden Wars", insights
        )
        assert 0.0 <= val <= 0.05


# ══════════════════════════════════════════════════════════════════════════════
# 7. Threshold config integration — verify _th() reads SCORING_THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

class TestThresholdConfigIntegration:
    """Verify that signal functions respect SCORING_THRESHOLDS overrides."""

    def test_demographic_min_pct_override(self):
        """Lowering demographic_min_audience_pct should let smaller segments trigger."""
        insights = {
            "audience_demographics": {
                "top_countries": [{"country": "IN", "pct": 12.0}],
            },
        }
        # Default threshold is 20 — 12% should NOT trigger
        val_default, _ = td._get_demographic_alignment_boost("Mughal Empire", insights)
        assert val_default == 0.0

        # Override threshold to 10 — 12% should now trigger
        old = td.SCORING_THRESHOLDS.copy()
        td.SCORING_THRESHOLDS["demographic_min_audience_pct"] = 10
        try:
            val_override, reason = td._get_demographic_alignment_boost("Mughal Empire", insights)
            assert val_override > 0.0
            assert "IN" in reason
        finally:
            td.SCORING_THRESHOLDS.clear()
            td.SCORING_THRESHOLDS.update(old)

    def test_search_demand_min_matches_override(self):
        """Lowering search_demand_min_matches to 1 should trigger on single match."""
        insights = {
            "search_intelligence": {
                "top_search_terms": ["mughal empire"],
            },
        }
        # Default needs 2 matches — "Mughal Secrets" only matches "mughal"
        val_default, _ = td._get_search_demand_boost("Mughal Secrets", insights)
        assert val_default == 0.0

        old = td.SCORING_THRESHOLDS.copy()
        td.SCORING_THRESHOLDS["search_demand_min_matches"] = 1
        try:
            val_override, _ = td._get_search_demand_boost("Mughal Secrets", insights)
            assert val_override > 0.0
        finally:
            td.SCORING_THRESHOLDS.clear()
            td.SCORING_THRESHOLDS.update(old)

    def test_quality_multiplier_range_override(self):
        """Wider quality range should allow more extreme scores."""
        # A topic with many positives should hit the cap
        topic = "Who Killed Emperor Nero vs Caesar — The Dark Secret Conspiracy of 68 AD"
        val_default, _ = td._score_topic_quality(topic)
        assert val_default <= 1.2  # default cap

        old = td.SCORING_THRESHOLDS.copy()
        td.SCORING_THRESHOLDS["quality_multiplier_max"] = 1.5
        try:
            val_wider, _ = td._score_topic_quality(topic)
            assert val_wider >= val_default
        finally:
            td.SCORING_THRESHOLDS.clear()
            td.SCORING_THRESHOLDS.update(old)

    def test_traffic_dominant_pct_override(self):
        """Lowering search dominant threshold should trigger on lower search %."""
        insights = {
            "traffic_sources": {
                "search": {"pct": 35},
                "browse": {"pct": 35},
                "suggested": {"pct": 30},
            },
        }
        # Default needs >50% search — 35% should NOT trigger
        val_default, _ = td._get_traffic_source_adjustment(
            "Who Killed Emperor Nero in 68 AD", "ancient", insights
        )
        assert val_default == 0.0

        old = td.SCORING_THRESHOLDS.copy()
        td.SCORING_THRESHOLDS["traffic_search_dominant_pct"] = 30
        try:
            val_override, reason = td._get_traffic_source_adjustment(
                "Who Killed Emperor Nero in 68 AD", "ancient", insights
            )
            assert val_override > 0.0
            assert "search" in reason.lower()
        finally:
            td.SCORING_THRESHOLDS.clear()
            td.SCORING_THRESHOLDS.update(old)

    def test_sub_conversion_high_multiplier_override(self):
        """Lowering high_multiplier makes it easier to trigger 'high' tier."""
        insights = {
            "era_performance": {
                "medieval": {"avg_views": 5000, "video_count": 3},
                "ancient": {"avg_views": 4000, "video_count": 2},
            },
        }
        # With 1.5x multiplier, medieval (5000) vs avg (4500) is only 1.11x — not "high"
        val_default, _ = td._get_subscriber_conversion_boost("Knights", "medieval", insights)

        old = td.SCORING_THRESHOLDS.copy()
        td.SCORING_THRESHOLDS["sub_conversion_high_multiplier"] = 1.05
        try:
            val_low, reason = td._get_subscriber_conversion_boost("Knights", "medieval", insights)
            assert val_low >= val_default
        finally:
            td.SCORING_THRESHOLDS.clear()
            td.SCORING_THRESHOLDS.update(old)

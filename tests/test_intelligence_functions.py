"""Tests for untested intelligence functions in channel_insights.py and 00_topic_discovery.py."""
import sys
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from intel import channel_insights

# ── Import 00_topic_discovery safely (mock heavy deps before exec) ───────────

_mod_spec = importlib.util.spec_from_file_location(
    "topic_discovery",
    str(Path(__file__).parent.parent / "agents" / "00_topic_discovery.py"),
    submodule_search_locations=[],
)
_topic_discovery = importlib.util.module_from_spec(_mod_spec)

with patch.dict("sys.modules", {
    "clients.claude_client": MagicMock(),
    "clients.supabase_client": MagicMock(),
    "intel.dna_loader": MagicMock(),
}):
    _mod_spec.loader.exec_module(_topic_discovery)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _base_insights(**overrides):
    """Minimal insights dict that passes confidence checks."""
    base = {
        "data_quality": {"confidence_level": "sufficient", "videos_analyzed": 20},
    }
    base.update(overrides)
    return base


# ── 1. get_traffic_intelligence ──────────────────────────────────────────────

class TestGetTrafficIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_traffic_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_traffic_mix_with_valid_data(self, mock_load):
        mock_load.return_value = _base_insights(
            traffic_sources={
                "browse": {"views": 5000, "watch_min": 1200, "pct": 45.0},
                "search": {"views": 3000, "watch_min": 800, "pct": 25.0},
                "suggested": {"views": 2500, "watch_min": 600, "pct": 20.0},
                "external": {"views": 1000, "watch_min": 200, "pct": 10.0},
            },
            primary_source="browse",
        )
        result = channel_insights.get_traffic_intelligence()
        assert "TRAFFIC SOURCE INTELLIGENCE" in result
        assert "Browse 45%" in result
        assert "Search 25%" in result
        assert "Suggested 20%" in result
        assert "External 10%" in result
        assert "BROWSE-DRIVEN" in result

    @patch("intel.channel_insights.load_insights")
    def test_search_dependent_classification(self, mock_load):
        mock_load.return_value = _base_insights(
            traffic_sources={
                "browse": {"views": 1000, "watch_min": 200, "pct": 15.0},
                "search": {"views": 5000, "watch_min": 1200, "pct": 55.0},
                "suggested": {"views": 500, "watch_min": 100, "pct": 10.0},
                "external": {"views": 2000, "watch_min": 400, "pct": 20.0},
            },
        )
        result = channel_insights.get_traffic_intelligence()
        assert "SEARCH-DEPENDENT" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            traffic_sources={
                "browse": {},
                "search": {"pct": 30.0},
            },
        )
        result = channel_insights.get_traffic_intelligence()
        assert "TRAFFIC SOURCE INTELLIGENCE" in result
        # Should not crash — missing pct defaults to 0
        assert "Browse 0%" in result


# ── 2. get_retention_intelligence ────────────────────────────────────────────

class TestGetRetentionIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_retention_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_retention_data(self, mock_load):
        mock_load.return_value = _base_insights(
            retention_analysis={
                "optimal_length_minutes": 12,
                "retention_note": "Shorter videos retain better",
                "retention_verdict": "shorter_wins",
                "retention_by_length_band": {
                    "under_8min": {"avg_retention": 55, "sample_count": 3, "avg_views": 4000},
                    "8_to_12min": {"avg_retention": 48, "sample_count": 5, "avg_views": 6000},
                },
            },
            retention_curves={
                "avg_hook_retention_30s": 78.0,
                "avg_midpoint_retention": 45.0,
                "avg_end_retention": 30.0,
            },
        )
        result = channel_insights.get_retention_intelligence()
        assert "RETENTION INTELLIGENCE" in result
        assert "Optimal length: 12 minutes" in result
        assert "Hook retention (30s): 78%" in result
        assert "Midpoint retention: 45%" in result
        assert "End retention: 30%" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            retention_analysis={"optimal_length_minutes": 10},
            # retention_curves missing entirely
        )
        result = channel_insights.get_retention_intelligence()
        assert "RETENTION INTELLIGENCE" in result
        assert "Optimal length: 10 minutes" in result


# ── 3. get_engagement_intelligence ───────────────────────────────────────────

class TestGetEngagementIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_engagement_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_engagement_data(self, mock_load):
        mock_load.return_value = _base_insights(
            engagement_metrics={
                "avg_engagement_rate": 5.42,
                "avg_like_ratio": 4.10,
                "total_likes": 12000,
                "total_comments": 850,
                "total_shares": 320,
                "sample_count": 20,
            },
        )
        result = channel_insights.get_engagement_intelligence()
        assert "ENGAGEMENT INTELLIGENCE" in result
        assert "5.42%" in result
        assert "4.10%" in result
        assert "12,000 likes" in result
        assert "850 comments" in result
        assert "320 shares" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            engagement_metrics={
                "avg_engagement_rate": 3.0,
                # no like_ratio, no totals
            },
        )
        result = channel_insights.get_engagement_intelligence()
        assert "ENGAGEMENT INTELLIGENCE" in result
        assert "3.00%" in result


# ── 4. get_search_intelligence ───────────────────────────────────────────────

class TestGetSearchIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_search_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_search_terms(self, mock_load):
        mock_load.return_value = _base_insights(
            search_intelligence={
                "top_search_terms": [
                    {"term": "ancient rome secrets", "views": 5000},
                    {"term": "dark history india", "views": 3200},
                    {"term": "medieval poison", "views": 1800},
                ],
            },
        )
        result = channel_insights.get_search_intelligence()
        assert "SEARCH INTELLIGENCE" in result
        assert "ancient rome secrets" in result
        assert "5,000 views" in result
        assert "dark history india" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            search_intelligence={"some_other_key": True},
        )
        result = channel_insights.get_search_intelligence()
        # Has search_intelligence but no top_search_terms — returns header only
        assert "SEARCH INTELLIGENCE" in result

    @patch("intel.channel_insights.load_insights")
    def test_empty_search_intelligence_dict(self, mock_load):
        mock_load.return_value = _base_insights(search_intelligence={})
        assert channel_insights.get_search_intelligence() == ""


# ── 5. get_first_48h_intelligence ────────────────────────────────────────────

class TestGetFirst48hIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_first_48h_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_benchmark_data(self, mock_load):
        mock_load.return_value = _base_insights(
            first_48h_benchmarks={
                "avg_velocity": 1250.75,
                "sample_count": 18,
                "best_performer": {"title": "The Secret Poison Ring of Ancient Rome", "velocity": 3200.50},
                "worst_performer": {"title": "General History Overview Part 1", "velocity": 120.30},
            },
        )
        result = channel_insights.get_first_48h_intelligence()
        assert "FIRST 48H PERFORMANCE INTELLIGENCE" in result
        assert "1250.75" in result
        assert "18 videos" in result
        assert "Secret Poison Ring" in result
        assert "3200.50" in result
        assert "General History Overview" in result
        assert "120.30" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            first_48h_benchmarks={
                "avg_velocity": 800.0,
                # no sample_count, no best/worst
            },
        )
        result = channel_insights.get_first_48h_intelligence()
        assert "FIRST 48H PERFORMANCE INTELLIGENCE" in result
        assert "800.00" in result


# ── 6. get_endscreen_intelligence ────────────────────────────────────────────

class TestGetEndscreenIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_endscreen_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_endscreen_data(self, mock_load):
        mock_load.return_value = _base_insights(
            endscreen_performance={
                "avg_card_ctr": 2.35,
                "avg_endscreen_ctr": 1.80,
                "videos_with_cards": 12,
                "videos_with_endscreens": 15,
            },
        )
        result = channel_insights.get_endscreen_intelligence()
        assert "ENDSCREEN INTELLIGENCE" in result
        assert "2.35%" in result
        assert "1.80%" in result
        assert "cards: 12" in result
        assert "endscreens: 15" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            endscreen_performance={
                "avg_card_ctr": 1.5,
                # no endscreen_ctr, no counts
            },
        )
        result = channel_insights.get_endscreen_intelligence()
        assert "ENDSCREEN INTELLIGENCE" in result
        assert "1.50%" in result


# ── 7. get_demographic_intelligence ──────────────────────────────────────────

class TestGetDemographicIntelligence:

    @patch("intel.channel_insights.load_insights", return_value={})
    def test_empty_when_no_data(self, mock_load):
        assert channel_insights.get_demographic_intelligence() == ""

    @patch("intel.channel_insights.load_insights")
    def test_returns_demographic_data(self, mock_load):
        mock_load.return_value = _base_insights(
            audience_demographics={
                "top_countries": [
                    {"country": "India", "pct": 62.5},
                    {"country": "United States", "pct": 15.0},
                    {"country": "United Kingdom", "pct": 8.0},
                ],
                "age_distribution": {
                    "18-24": 35.0,
                    "25-34": 40.0,
                    "35-44": 15.0,
                    "45-54": 10.0,
                },
                "gender_split": {
                    "male": 72.0,
                    "female": 28.0,
                },
            },
        )
        result = channel_insights.get_demographic_intelligence()
        assert "AUDIENCE DEMOGRAPHIC INTELLIGENCE" in result
        assert "India" in result
        assert "62.5%" in result
        assert "Indian audience" in result  # india_pct > 40 triggers hint
        assert "18-24" in result
        assert "male" in result.lower() or "Male" in result

    @patch("intel.channel_insights.load_insights")
    def test_handles_missing_sub_keys(self, mock_load):
        mock_load.return_value = _base_insights(
            audience_demographics={
                "top_countries": [{"country": "Germany", "pct": 30.0}],
                # no age_distribution, no gender_split
            },
        )
        result = channel_insights.get_demographic_intelligence()
        assert "AUDIENCE DEMOGRAPHIC INTELLIGENCE" in result
        assert "Germany" in result

    @patch("intel.channel_insights.load_insights")
    def test_empty_demographics_dict(self, mock_load):
        mock_load.return_value = _base_insights(audience_demographics={})
        assert channel_insights.get_demographic_intelligence() == ""


# ── 8. _score_topic_quality (from 00_topic_discovery.py) ─────────────────────

class TestScoreTopicQuality:

    def test_specific_topic_with_names_and_emotion(self):
        multiplier, reason = _topic_discovery._score_topic_quality(
            "The Secret Poison Ring of Emperor Nero in 54 AD"
        )
        assert 0.8 <= multiplier <= 1.2
        assert multiplier > 1.0  # names + dates + emotional word
        assert "specific names" in reason

    def test_broad_short_topic_penalized(self):
        multiplier, reason = _topic_discovery._score_topic_quality(
            "History of War"
        )
        assert 0.8 <= multiplier <= 1.2
        assert multiplier < 1.0
        assert "too broad" in reason or "no named entities" in reason

    def test_comparison_format_boosted(self):
        multiplier, reason = _topic_discovery._score_topic_quality(
            "Genghis Khan vs Alexander the Great"
        )
        assert 0.8 <= multiplier <= 1.2
        assert "comparison format" in reason

    def test_very_short_topic_penalized(self):
        multiplier, reason = _topic_discovery._score_topic_quality("Rome")
        assert 0.8 <= multiplier <= 1.2
        assert multiplier <= 1.0
        assert "too short" in reason

    def test_neutral_topic(self):
        multiplier, reason = _topic_discovery._score_topic_quality(
            "The Ancient Temple Complex"
        )
        assert 0.8 <= multiplier <= 1.2

    def test_clamped_to_range(self):
        # Even an extreme topic stays within 0.8 to 1.2
        multiplier, _ = _topic_discovery._score_topic_quality("x")
        assert 0.8 <= multiplier <= 1.2
        multiplier2, _ = _topic_discovery._score_topic_quality(
            "The Secret Dark Conspiracy: Hidden Murder of Emperor Julius Caesar vs Brutus in 44 BC"
        )
        assert 0.8 <= multiplier2 <= 1.2


# ── 9. _get_dynamic_adjustments (from 00_topic_discovery.py) ─────────────────

class TestGetDynamicAdjustments:

    def test_early_tier(self):
        """video_count=3 -> EARLY adjustments."""
        adj = _topic_discovery._get_dynamic_adjustments(3)
        assert isinstance(adj, dict)
        assert "era_fatigue" in adj
        assert adj["era_fatigue"] == -0.15
        assert adj["audience_request"] == 0.20

    def test_growing_tier(self):
        """video_count=10 -> GROWING adjustments."""
        adj = _topic_discovery._get_dynamic_adjustments(10)
        assert isinstance(adj, dict)
        assert adj["era_fatigue"] == -0.20
        assert adj["audience_request"] == 0.15

    def test_mature_tier(self):
        """video_count=20 -> MATURE adjustments (>= threshold 15)."""
        adj = _topic_discovery._get_dynamic_adjustments(20)
        assert isinstance(adj, dict)
        assert adj["era_fatigue"] == -0.25
        assert adj["audience_request"] == 0.12

    def test_returns_copy_not_original(self):
        """Ensure we get a copy so mutations don't affect the original."""
        adj1 = _topic_discovery._get_dynamic_adjustments(3)
        adj1["era_fatigue"] = 999
        adj2 = _topic_discovery._get_dynamic_adjustments(3)
        assert adj2["era_fatigue"] == -0.15

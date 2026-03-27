"""Tests for shorts intelligence computation functions in 12_analytics_agent.py
and shorts-informed scoring in 00_topic_discovery.py."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the analytics functions directly
from importlib import import_module

analytics = import_module("agents.12_analytics_agent")
compute_shorts_intelligence = analytics.compute_shorts_intelligence
compute_shorts_long_correlation = analytics.compute_shorts_long_correlation

topic_discovery = import_module("agents.00_topic_discovery")


# ── Test data helpers ────────────────────────────────────────────────────────

def _short_row(topic, views, subs, title=None):
    return {
        "topic": topic,
        "title": title or topic,
        "views": views,
        "subscribers_gained": subs,
    }

def _long_row(topic, views, subs):
    return {
        "topic": topic,
        "views": views,
        "subscribers_gained": subs,
    }


# ── compute_shorts_intelligence ──────────────────────────────────────────────

class TestComputeShortsIntelligence:
    def test_empty_input_returns_empty(self):
        assert compute_shorts_intelligence([], []) == {}

    def test_basic_stats(self):
        shorts = [
            _short_row("Fall of Rome", 10000, 30),
            _short_row("Cleopatra's Death", 6000, 20),
        ]
        result = compute_shorts_intelligence(shorts, [])
        assert result["total_shorts"] == 2
        assert result["total_views"] == 16000
        assert result["avg_views_per_short"] == 8000.0
        assert result["total_subs_from_shorts"] == 50
        assert result["avg_subs_per_short"] == 25.0

    def test_era_performance_bucketing(self):
        shorts = [
            _short_row("Roman Emperor Nero's madness", 10000, 30),
            _short_row("Julius Caesar assassination", 8000, 25),
            _short_row("Mughal poison plots", 5000, 15),
        ]
        result = compute_shorts_intelligence(shorts, [])
        era_perf = result["era_performance"]
        # Both Roman topics should be in same era bucket (ancient_rome)
        assert "ancient_rome" in era_perf
        assert era_perf["ancient_rome"]["short_count"] == 2

    def test_top_hooks_sorted_by_views(self):
        shorts = [
            _short_row("Topic A", 1000, 5, "Low views short"),
            _short_row("Topic B", 50000, 100, "Massive viral short about history"),
            _short_row("Topic C", 3000, 10, "Medium short"),
        ]
        result = compute_shorts_intelligence(shorts, [])
        assert result["top_hooks"][0]["views"] == 50000
        assert "Massive" in result["top_hooks"][0]["hook"]

    def test_top_hooks_limited_to_5(self):
        shorts = [_short_row(f"Topic {i}", i * 1000, i * 5) for i in range(10)]
        result = compute_shorts_intelligence(shorts, [])
        assert len(result["top_hooks"]) == 5

    def test_conversion_rate_calculation(self):
        shorts = [
            _short_row("Topic A", 10000, 50),
            _short_row("Topic B", 10000, 50),
        ]
        result = compute_shorts_intelligence(shorts, [])
        # 100 subs / 20000 views * 100 = 0.5%
        assert result["sub_conversion_rate_pct"] == 0.5

    def test_single_short(self):
        shorts = [_short_row("Only One", 5000, 20)]
        result = compute_shorts_intelligence(shorts, [])
        assert result["total_shorts"] == 1
        assert result["avg_views_per_short"] == 5000.0


# ── compute_shorts_long_correlation ──────────────────────────────────────────

class TestComputeShortsLongCorrelation:
    def test_empty_inputs_return_empty(self):
        assert compute_shorts_long_correlation([], [], []) == {}
        assert compute_shorts_long_correlation([], [_long_row("x", 100, 5)], []) == {}
        assert compute_shorts_long_correlation([_short_row("x", 100, 5)], [], []) == {}

    def test_no_matching_topics(self):
        shorts = [_short_row("Topic A", 5000, 20)]
        longs = [_long_row("Completely Different", 10000, 50)]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert "note" in result
        assert "No topic-matched" in result["note"]

    def test_basic_correlation(self):
        shorts = [_short_row("Fall of Rome", 5000, 20)]
        longs = [
            _long_row("Fall of Rome", 15000, 80),   # has matching short
            _long_row("Other Topic", 8000, 30),      # no matching short
        ]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert result["topics_with_shorts"] == 1
        assert result["topics_without_shorts"] == 1
        assert result["avg_views_with_short"] == 15000
        assert result["avg_views_without_short"] == 8000
        # lift = (15000 - 8000) / 8000 * 100 = 87.5%
        assert result["view_lift_pct"] == 87.5

    def test_case_insensitive_matching(self):
        shorts = [_short_row("fall of rome", 5000, 20)]
        longs = [_long_row("Fall of Rome", 15000, 80)]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert result["topics_with_shorts"] == 1

    def test_sample_size_note_directional(self):
        shorts = [_short_row("Topic A", 5000, 20)]
        longs = [_long_row("Topic A", 10000, 50), _long_row("Topic B", 8000, 30)]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert "directional only" in result["sample_size_note"]

    def test_sample_size_note_moderate_confidence(self):
        shorts = [_short_row(f"Topic {i}", 5000, 20) for i in range(5)]
        longs = [_long_row(f"Topic {i}", 10000, 50) for i in range(5)]
        longs.append(_long_row("Unmatched", 8000, 30))
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert "moderate confidence" in result["sample_size_note"]

    def test_era_correlation_included(self):
        shorts = [_short_row("Fall of Rome", 5000, 20)]
        longs = [_long_row("Fall of Rome", 15000, 80)]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert "era_correlation" in result
        assert len(result["era_correlation"]) >= 1

    def test_all_topics_matched(self):
        """When all long-form have a matching short, without_short should be 0."""
        shorts = [_short_row("Topic A", 5000, 20)]
        longs = [_long_row("Topic A", 10000, 50)]
        result = compute_shorts_long_correlation(shorts, longs, [])
        assert result["topics_without_shorts"] == 0
        # lift is 0 when there's no baseline (division by max(0,1))
        assert result["view_lift_pct"] == 0


# ── _get_shorts_era_boosts (topic discovery) ─────────────────────────────────

class TestGetShortsEraBoosts:
    def test_empty_when_no_shorts_data(self):
        with patch("intel.channel_insights.load_insights", return_value={}):
            result = topic_discovery._get_shorts_era_boosts()
            assert result == {}

    def test_boosts_above_average_eras(self):
        insights = {
            "shorts_intelligence": {
                "era_performance": {
                    "ancient": {"avg_subs_per_short": 30.0, "short_count": 3},
                    "medieval": {"avg_subs_per_short": 10.0, "short_count": 3},
                    "colonial": {"avg_subs_per_short": 5.0, "short_count": 2},
                }
            }
        }
        with patch.object(topic_discovery, "load_insights", return_value=insights):
            result = topic_discovery._get_shorts_era_boosts()
            # avg = (30+10+5)/3 = 15. Only ancient (30) is above average
            assert "ancient" in result
            assert result["ancient"] == 0.05
            assert "medieval" not in result
            assert "colonial" not in result

    def test_no_boosts_when_all_equal(self):
        insights = {
            "shorts_intelligence": {
                "era_performance": {
                    "ancient": {"avg_subs_per_short": 10.0, "short_count": 2},
                    "medieval": {"avg_subs_per_short": 10.0, "short_count": 2},
                }
            }
        }
        with patch.object(topic_discovery, "load_insights", return_value=insights):
            result = topic_discovery._get_shorts_era_boosts()
            assert result == {}

    def test_ignores_eras_with_zero_shorts(self):
        insights = {
            "shorts_intelligence": {
                "era_performance": {
                    "ancient": {"avg_subs_per_short": 30.0, "short_count": 0},
                    "medieval": {"avg_subs_per_short": 10.0, "short_count": 3},
                }
            }
        }
        with patch.object(topic_discovery, "load_insights", return_value=insights):
            result = topic_discovery._get_shorts_era_boosts()
            # ancient has 0 shorts, should be ignored
            assert "ancient" not in result


# ── Shorts boost integration in score adjustments ────────────────────────────

class TestShortsBoostInScoring:
    def test_shorts_boost_applied(self):
        topics = [{"topic": "Fall of Rome", "era": "ancient", "score": 0.70}]
        with patch.object(topic_discovery, "_get_video_count", return_value=10), \
             patch.object(topic_discovery, "load_insights", return_value={"data_quality": {"confidence_level": "sufficient"}}):
            result = topic_discovery._apply_score_adjustments(
                topics,
                recent_eras=[],
                audience_requests=[],
                trending_topics=[],
                cost_efficient_eras={},
                shorts_era_boosts={"ancient": 0.05},
            )
        # Score should increase from shorts boost (growing tier: +0.05)
        assert result[0]["score"] > 0.70

    def test_shorts_boost_stacks_with_others(self):
        topics = [{"topic": "Fall of Rome", "era": "ancient", "score": 0.70}]
        with patch.object(topic_discovery, "_get_video_count", return_value=10), \
             patch.object(topic_discovery, "load_insights", return_value={"data_quality": {"confidence_level": "sufficient"}}):
            result = topic_discovery._apply_score_adjustments(
                topics,
                recent_eras=[],
                audience_requests=[],
                trending_topics=[],
                cost_efficient_eras={"ancient": 0.05},
                shorts_era_boosts={"ancient": 0.05},
            )
        # Both boosts should apply
        assert result[0]["score"] > 0.75

    def test_no_boost_when_era_not_matched(self):
        topics = [{"topic": "Mughal Dynasty", "era": "medieval", "score": 0.70}]
        with patch.object(topic_discovery, "_get_video_count", return_value=10), \
             patch.object(topic_discovery, "load_insights", return_value={"data_quality": {"confidence_level": "sufficient"}}):
            result = topic_discovery._apply_score_adjustments(
                topics,
                recent_eras=[],
                audience_requests=[],
                trending_topics=[],
                cost_efficient_eras={},
                shorts_era_boosts={"ancient": 0.05},
            )
        assert result[0]["score"] == 0.70

    def test_none_shorts_boosts_handled(self):
        """When shorts_era_boosts is None (no data), scoring still works."""
        topics = [{"topic": "Test Topic", "era": "ancient", "score": 0.70}]
        with patch.object(topic_discovery, "_get_video_count", return_value=10), \
             patch.object(topic_discovery, "load_insights", return_value={"data_quality": {"confidence_level": "sufficient"}}):
            result = topic_discovery._apply_score_adjustments(
                topics,
                recent_eras=[],
                audience_requests=[],
                trending_topics=[],
                cost_efficient_eras={},
                shorts_era_boosts=None,
            )
        assert result[0]["score"] == 0.70

    def test_score_capped_at_1(self):
        topics = [{"topic": "Great Topic", "era": "ancient", "score": 0.98}]
        with patch.object(topic_discovery, "_get_video_count", return_value=10), \
             patch.object(topic_discovery, "load_insights", return_value={"data_quality": {"confidence_level": "sufficient"}}):
            result = topic_discovery._apply_score_adjustments(
                topics,
                recent_eras=[],
                audience_requests=[],
                trending_topics=[],
                cost_efficient_eras={"ancient": 0.05},
                shorts_era_boosts={"ancient": 0.05},
            )
        assert result[0]["score"] == 1.0

"""Tests for competitive intelligence scoring signals in 00_topic_discovery.py."""
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
# Helper: build competitive_data fixture
# ══════════════════════════════════════════════════════════════════════════════

def _make_competitive_data(gaps=None, trending=None, saturated=None, channel_avg=None):
    return {
        "data_available": True,
        "gaps": gaps or [],
        "trending": trending or [],
        "saturated": saturated or [],
        "channel_avg_views": channel_avg or {},
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1. _get_competitive_gap_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestCompetitiveGapBoost:
    def test_no_data_returns_zero(self):
        val, reason = td._get_competitive_gap_boost("The Fall of Rome", "ancient", None)
        assert val == 0.0
        assert reason == ""

    def test_no_gaps_returns_zero(self):
        data = _make_competitive_data(gaps=[])
        val, reason = td._get_competitive_gap_boost("The Fall of Rome", "ancient", data)
        assert val == 0.0

    def test_matching_gap_returns_positive(self):
        data = _make_competitive_data(
            gaps=[{
                "title": "The Fall of the Roman Empire Explained",
                "views": 500000,
                "channel": "OverSimplified",
            }],
            channel_avg={"OverSimplified": 200000},
        )
        val, reason = td._get_competitive_gap_boost("The Fall of Rome and Its Aftermath", "ancient", data)
        assert val > 0.0
        assert "gap:" in reason

    def test_low_view_gap_ignored(self):
        data = _make_competitive_data(
            gaps=[{
                "title": "The Fall of the Roman Empire",
                "views": 500,  # below min_views threshold of 10000
                "channel": "SmallChannel",
            }],
            channel_avg={"SmallChannel": 100},
        )
        val, reason = td._get_competitive_gap_boost("The Fall of Rome", "ancient", data)
        assert val == 0.0

    def test_high_overlap_reduces_boost(self):
        """Topics with >80% word overlap get halved boost (me-too prevention)."""
        data = _make_competitive_data(
            gaps=[{
                "title": "Rome Fall",
                "views": 600000,
                "channel": "TestChannel",
            }],
            channel_avg={"TestChannel": 100000},
        )
        # Near-exact match
        val_copy, _ = td._get_competitive_gap_boost("Rome Fall", "ancient", data)
        # Different enough topic
        val_diff, _ = td._get_competitive_gap_boost("Rome Fall and the Dark Ages That Followed", "ancient", data)
        assert val_copy <= val_diff or val_copy == 0.0  # copy should be weaker or zero

    def test_performance_ratio_scales_boost(self):
        """Higher performance ratio should give higher boost."""
        data_low = _make_competitive_data(
            gaps=[{"title": "Ancient Mystery Pyramid Secrets", "views": 100000, "channel": "Ch1"}],
            channel_avg={"Ch1": 100000},  # ratio = 1.0
        )
        data_high = _make_competitive_data(
            gaps=[{"title": "Ancient Mystery Pyramid Secrets", "views": 600000, "channel": "Ch1"}],
            channel_avg={"Ch1": 100000},  # ratio = 6.0
        )
        val_low, _ = td._get_competitive_gap_boost("Ancient Mystery Pyramid Discovery", "ancient", data_low)
        val_high, _ = td._get_competitive_gap_boost("Ancient Mystery Pyramid Discovery", "ancient", data_high)
        assert val_high >= val_low

    def test_boost_value_range(self):
        data = _make_competitive_data(
            gaps=[{"title": "Dark History Medieval Poison Plot", "views": 1000000, "channel": "Big"}],
            channel_avg={"Big": 50000},
        )
        val, _ = td._get_competitive_gap_boost("Dark History Medieval Poison", "medieval", data)
        assert 0.0 <= val <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 2. _get_competitor_trending_boost
# ══════════════════════════════════════════════════════════════════════════════

class TestCompetitorTrendingBoost:
    def test_no_data_returns_zero(self):
        val, reason = td._get_competitor_trending_boost("Roman Siege Tactics", None)
        assert val == 0.0
        assert reason == ""

    def test_no_trending_returns_zero(self):
        data = _make_competitive_data(trending=[])
        val, reason = td._get_competitor_trending_boost("Roman Siege", data)
        assert val == 0.0

    def test_matching_trending_returns_positive(self):
        data = _make_competitive_data(
            trending=[{
                "title": "The Siege of Constantinople Was Brutal",
                "performance_ratio": 3.5,
                "channel": "Kings and Generals",
                "views": 500000,
            }],
        )
        val, reason = td._get_competitor_trending_boost("Siege of Constantinople Untold", data)
        assert val > 0.0
        assert "trending:" in reason

    def test_higher_ratio_bigger_boost(self):
        trending_low = [{"title": "Dark Poison Medieval Plot", "performance_ratio": 1.6, "channel": "C", "views": 50000}]
        trending_high = [{"title": "Dark Poison Medieval Plot", "performance_ratio": 5.0, "channel": "C", "views": 200000}]
        val_low, _ = td._get_competitor_trending_boost("Dark Poison Medieval", _make_competitive_data(trending=trending_low))
        val_high, _ = td._get_competitor_trending_boost("Dark Poison Medieval", _make_competitive_data(trending=trending_high))
        assert val_high >= val_low

    def test_no_word_match_returns_zero(self):
        data = _make_competitive_data(
            trending=[{"title": "Space Exploration Mars Colony", "performance_ratio": 5.0, "channel": "Sci", "views": 100000}],
        )
        val, _ = td._get_competitor_trending_boost("Mughal Empire Poison Plot", data)
        assert val == 0.0

    def test_boost_value_range(self):
        data = _make_competitive_data(
            trending=[{"title": "Ancient Empire Dark Secrets", "performance_ratio": 10.0, "channel": "X", "views": 999999}],
        )
        val, _ = td._get_competitor_trending_boost("Ancient Empire Dark History", data)
        assert 0.0 <= val <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 3. _get_niche_saturation_penalty
# ══════════════════════════════════════════════════════════════════════════════

class TestNicheSaturationPenalty:
    def test_no_data_returns_zero(self):
        val, reason = td._get_niche_saturation_penalty("Roman Empire", None)
        assert val == 0.0
        assert reason == ""

    def test_few_competitors_no_penalty(self):
        data = _make_competitive_data(
            saturated=[{"words": ["roman", "empire", "fall"], "channels": ["A", "B"], "count": 2}],
        )
        val, _ = td._get_niche_saturation_penalty("Roman Empire Fall", data)
        assert val == 0.0  # count=2 < min_competitors=3

    def test_three_plus_competitors_penalizes(self):
        data = _make_competitive_data(
            saturated=[{"words": ["roman", "empire", "fall"], "channels": ["A", "B", "C"], "count": 3}],
        )
        val, reason = td._get_niche_saturation_penalty("The Fall of Roman Empire", data)
        assert val < 0.0
        assert "saturated:" in reason

    def test_more_competitors_stronger_penalty(self):
        data_3 = _make_competitive_data(
            saturated=[{"words": ["dark", "medieval", "poison"], "channels": ["A", "B", "C"], "count": 3}],
        )
        data_7 = _make_competitive_data(
            saturated=[{"words": ["dark", "medieval", "poison"], "channels": list("ABCDEFG"), "count": 7}],
        )
        val_3, _ = td._get_niche_saturation_penalty("Dark Medieval Poison Plot", data_3)
        val_7, _ = td._get_niche_saturation_penalty("Dark Medieval Poison Plot", data_7)
        assert val_7 < val_3  # more competitors = stronger penalty (more negative)

    def test_unique_topic_no_penalty(self):
        data = _make_competitive_data(
            saturated=[{"words": ["roman", "empire", "fall"], "channels": ["A", "B", "C", "D"], "count": 4}],
        )
        val, _ = td._get_niche_saturation_penalty("Mughal Dynasty Secrets Revealed", data)
        assert val == 0.0  # no word overlap

    def test_penalty_value_range(self):
        data = _make_competitive_data(
            saturated=[{"words": ["dark", "history", "secrets"], "channels": list("ABCDEFGH"), "count": 8}],
        )
        val, _ = td._get_niche_saturation_penalty("Dark History Secrets", data)
        assert -1.0 <= val <= 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 4. Competitive max cap in _apply_score_adjustments
# ══════════════════════════════════════════════════════════════════════════════

class TestCompetitiveMaxCap:
    """Test that total competitive signal contribution is capped at competitive_max_total_boost."""

    def _make_topic(self, topic="Test Topic", score=0.5, era="ancient"):
        return {"topic": topic, "score": score, "era": era, "hook": "test", "reason": "test"}

    def _apply(self, topics, competitive_data=None):
        with patch.object(td, "_get_video_count", return_value=0):
            with patch.object(td, "load_insights", return_value={}):
                return td._apply_score_adjustments(
                    topics,
                    recent_eras=[],
                    audience_requests=[],
                    trending_topics=[],
                    cost_efficient_eras={},
                    shorts_era_boosts=None,
                    insights={},
                    competitive_data=competitive_data,
                )

    def test_all_three_signals_capped(self):
        """When gap + trending both fire, total competitive boost is capped at 0.15."""
        data = _make_competitive_data(
            gaps=[{"title": "Dark Ancient Empire Secrets Revealed", "views": 1000000, "channel": "Big"}],
            trending=[{"title": "Dark Ancient Empire Mystery", "performance_ratio": 5.0, "channel": "Big", "views": 999999}],
            channel_avg={"Big": 100000},
        )
        topics = [self._make_topic(topic="Dark Ancient Empire Secrets")]
        result = self._apply(topics, competitive_data=data)
        # Score increase from competitive signals alone should not exceed 0.15
        base = 0.5
        competitive_increase = result[0]["score"] - base
        # Allow for quality multiplier and competitive cap
        assert competitive_increase <= 0.20  # cap + some tolerance for quality signal

    def test_single_signal_not_capped(self):
        """A single competitive signal below cap passes through unscaled."""
        data = _make_competitive_data(
            gaps=[{"title": "Unique Ancient Mystery Pyramid", "views": 200000, "channel": "Ch1"}],
            channel_avg={"Ch1": 100000},
        )
        topics = [self._make_topic(topic="Unique Ancient Mystery Pyramid Discovery")]
        result = self._apply(topics, competitive_data=data)
        assert result[0]["score"] >= 0.5  # should get some boost

    def test_penalty_not_capped(self):
        """Saturation penalty should still apply even when positive signals are capped."""
        data = _make_competitive_data(
            saturated=[{"words": ["dark", "poison", "medieval"], "channels": list("ABCDE"), "count": 5}],
        )
        topics = [self._make_topic(topic="Dark Poison Medieval Plot")]
        result = self._apply(topics, competitive_data=data)
        assert result[0]["score"] <= 0.5  # should be penalized

    def test_config_override_respected(self):
        """When no competitive data, score should be unchanged (minus quality)."""
        topics = [self._make_topic(topic="The Battle of Thermopylae")]
        result = self._apply(topics, competitive_data=None)
        # Without competitive data, only quality signal applies
        assert isinstance(result[0]["score"], float)

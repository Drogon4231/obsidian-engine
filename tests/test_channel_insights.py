"""Tests for channel_insights.py — intelligence formatting for agent prompts."""
import sys
import json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from intel import channel_insights


def _make_insights(overrides=None, confidence="sufficient", n_videos=20):
    """Build a minimal valid insights dict."""
    base = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_quality": {"confidence_level": confidence, "videos_analyzed": n_videos},
        "per_video_stats": [{"title": f"Video {i}"} for i in range(n_videos)],
        "channel_health": {"avg_views_per_video": 5000, "avg_ctr_pct": 5.2},
        "era_performance": {
            "ancient_rome": {"avg_views": 8000, "avg_ctr": 6.1, "video_count": 3},
            "medieval": {"avg_views": 3000, "avg_ctr": 3.5, "video_count": 2},
        },
        "title_pattern_analysis": {
            "high_ctr_patterns": ["Numbers in title"],
            "low_ctr_patterns": ["Generic titles"],
            "avg_ctr_by_title_length": {"short_4_6_words": 6.2, "medium_7_9_words": 5.1},
            "best_opening_words": ["The", "How", "Why"],
        },
        "retention_analysis": {
            "optimal_length_minutes": 11,
            "retention_verdict": "shorter_wins",
            "retention_note": "Videos under 12 min retain better",
            "retention_by_length_band": {
                "under_8min": {"avg_retention": 55, "avg_views": 4000, "sample_count": 2},
                "8_to_12min": {"avg_retention": 48, "avg_views": 6000, "sample_count": 4},
                "over_16min": {"avg_retention": 32, "avg_views": 2000, "sample_count": 1},
            },
        },
        "agent_intelligence": {
            "topic_discovery": "Ancient Rome outperforms by 60%",
            "seo_agent": "Short titles get 20% higher CTR",
            "narrative_architect": "Keep under 12 minutes",
            "script_writer": "Open with a question for best hooks",
        },
        "dna_confidence_updates": {
            "open_mid_action_hook": 0.8,
            "twist_reveal_ending": 0.6,
            "ancient_medieval_priority": 0.75,
            "10_15_min_standard_length": 0.5,
            "present_tense_narration": 0.3,
            "dark_thumbnail_aesthetic": 0.35,
        },
        "top_performing_videos": [
            {"title": "Caesar's Assassination", "views": 12000, "ctr_pct": 7.2,
             "avg_retention_pct": 52},
            {"title": "Cleopatra's Secret", "views": 9000, "ctr_pct": 6.5,
             "avg_view_percentage": 48},
        ],
        "bottom_performing_videos": [
            {"title": "Random History Topic", "views": 800, "ctr_pct": 2.1,
             "avg_retention_pct": 25},
        ],
        "tag_performance": {
            "high_performing_tags": ["history", "ancient rome", "documentary"],
            "recommended_tag_mix": "Mix broad + niche tags",
        },
        "experiment_recommendations": ["Try a villain-focused narrative"],
    }
    if overrides:
        base.update(overrides)
    return base


def _write_insights(tmp_dir, data):
    path = Path(tmp_dir) / "channel_insights.json"
    path.write_text(json.dumps(data))
    return path


class TestLoadInsights:
    def test_returns_empty_when_missing(self, tmp_path):
        with patch.object(channel_insights, 'INSIGHTS_FILE', tmp_path / "missing.json"):
            assert channel_insights.load_insights() == {}

    def test_returns_empty_on_corrupt_json(self, tmp_path):
        bad = tmp_path / "channel_insights.json"
        bad.write_text("not json {{{")
        with patch.object(channel_insights, 'INSIGHTS_FILE', bad):
            assert channel_insights.load_insights() == {}

    def test_loads_valid_json(self, tmp_path):
        data = {"data_quality": {"confidence_level": "sufficient"}}
        p = tmp_path / "channel_insights.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.load_insights()
            assert result["data_quality"]["confidence_level"] == "sufficient"


class TestConfidenceLevel:
    def test_none_when_missing(self, tmp_path):
        with patch.object(channel_insights, 'INSIGHTS_FILE', tmp_path / "nope.json"):
            assert channel_insights.get_confidence_level() == "none"

    def test_returns_level(self, tmp_path):
        p = tmp_path / "insights.json"
        p.write_text(json.dumps({"data_quality": {"confidence_level": "low"}}))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_confidence_level() == "low"


class TestIsFresh:
    def test_fresh_data(self, tmp_path):
        data = {"generated_at": datetime.now(timezone.utc).isoformat()}
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.is_insights_fresh() is True

    def test_stale_data(self, tmp_path):
        old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        data = {"generated_at": old}
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.is_insights_fresh() is False

    def test_missing_timestamp(self, tmp_path):
        p = tmp_path / "i.json"
        p.write_text(json.dumps({"generated_at": ""}))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.is_insights_fresh() is False

    def test_z_suffix_parsed(self, tmp_path):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        p = tmp_path / "i.json"
        p.write_text(json.dumps({"generated_at": ts}))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.is_insights_fresh() is True


class TestTruncate:
    def test_short_text_unchanged(self):
        assert channel_insights._truncate("hello world", 10) == "hello world"

    def test_long_text_truncated(self):
        text = " ".join(["word"] * 20)
        result = channel_insights._truncate(text, max_words=5)
        assert result.endswith("[...]")
        assert len(result.split()) == 6  # 5 words + [...]


class TestGlobalIntelligenceBlock:
    def test_empty_when_no_confidence(self, tmp_path):
        data = {"data_quality": {"confidence_level": "none"}}
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_global_intelligence_block() == ""

    def test_contains_channel_performance(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_global_intelligence_block()
            assert "CHANNEL PERFORMANCE INTELLIGENCE" in result
            assert "20 published videos" in result

    def test_low_confidence_prefix(self, tmp_path):
        data = _make_insights(confidence="low", n_videos=3)
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_global_intelligence_block()
            assert "EARLY DATA" in result

    def test_whats_working_section(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_global_intelligence_block()
            assert "WHAT'S WORKING" in result

    def test_dna_confidence_section(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_global_intelligence_block()
            assert "DNA CONFIDENCE" in result
            assert "VALIDATED" in result


class TestTopicDiscoveryIntelligence:
    def test_empty_when_no_confidence(self, tmp_path):
        data = {"data_quality": {"confidence_level": "none"}}
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_topic_discovery_intelligence() == ""

    def test_contains_era_rankings(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_topic_discovery_intelligence()
            assert "ERA RANKINGS" in result
            assert "Ancient Rome" in result


class TestSeoIntelligence:
    def test_contains_high_ctr_patterns(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_seo_intelligence()
            assert "HIGH-CTR TITLE PATTERNS" in result
            assert "Numbers in title" in result

    def test_contains_recommended_tags(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_seo_intelligence()
            assert "RECOMMENDED TAGS" in result


class TestNarrativeIntelligence:
    def test_contains_retention_data(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_narrative_intelligence()
            assert "OPTIMAL LENGTH" in result
            assert "11" in result

    def test_contains_retention_bands(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_narrative_intelligence()
            assert "RETENTION BY VIDEO LENGTH" in result


class TestScriptIntelligence:
    def test_contains_top_performers(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_script_intelligence()
            assert "TOP PERFORMING VIDEOS" in result
            assert "Caesar" in result

    def test_contains_weak_performers(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_script_intelligence()
            assert "WEAK PERFORMERS" in result

    def test_contains_experiment_rec(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_script_intelligence()
            assert "EXPERIMENT TO TRY" in result


class TestDnaConfidenceBlock:
    def test_empty_when_few_videos(self, tmp_path):
        data = _make_insights(n_videos=1)
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_dna_confidence_block() == ""

    def test_validated_scores(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_dna_confidence_block()
            assert "VALIDATED" in result
            assert "80%" in result  # open_mid_action_hook = 0.8

    def test_weakening_scores(self, tmp_path):
        data = _make_insights()
        data["dna_confidence_updates"]["present_tense_narration"] = 0.2
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_dna_confidence_block()
            assert "WEAKENING" in result


class TestRetentionFallback:
    """Test that avg_retention_pct falls back to avg_view_percentage."""

    def test_uses_avg_retention_pct(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_narrative_intelligence()
            assert "52%" in result  # first video has avg_retention_pct=52

    def test_falls_back_to_avg_view_percentage(self, tmp_path):
        data = _make_insights()
        # Remove avg_retention_pct, keep avg_view_percentage
        data["top_performing_videos"] = [
            {"title": "Test Video", "views": 5000, "avg_view_percentage": 45},
        ]
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_narrative_intelligence()
            assert "45%" in result


# ── Shorts Intelligence Tests ────────────────────────────────────────────────

class TestGetShortsIntelligence:
    def _insights_with_shorts(self):
        data = _make_insights()
        data["shorts_intelligence"] = {
            "total_shorts": 8,
            "total_views": 40000,
            "avg_views_per_short": 5000.0,
            "total_subs_from_shorts": 120,
            "avg_subs_per_short": 15.0,
            "sub_conversion_rate_pct": 0.300,
            "era_performance": {
                "ancient": {"avg_views": 6000, "total_subs": 80, "avg_subs_per_short": 20.0,
                            "short_count": 4, "sub_conversion_rate": 0.333},
                "medieval": {"avg_views": 4000, "total_subs": 40, "avg_subs_per_short": 10.0,
                             "short_count": 4, "sub_conversion_rate": 0.250},
            },
            "top_hooks": [
                {"hook": "The Secret Poison That Killed An Emperor", "views": 12000, "subs": 45, "era": "ancient"},
                {"hook": "Why Knights Actually Feared This Weapon", "views": 8000, "subs": 30, "era": "medieval"},
            ],
        }
        data["shorts_long_correlation"] = {
            "topics_with_shorts": 3,
            "topics_without_shorts": 5,
            "view_lift_pct": 18.5,
            "sample_size_note": "3 paired, 5 unpaired — directional only",
        }
        return data

    def test_empty_when_no_shorts_data(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_shorts_intelligence() == ""

    def test_empty_when_zero_shorts(self, tmp_path):
        data = _make_insights()
        data["shorts_intelligence"] = {"total_shorts": 0}
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            assert channel_insights.get_shorts_intelligence() == ""

    def test_contains_global_stats(self, tmp_path):
        data = self._insights_with_shorts()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_shorts_intelligence()
            assert "SHORTS PERFORMANCE INTELLIGENCE" in result
            assert "Total shorts: 8" in result
            assert "Total subs: 120" in result

    def test_contains_era_rankings(self, tmp_path):
        data = self._insights_with_shorts()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_shorts_intelligence()
            assert "SHORTS ERA RANKINGS BY SUBS" in result
            assert "Ancient" in result
            assert "80 subs" in result

    def test_contains_top_hooks(self, tmp_path):
        data = self._insights_with_shorts()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_shorts_intelligence()
            assert "TOP SHORT HOOKS" in result
            assert "Secret Poison" in result

    def test_contains_correlation(self, tmp_path):
        data = self._insights_with_shorts()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_shorts_intelligence()
            assert "CORRELATION" in result
            assert "+18.5%" in result

    def test_no_correlation_when_missing(self, tmp_path):
        data = self._insights_with_shorts()
        del data["shorts_long_correlation"]
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_shorts_intelligence()
            assert "CORRELATION" not in result


class TestTopicDiscoveryShortsSignals:
    """Test that topic discovery intelligence includes shorts signals."""

    def test_includes_shorts_era_performance(self, tmp_path):
        data = _make_insights()
        data["shorts_intelligence"] = {
            "era_performance": {
                "ancient": {"total_subs": 50, "short_count": 3, "sub_conversion_rate": 0.250},
            }
        }
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_topic_discovery_intelligence()
            assert "SHORTS ERA PERFORMANCE" in result
            assert "50 subs" in result

    def test_includes_shorts_correlation_lift(self, tmp_path):
        data = _make_insights()
        data["shorts_long_correlation"] = {
            "topics_with_shorts": 4,
            "view_lift_pct": 22.3,
            "sample_size_note": "4 paired, 6 unpaired — directional only",
        }
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_topic_discovery_intelligence()
            assert "SHORTS BOOST" in result
            assert "+22.3%" in result

    def test_no_shorts_signals_when_absent(self, tmp_path):
        data = _make_insights()
        p = tmp_path / "i.json"
        p.write_text(json.dumps(data))
        with patch.object(channel_insights, 'INSIGHTS_FILE', p):
            result = channel_insights.get_topic_discovery_intelligence()
            assert "SHORTS ERA PERFORMANCE" not in result
            assert "SHORTS BOOST" not in result


class TestRecurringQualityWarnings:

    def test_empty_when_no_data(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        assert _get_recurring_quality_warnings({}) == ""

    def test_empty_when_no_warnings(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        insights = {"per_video_stats": [{"title": "V1"}, {"title": "V2"}]}
        assert _get_recurring_quality_warnings(insights) == ""

    def test_detects_recurring_warning(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        insights = {"per_video_stats": [
            {"title": "V1", "quality_report_warnings": ["SEO title too long: 85 characters"]},
            {"title": "V2", "quality_report_warnings": ["SEO title too long: 92 characters"]},
            {"title": "V3", "quality_report_warnings": ["No rhetorical questions"]},
        ]}
        result = _get_recurring_quality_warnings(insights)
        assert "seo title too long" in result.lower()

    def test_ignores_one_off_warnings(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        insights = {"per_video_stats": [
            {"title": "V1", "quality_report_warnings": ["Unique issue A"]},
            {"title": "V2", "quality_report_warnings": ["Unique issue B"]},
        ]}
        assert _get_recurring_quality_warnings(insights) == ""

    def test_only_checks_last_5(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        stats = [{"title": f"V{i}", "quality_report_warnings": []} for i in range(10)]
        stats[0]["quality_report_warnings"] = ["Old issue"]
        stats[1]["quality_report_warnings"] = ["Old issue"]
        assert _get_recurring_quality_warnings({"per_video_stats": stats}) == ""

    def test_no_crash_on_malformed(self):
        from intel.channel_insights import _get_recurring_quality_warnings
        insights = {"per_video_stats": [
            {"quality_report_warnings": "not a list"},
            {"quality_report_warnings": None},
            {},
        ]}
        assert isinstance(_get_recurring_quality_warnings(insights), str)

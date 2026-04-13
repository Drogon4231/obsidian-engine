"""Tests for intel/youtube_knowledge_base.py — base knowledge layer for agents."""
import pytest

from intel.youtube_knowledge_base import (
    BASE_BENCHMARKS,
    BENCHMARK_TIERS,
    TITLE_PATTERNS,
    get_blended_value,
    get_blended_benchmarks,
    get_confidence_pct,
    get_base_topic_discovery_intel,
    get_base_narrative_intel,
    get_base_retention_intel,
    get_base_script_intel,
    get_base_seo_intel,
    get_base_thumbnail_intel,
    get_base_shorts_intel,
    get_base_publishing_intel,
    get_base_content_quality_intel,
    get_full_knowledge_summary,
)


@pytest.mark.unit
class TestBaseBenchmarks:
    """Verify benchmark data structure and reasonable values."""

    def test_has_ctr_benchmarks(self):
        assert "ctr_0_1k" in BASE_BENCHMARKS
        assert "ctr_100k_plus" in BASE_BENCHMARKS

    def test_ctr_increases_with_size(self):
        assert BASE_BENCHMARKS["ctr_0_1k"] < BASE_BENCHMARKS["ctr_100k_plus"]

    def test_has_retention_benchmarks(self):
        assert "retention_under_8min" in BASE_BENCHMARKS
        assert "retention_over_20min" in BASE_BENCHMARKS

    def test_retention_decreases_with_length(self):
        assert BASE_BENCHMARKS["retention_under_8min"] > BASE_BENCHMARKS["retention_over_20min"]

    def test_all_values_are_numeric(self):
        for key, val in BASE_BENCHMARKS.items():
            assert isinstance(val, (int, float)), f"{key} is not numeric: {val}"


@pytest.mark.unit
class TestBenchmarkTiers:
    """Verify tier structure."""

    def test_has_four_tiers(self):
        assert len(BENCHMARK_TIERS) == 4

    def test_each_tier_has_required_keys(self):
        required = {"label", "avg_ctr_pct", "avg_retention_pct", "avg_views_per_video"}
        for tier_name, tier_data in BENCHMARK_TIERS.items():
            for key in required:
                assert key in tier_data, f"Tier {tier_name} missing {key}"


@pytest.mark.unit
class TestTitlePatterns:
    """Verify title pattern intelligence structure."""

    def test_has_high_ctr_structures(self):
        assert len(TITLE_PATTERNS["high_ctr_structures"]) >= 3

    def test_each_pattern_has_example(self):
        for pat in TITLE_PATTERNS["high_ctr_structures"]:
            assert "pattern" in pat
            assert "example" in pat
            assert "why" in pat

    def test_has_power_words(self):
        assert "mystery_intrigue" in TITLE_PATTERNS["power_words"]
        assert "darkness_severity" in TITLE_PATTERNS["power_words"]

    def test_has_words_to_avoid(self):
        assert len(TITLE_PATTERNS["words_to_avoid"]) >= 3


@pytest.mark.unit
class TestGetBlendedValue:
    """Test Bayesian blending of base priors with channel data."""

    def test_pure_base_at_zero_videos(self):
        result = get_blended_value("ctr_0_1k", own_data_value=80.0, own_video_count=0)
        assert result == BASE_BENCHMARKS["ctr_0_1k"]

    def test_pure_own_at_threshold(self):
        result = get_blended_value("ctr_0_1k", own_data_value=80.0, own_video_count=15)
        assert result == 80.0

    def test_blend_at_midpoint(self):
        base = BASE_BENCHMARKS["ctr_0_1k"]
        result = get_blended_value("ctr_0_1k", own_data_value=80.0, own_video_count=7)
        assert base < result < 80.0

    def test_above_threshold_uses_own(self):
        result = get_blended_value("ctr_0_1k", own_data_value=80.0, own_video_count=100)
        assert result == 80.0

    def test_unknown_metric_returns_own(self):
        result = get_blended_value("nonexistent_metric", own_data_value=42.0, own_video_count=5)
        assert result == 42.0


@pytest.mark.unit
class TestGetBlendedBenchmarks:
    """Test full benchmark blending."""

    def test_returns_dict(self):
        result = get_blended_benchmarks(own_metrics={}, own_video_count=0)
        assert isinstance(result, dict)

    def test_empty_own_returns_empty(self):
        result = get_blended_benchmarks(own_metrics={}, own_video_count=0)
        assert result == {}

    def test_uses_own_when_mature(self):
        own = {"ctr_0_1k": 10.0}
        result = get_blended_benchmarks(own_metrics=own, own_video_count=20)
        assert result["ctr_0_1k"] == 10.0

    def test_blends_at_midpoint(self):
        own = {"ctr_0_1k": 10.0}
        result = get_blended_benchmarks(own_metrics=own, own_video_count=7)
        assert result["ctr_0_1k"] != 10.0  # blended, not pure own


@pytest.mark.unit
class TestGetConfidencePct:
    """Test confidence percentage computation."""

    def test_zero_videos_zero_confidence(self):
        assert get_confidence_pct(0) == 0.0

    def test_full_confidence_at_threshold(self):
        assert get_confidence_pct(15) == 1.0

    def test_partial_confidence(self):
        pct = get_confidence_pct(7, maturity_threshold=15)
        assert 0.0 < pct < 1.0

    def test_capped_above_threshold(self):
        assert get_confidence_pct(100) == 1.0


@pytest.mark.unit
class TestGetBaseIntelFunctions:
    """Test all get_base_*_intel functions return non-empty strings."""

    def test_topic_discovery(self):
        result = get_base_topic_discovery_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_narrative(self):
        result = get_base_narrative_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_retention(self):
        result = get_base_retention_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_script(self):
        result = get_base_script_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_seo(self):
        result = get_base_seo_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_thumbnail(self):
        result = get_base_thumbnail_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_shorts(self):
        result = get_base_shorts_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_publishing(self):
        result = get_base_publishing_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_content_quality(self):
        result = get_base_content_quality_intel()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_full_summary(self):
        result = get_full_knowledge_summary()
        assert isinstance(result, str)
        assert len(result) > 100

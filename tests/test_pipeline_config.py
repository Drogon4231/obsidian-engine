"""Tests for pipeline_config.py — configuration validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import pipeline_config


class TestPipelineConfig:
    def test_has_required_settings(self):
        """All critical config variables exist."""
        assert hasattr(pipeline_config, 'WEBHOOK_MAX_TRIGGERS_PER_HOUR')
        assert hasattr(pipeline_config, 'WEBHOOK_MAX_CALLS_PER_MINUTE')
        assert hasattr(pipeline_config, 'DISCORD_WEBHOOK_URL')
        assert hasattr(pipeline_config, 'DASHBOARD_PASSWORD')

    def test_rate_limits_are_sane(self):
        """Rate limits should be positive integers."""
        assert pipeline_config.WEBHOOK_MAX_TRIGGERS_PER_HOUR > 0
        assert pipeline_config.WEBHOOK_MAX_CALLS_PER_MINUTE > 0

    def test_discord_url_is_string(self):
        assert isinstance(pipeline_config.DISCORD_WEBHOOK_URL, str)

    def test_dashboard_password_is_string(self):
        assert isinstance(pipeline_config.DASHBOARD_PASSWORD, str)


# ---------------------------------------------------------------------------
# Scoring config objects exist
# ---------------------------------------------------------------------------

class TestScoringConfigsExist:
    def test_scoring_config_exists(self):
        assert hasattr(pipeline_config, 'SCORING_CONFIG')
        assert isinstance(pipeline_config.SCORING_CONFIG, dict)

    def test_scoring_adjustments_early_exists(self):
        assert hasattr(pipeline_config, 'SCORING_ADJUSTMENTS_EARLY')
        assert isinstance(pipeline_config.SCORING_ADJUSTMENTS_EARLY, dict)

    def test_scoring_adjustments_growing_exists(self):
        assert hasattr(pipeline_config, 'SCORING_ADJUSTMENTS_GROWING')
        assert isinstance(pipeline_config.SCORING_ADJUSTMENTS_GROWING, dict)

    def test_scoring_adjustments_mature_exists(self):
        assert hasattr(pipeline_config, 'SCORING_ADJUSTMENTS_MATURE')
        assert isinstance(pipeline_config.SCORING_ADJUSTMENTS_MATURE, dict)

    def test_scoring_thresholds_exists(self):
        assert hasattr(pipeline_config, 'SCORING_THRESHOLDS')
        assert isinstance(pipeline_config.SCORING_THRESHOLDS, dict)


# ---------------------------------------------------------------------------
# Adjustment dicts share the same 11 signal keys
# ---------------------------------------------------------------------------

EXPECTED_SIGNAL_KEYS = {
    "era_fatigue",
    "audience_request",
    "trending",
    "cost_efficiency",
    "shorts_subs",
    "search_demand",
    "engagement",
    "subscriber_conversion",
    "traffic_source",
    "content_pattern",
    "demographic_alignment",
    "shorts_correlation",
    "sentiment",
    "competitive_gap",
    "competitor_trending",
    "niche_saturation",
}


class TestScoringAdjustmentKeys:
    def test_early_has_all_signal_keys(self):
        assert set(pipeline_config.SCORING_ADJUSTMENTS_EARLY.keys()) == EXPECTED_SIGNAL_KEYS

    def test_growing_has_all_signal_keys(self):
        assert set(pipeline_config.SCORING_ADJUSTMENTS_GROWING.keys()) == EXPECTED_SIGNAL_KEYS

    def test_mature_has_all_signal_keys(self):
        assert set(pipeline_config.SCORING_ADJUSTMENTS_MATURE.keys()) == EXPECTED_SIGNAL_KEYS

    def test_all_three_dicts_have_same_keys(self):
        early = set(pipeline_config.SCORING_ADJUSTMENTS_EARLY.keys())
        growing = set(pipeline_config.SCORING_ADJUSTMENTS_GROWING.keys())
        mature = set(pipeline_config.SCORING_ADJUSTMENTS_MATURE.keys())
        assert early == growing == mature


# ---------------------------------------------------------------------------
# SCORING_THRESHOLDS validation
# ---------------------------------------------------------------------------

class TestScoringThresholds:
    """Validate every key in SCORING_THRESHOLDS for type and range."""

    def _t(self):
        return pipeline_config.SCORING_THRESHOLDS

    # -- All values must be numeric --
    def test_all_values_are_numeric(self):
        for key, val in self._t().items():
            assert isinstance(val, (int, float)), f"{key} should be numeric, got {type(val)}"

    # -- Subscriber conversion --
    def test_sub_conversion_high_multiplier_gt_one(self):
        assert self._t()["sub_conversion_high_multiplier"] > 1.0

    # -- Engagement --
    def test_engagement_min_video_count_gte_one(self):
        assert self._t()["engagement_min_video_count"] >= 1

    # -- Search demand --
    def test_search_demand_min_word_len_gte_one(self):
        assert self._t()["search_demand_min_word_len"] >= 1

    def test_search_demand_min_matches_gte_one(self):
        assert self._t()["search_demand_min_matches"] >= 1

    # -- Traffic source percentages (0-100) --
    def test_traffic_search_dominant_pct_range(self):
        assert 0 <= self._t()["traffic_search_dominant_pct"] <= 100

    def test_traffic_browse_dominant_pct_range(self):
        assert 0 <= self._t()["traffic_browse_dominant_pct"] <= 100

    def test_traffic_suggested_dominant_pct_range(self):
        assert 0 <= self._t()["traffic_suggested_dominant_pct"] <= 100

    def test_traffic_min_specificity_signals_gte_one(self):
        assert self._t()["traffic_min_specificity_signals"] >= 1

    def test_traffic_min_click_signals_gte_one(self):
        assert self._t()["traffic_min_click_signals"] >= 1

    # -- Demographic alignment (0-100) --
    def test_demographic_min_audience_pct_range(self):
        assert 0 <= self._t()["demographic_min_audience_pct"] <= 100

    # -- Quality scoring --
    def test_quality_min_proper_nouns_gte_zero(self):
        assert self._t()["quality_min_proper_nouns"] >= 0

    def test_quality_proper_noun_bonus_is_float(self):
        assert isinstance(self._t()["quality_proper_noun_bonus"], float)

    def test_quality_no_proper_noun_penalty_lte_zero(self):
        assert self._t()["quality_no_proper_noun_penalty"] <= 0

    def test_quality_date_bonus_gte_zero(self):
        assert self._t()["quality_date_bonus"] >= 0

    def test_quality_comparison_bonus_gte_zero(self):
        assert self._t()["quality_comparison_bonus"] >= 0

    def test_quality_min_emotional_words_gte_one(self):
        assert self._t()["quality_min_emotional_words"] >= 1

    def test_quality_emotional_high_bonus_gte_zero(self):
        assert self._t()["quality_emotional_high_bonus"] >= 0

    def test_quality_emotional_low_bonus_gte_zero(self):
        assert self._t()["quality_emotional_low_bonus"] >= 0

    def test_quality_broad_penalty_lte_zero(self):
        assert self._t()["quality_broad_penalty"] <= 0

    def test_quality_min_title_words_gte_one(self):
        assert self._t()["quality_min_title_words"] >= 1

    def test_quality_max_title_words_gt_min(self):
        assert self._t()["quality_max_title_words"] > self._t()["quality_min_title_words"]

    def test_quality_title_length_penalty_lte_zero(self):
        assert self._t()["quality_title_length_penalty"] <= 0

    def test_quality_multiplier_min_lt_max(self):
        assert self._t()["quality_multiplier_min"] < self._t()["quality_multiplier_max"]

    # -- Experiment strategy --
    def test_experiment_underexplored_videos_gte_zero(self):
        assert self._t()["experiment_underexplored_videos"] >= 0

    # -- Queue management --
    def test_queue_low_threshold_gte_zero(self):
        assert self._t()["queue_low_threshold"] >= 0

    def test_queue_high_threshold_gt_low(self):
        assert self._t()["queue_high_threshold"] > self._t()["queue_low_threshold"]

    def test_queue_medium_ratio_range(self):
        assert 0 <= self._t()["queue_medium_ratio"] <= 1

    def test_queue_high_ratio_range(self):
        assert 0 <= self._t()["queue_high_ratio"] <= 1

    def test_queue_minimum_topics_gte_one(self):
        assert self._t()["queue_minimum_topics"] >= 1

    # -- Word matching --
    def test_matching_min_word_len_gte_one(self):
        assert self._t()["matching_min_word_len"] >= 1

    def test_matching_min_word_matches_gte_one(self):
        assert self._t()["matching_min_word_matches"] >= 1

    def test_matching_long_word_len_gte_one(self):
        assert self._t()["matching_long_word_len"] >= 1

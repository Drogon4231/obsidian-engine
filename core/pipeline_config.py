"""
Pipeline configuration — reads from obsidian.yaml via core.config.

All module-level constants are preserved for backward compatibility.
To customize, edit obsidian.yaml (not this file).
"""

import os
from pathlib import Path

from core.config import cfg

# ── Project paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# ── Voice settings (from obsidian.yaml → voice.*) ────────────────────────────
NARRATOR_VOICE_ID = cfg.voice.narrator_id
QUOTE_VOICE_ID = cfg.voice.quote_id
VOICE_BODY = cfg.voice.body.to_dict()
VOICE_HOOK = cfg.voice.hook.to_dict()
VOICE_QUOTE = cfg.voice.quote.to_dict()
VOICE_SPEED_BODY = cfg.voice.speed_body
VOICE_SPEED_HOOK = cfg.voice.speed_hook
VOICE_SPEED_QUOTE = cfg.voice.speed_quote

# ── Image generation (from obsidian.yaml → models.*) ─────────────────────────
IMAGE_MODEL = cfg.models.image_provider
IMAGE_QUALITY_THRESHOLD = cfg.models.image_quality_threshold
IMAGE_MAX_RETRIES = cfg.models.image_max_retries

# ── Script constraints (from obsidian.yaml → script.*) ───────────────────────
SCRIPT_MIN_WORDS = cfg.script.min_words
SCRIPT_MAX_WORDS = cfg.script.max_words
SHORT_SCRIPT_MIN_WORDS = cfg.script.short_min_words
SHORT_SCRIPT_MAX_WORDS = cfg.script.short_max_words

# ── Video rendering (from obsidian.yaml → video.*) ───────────────────────────
VIDEO_FPS = cfg.video.fps
VIDEO_CRF = cfg.video.crf
LONG_VIDEO_WIDTH = cfg.video.long_width
LONG_VIDEO_HEIGHT = cfg.video.long_height
SHORT_VIDEO_WIDTH = cfg.video.short_width
SHORT_VIDEO_HEIGHT = cfg.video.short_height

# ── Scene splitting ──────────────────────────────────────────────────────────
MAX_SCENE_SECONDS = cfg.video.max_scene_seconds

# ── Audio (from obsidian.yaml → audio.*) ─────────────────────────────────────
AUDIO_CHUNK_MAX_CHARS = cfg.audio.chunk_max_chars
AUDIO_TAIL_BUFFER_SEC = cfg.audio.tail_buffer_sec

# ── Scheduling (from obsidian.yaml → schedule.*) ─────────────────────────────
SCHEDULE_TOPIC_DISCOVERY = cfg.schedule.topic_discovery.to_dict()
SCHEDULE_PIPELINE = cfg.schedule.pipeline.to_dict()
SCHEDULE_ANALYTICS = {"hour": cfg.schedule.analytics_hour}

# ── Quality gates (from obsidian.yaml → quality.*) ───────────────────────────
MIN_RESEARCH_FACTS = cfg.quality.min_research_facts
MIN_RESEARCH_FIGURES = cfg.quality.min_research_figures
MIN_TAGS = cfg.quality.min_tags
MIN_SCENES = cfg.quality.min_scenes
MIN_AUDIO_DURATION = cfg.audio.min_duration
MAX_AUDIO_DURATION = cfg.audio.max_duration
MIN_VIDEO_SIZE_MB = cfg.quality.min_video_size_mb

# ── WPM gate enforcement ────────────────────────────────────────────────────
ENFORCE_WPM_GATE = cfg.quality.enforce_wpm_gate

# ── Cost budget (from obsidian.yaml → cost.*) ────────────────────────────────
COST_BUDGET_MAX_USD = cfg.cost.budget_max_usd

# ── Storage cleanup ──────────────────────────────────────────────────────────
CLEANUP_AFTER_UPLOAD = cfg.cost.cleanup_after_upload
CLEANUP_WARN_DISK_GB = cfg.cost.cleanup_warn_disk_gb

# ── API retry settings (from obsidian.yaml → api.*) ─────────────────────────
API_MAX_RETRIES = cfg.api.max_retries
API_BACKOFF_BASE = cfg.api.backoff_base
API_TIMEOUT = cfg.api.timeout

# ── Webhook security (from obsidian.yaml → server.*) ────────────────────────
WEBHOOK_MAX_TRIGGERS_PER_HOUR = cfg.server.max_triggers_per_hour
WEBHOOK_MAX_CALLS_PER_MINUTE = cfg.server.max_calls_per_minute

# ── Discord notifications ───────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Dashboard authentication ────────────────────────────────────────────────
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

# ── Topic Discovery Scoring ─────────────────────────────────────────────────
SCORING_CONFIG = {
    "maturity_threshold": cfg.scoring.maturity_threshold,
    "max_score": cfg.scoring.max_score,
    "min_score": cfg.scoring.min_score,
    "default_topic_score": cfg.scoring.default_topic_score,
    "max_topics_per_discovery": cfg.scoring.max_topics_per_discovery,
    "experiment_cadence_default": cfg.scoring.experiment_cadence_default,
    "experiment_cadence_throttled": cfg.scoring.experiment_cadence_throttled,
}

# Dynamic adjustment magnitudes by channel maturity tier
# These are kept as hardcoded dicts since they're deeply interconnected
# and rarely need per-deployment customization.
SCORING_ADJUSTMENTS_EARLY = {        # < 5 videos
    "era_fatigue": -0.15,
    "audience_request": +0.20,
    "trending": +0.15,
    "cost_efficiency": +0.03,
    "shorts_subs": +0.03,
    "search_demand": +0.12,
    "engagement": +0.03,
    "subscriber_conversion": +0.05,
    "traffic_source": +0.03,
    "content_pattern": +0.03,
    "demographic_alignment": +0.02,
    "shorts_correlation": +0.03,
    "sentiment": +0.03,
    "competitive_gap": +0.12,
    "competitor_trending": +0.10,
    "niche_saturation": -0.08,
}
SCORING_ADJUSTMENTS_GROWING = {      # 5-14 videos
    "era_fatigue": -0.20,
    "audience_request": +0.15,
    "trending": +0.10,
    "cost_efficiency": +0.05,
    "shorts_subs": +0.05,
    "search_demand": +0.10,
    "engagement": +0.05,
    "subscriber_conversion": +0.07,
    "traffic_source": +0.05,
    "content_pattern": +0.05,
    "demographic_alignment": +0.03,
    "shorts_correlation": +0.04,
    "sentiment": +0.05,
    "competitive_gap": +0.10,
    "competitor_trending": +0.08,
    "niche_saturation": -0.10,
}
SCORING_ADJUSTMENTS_MATURE = {       # 15+ videos
    "era_fatigue": -0.25,
    "audience_request": +0.12,
    "trending": +0.08,
    "cost_efficiency": +0.07,
    "shorts_subs": +0.05,
    "search_demand": +0.08,
    "engagement": +0.07,
    "subscriber_conversion": +0.10,
    "traffic_source": +0.05,
    "content_pattern": +0.05,
    "demographic_alignment": +0.03,
    "shorts_correlation": +0.05,
    "sentiment": +0.05,
    "competitive_gap": +0.08,
    "competitor_trending": +0.06,
    "niche_saturation": -0.12,
}

# ── Signal Thresholds ────────────────────────────────────────────────────────
SCORING_THRESHOLDS = {
    "sub_conversion_high_multiplier": 1.5,
    "engagement_min_video_count": 1,
    "search_demand_min_word_len": 4,
    "search_demand_min_matches": 2,
    "traffic_search_dominant_pct": 50,
    "traffic_browse_dominant_pct": 50,
    "traffic_suggested_dominant_pct": 40,
    "traffic_min_specificity_signals": 2,
    "traffic_min_click_signals": 2,
    "demographic_min_audience_pct": 20,
    "quality_min_proper_nouns": 2,
    "quality_proper_noun_bonus": 0.05,
    "quality_no_proper_noun_penalty": -0.05,
    "quality_date_bonus": 0.03,
    "quality_comparison_bonus": 0.05,
    "quality_min_emotional_words": 2,
    "quality_emotional_high_bonus": 0.05,
    "quality_emotional_low_bonus": 0.02,
    "quality_broad_penalty": -0.10,
    "quality_min_title_words": 3,
    "quality_max_title_words": 15,
    "quality_title_length_penalty": -0.05,
    "quality_multiplier_min": 0.8,
    "quality_multiplier_max": 1.2,
    "experiment_underexplored_videos": 3,
    "queue_low_threshold": 5,
    "queue_high_threshold": 15,
    "queue_medium_ratio": 0.75,
    "queue_high_ratio": 0.50,
    "queue_minimum_topics": 10,
    "matching_min_word_len": 4,
    "matching_min_word_matches": 2,
    "matching_long_word_len": 6,
    "competitive_gap_min_views": 10000,
    "competitive_gap_min_word_matches": 2,
    "competitive_gap_max_age_days": 180,
    "competitor_trending_min_ratio": 1.5,
    "competitor_trending_lookback_days": 14,
    "niche_saturation_min_competitors": 3,
    "niche_saturation_min_word_matches": 2,
    "competitive_shorts_max_duration": 60,
    "competitive_max_total_boost": 0.15,
}


# ── Config validation ─────────────────────────────────────────────────────────

def validate_config() -> list[str]:
    """Validate all configuration values. Returns list of errors (empty = valid)."""
    errors = []

    def _check_range(name, value, lo, hi):
        if not isinstance(value, (int, float)):
            errors.append(f"{name}: expected number, got {type(value).__name__}")
        elif value < lo or value > hi:
            errors.append(f"{name}: {value} out of range [{lo}, {hi}]")

    def _check_positive(name, value):
        if not isinstance(value, (int, float)) or value < 0:
            errors.append(f"{name}: must be non-negative, got {value}")

    # Voice settings
    for key in ("stability", "similarity_boost", "style"):
        for voice_name, voice_dict in [("BODY", VOICE_BODY), ("HOOK", VOICE_HOOK), ("QUOTE", VOICE_QUOTE)]:
            _check_range(f"VOICE_{voice_name}.{key}", voice_dict.get(key, 0), 0.0, 1.0)
    _check_range("VOICE_SPEED_BODY", VOICE_SPEED_BODY, 0.5, 2.0)
    _check_range("VOICE_SPEED_HOOK", VOICE_SPEED_HOOK, 0.5, 2.0)
    _check_range("VOICE_SPEED_QUOTE", VOICE_SPEED_QUOTE, 0.5, 2.0)

    # Image generation
    _check_range("IMAGE_QUALITY_THRESHOLD", IMAGE_QUALITY_THRESHOLD, 1, 10)
    _check_range("IMAGE_MAX_RETRIES", IMAGE_MAX_RETRIES, 0, 10)

    # Script constraints
    _check_positive("SCRIPT_MIN_WORDS", SCRIPT_MIN_WORDS)
    _check_positive("SCRIPT_MAX_WORDS", SCRIPT_MAX_WORDS)
    if SCRIPT_MIN_WORDS >= SCRIPT_MAX_WORDS:
        errors.append(f"SCRIPT_MIN_WORDS ({SCRIPT_MIN_WORDS}) must be < SCRIPT_MAX_WORDS ({SCRIPT_MAX_WORDS})")
    _check_positive("SHORT_SCRIPT_MIN_WORDS", SHORT_SCRIPT_MIN_WORDS)
    _check_positive("SHORT_SCRIPT_MAX_WORDS", SHORT_SCRIPT_MAX_WORDS)

    # Video rendering
    _check_range("VIDEO_FPS", VIDEO_FPS, 24, 60)
    _check_range("VIDEO_CRF", VIDEO_CRF, 0, 51)
    _check_positive("LONG_VIDEO_WIDTH", LONG_VIDEO_WIDTH)
    _check_positive("LONG_VIDEO_HEIGHT", LONG_VIDEO_HEIGHT)

    # Audio
    _check_positive("AUDIO_CHUNK_MAX_CHARS", AUDIO_CHUNK_MAX_CHARS)
    _check_positive("AUDIO_TAIL_BUFFER_SEC", AUDIO_TAIL_BUFFER_SEC)

    # Quality gates
    _check_positive("MIN_RESEARCH_FACTS", MIN_RESEARCH_FACTS)
    _check_positive("MIN_RESEARCH_FIGURES", MIN_RESEARCH_FIGURES)
    _check_positive("MIN_TAGS", MIN_TAGS)
    _check_positive("MIN_SCENES", MIN_SCENES)
    _check_positive("MIN_AUDIO_DURATION", MIN_AUDIO_DURATION)
    _check_positive("MAX_AUDIO_DURATION", MAX_AUDIO_DURATION)
    if MIN_AUDIO_DURATION >= MAX_AUDIO_DURATION:
        errors.append(f"MIN_AUDIO_DURATION ({MIN_AUDIO_DURATION}) must be < MAX_AUDIO_DURATION ({MAX_AUDIO_DURATION})")

    # Cost budget
    _check_positive("COST_BUDGET_MAX_USD", COST_BUDGET_MAX_USD)

    # API settings
    _check_range("API_MAX_RETRIES", API_MAX_RETRIES, 0, 20)
    _check_positive("API_BACKOFF_BASE", API_BACKOFF_BASE)
    _check_positive("API_TIMEOUT", API_TIMEOUT)

    # Webhook security
    _check_positive("WEBHOOK_MAX_TRIGGERS_PER_HOUR", WEBHOOK_MAX_TRIGGERS_PER_HOUR)
    _check_positive("WEBHOOK_MAX_CALLS_PER_MINUTE", WEBHOOK_MAX_CALLS_PER_MINUTE)

    # Scoring config
    _check_range("SCORING_CONFIG.max_score", SCORING_CONFIG["max_score"], 0.0, 10.0)
    _check_range("SCORING_CONFIG.min_score", SCORING_CONFIG["min_score"], 0.0, 10.0)
    if SCORING_CONFIG["min_score"] >= SCORING_CONFIG["max_score"]:
        errors.append("SCORING_CONFIG.min_score must be < max_score")

    # Scoring adjustments: all three tiers must have same keys
    early_keys = set(SCORING_ADJUSTMENTS_EARLY.keys())
    growing_keys = set(SCORING_ADJUSTMENTS_GROWING.keys())
    mature_keys = set(SCORING_ADJUSTMENTS_MATURE.keys())
    if early_keys != growing_keys:
        errors.append(f"SCORING_ADJUSTMENTS key mismatch: EARLY vs GROWING diff={early_keys ^ growing_keys}")
    if early_keys != mature_keys:
        errors.append(f"SCORING_ADJUSTMENTS key mismatch: EARLY vs MATURE diff={early_keys ^ mature_keys}")

    # All scoring thresholds must be numeric
    for key, val in SCORING_THRESHOLDS.items():
        if not isinstance(val, (int, float)):
            errors.append(f"SCORING_THRESHOLDS.{key}: expected number, got {type(val).__name__}")

    return errors


# Run validation on import — print warnings but don't crash
_config_errors = validate_config()
if _config_errors:
    import sys
    print(f"[Config] WARNING: {len(_config_errors)} validation error(s):", file=sys.stderr)
    for err in _config_errors:
        print(f"  - {err}", file=sys.stderr)

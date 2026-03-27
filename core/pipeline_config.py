"""
Pipeline configuration — edit these instead of modifying agent code.
Import with: from pipeline_config import * (or specific values)
"""

import os
from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# Voice settings
NARRATOR_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George
QUOTE_VOICE_ID = "pNInz6obpgDQGcFmaJgB"      # Adam
VOICE_BODY = {"stability": 0.38, "similarity_boost": 0.82, "style": 0.60, "use_speaker_boost": True}
VOICE_HOOK = {"stability": 0.28, "similarity_boost": 0.85, "style": 0.75, "use_speaker_boost": True}
VOICE_QUOTE = {"stability": 0.50, "similarity_boost": 0.75, "style": 0.40, "use_speaker_boost": True}
VOICE_SPEED_BODY = 0.76
VOICE_SPEED_HOOK = 0.82
VOICE_SPEED_QUOTE = 0.74

# Image generation
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "recraft")  # "recraft" or "flux"
IMAGE_QUALITY_THRESHOLD = 7  # Reject images scored below this (1-10)
IMAGE_MAX_RETRIES = 3        # Regenerate up to N times if quality is low

# Script constraints
SCRIPT_MIN_WORDS = 1000
SCRIPT_MAX_WORDS = 2500
SHORT_SCRIPT_MIN_WORDS = 80
SHORT_SCRIPT_MAX_WORDS = 180

# Video rendering
VIDEO_FPS = 30
VIDEO_CRF = 15  # Lower = higher quality (0-51 scale). YouTube re-encodes, so 15 gives it more data.
LONG_VIDEO_WIDTH = 1920
LONG_VIDEO_HEIGHT = 1080
SHORT_VIDEO_WIDTH = 1080
SHORT_VIDEO_HEIGHT = 1920

# Scene splitting
MAX_SCENE_SECONDS = 12.0

# Audio
AUDIO_CHUNK_MAX_CHARS = 500
AUDIO_TAIL_BUFFER_SEC = 1.5

# Scheduling (cron-like, 24h UTC)
SCHEDULE_TOPIC_DISCOVERY = {"day": "monday", "hour": 8}
SCHEDULE_PIPELINE = {"day": "tuesday", "hour": 9}
SCHEDULE_ANALYTICS = {"hour": 6}

# Quality gates
MIN_RESEARCH_FACTS = 5
MIN_RESEARCH_FIGURES = 2
MIN_TAGS = 5
MIN_SCENES = 5
MIN_AUDIO_DURATION = 300
MAX_AUDIO_DURATION = 1200
MIN_VIDEO_SIZE_MB = 50

# WPM gate enforcement (off by default — enable when speed tuning is validated)
ENFORCE_WPM_GATE = os.getenv("ENFORCE_WPM_GATE", "false").lower() == "true"

# Cost budget — maximum USD spend per pipeline run
# Pipeline aborts after completing the current stage if this threshold is exceeded.
# Set to 0 to disable budget enforcement.
COST_BUDGET_MAX_USD = float(os.getenv("COST_BUDGET_MAX_USD", "0"))

# Storage cleanup (after successful YouTube upload)
# Intermediate media files (frames, chunks, raw video) are deleted to reclaim disk.
# State files are KEPT — they feed the optimizer's cross-run trend analysis.
# Set to False to keep all media (useful for debugging).
CLEANUP_AFTER_UPLOAD = True
# Max total size (GB) for outputs/ before health check warns
CLEANUP_WARN_DISK_GB = 50  # Railway plan: 100 GB shared disk

# API retry settings
API_MAX_RETRIES = 5
API_BACKOFF_BASE = 2  # seconds, doubles each retry
API_TIMEOUT = 120     # seconds

# Webhook security
WEBHOOK_MAX_TRIGGERS_PER_HOUR = 3
WEBHOOK_MAX_CALLS_PER_MINUTE = 10

# Discord notifications
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Dashboard authentication (leave empty to disable login requirement)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

# ── Topic Discovery Scoring ─────────────────────────────────────────────────
SCORING_CONFIG = {
    "maturity_threshold": 15,           # Videos needed before channel is "mature"
    "max_score": 1.0,
    "min_score": 0.0,
    "default_topic_score": 0.5,
    "max_topics_per_discovery": 20,
    "experiment_cadence_default": 5,
    "experiment_cadence_throttled": 8,
}

# Dynamic adjustment magnitudes by channel maturity tier
# Keys: era_fatigue, audience_request, trending, cost_efficiency, shorts_subs,
#        search_demand, engagement, subscriber_conversion, traffic_source,
#        content_pattern, demographic_alignment
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
# Internal thresholds for each scoring signal function.
# Defaults come from youtube_knowledge_base.py benchmarks for history/edu channels.
# As your channel grows, override these based on your own analytics data.
SCORING_THRESHOLDS = {
    # -- Subscriber conversion --
    # YouTube avg sub rate: 0.3% for long-form, 0.1% for shorts (knowledge base)
    # "high" = 1.5x your channel avg; starts data-driven once analytics accumulate
    "sub_conversion_high_multiplier": 1.5,

    # -- Engagement --
    # Avg retention for edu channels: 42-48% (knowledge base by video length)
    # Signal fires when era retention > channel average; this sets minimum videos
    "engagement_min_video_count": 1,

    # -- Search demand --
    # YouTube search drives ~20% of traffic for edu channels (knowledge base)
    # Require 2+ keyword matches with 4+ char words to avoid noise
    "search_demand_min_word_len": 4,
    "search_demand_min_matches": 2,

    # -- Traffic source dominance --
    # Knowledge base: browse ~40%, suggested ~30%, search ~20%, external ~10%
    # "Dominant" = significantly above baseline distribution
    "traffic_search_dominant_pct": 50,     # 2.5x normal search share
    "traffic_browse_dominant_pct": 50,     # 1.25x normal browse share
    "traffic_suggested_dominant_pct": 40,  # 1.33x normal suggested share
    "traffic_min_specificity_signals": 2,
    "traffic_min_click_signals": 2,

    # -- Demographic alignment --
    # Only boost for audience segments that are >= this % of total viewers
    "demographic_min_audience_pct": 20,

    # -- Topic quality scoring --
    # Proper nouns: specific names/places increase searchability & CTR
    "quality_min_proper_nouns": 2,
    "quality_proper_noun_bonus": 0.05,
    "quality_no_proper_noun_penalty": -0.05,
    # Dates/numbers: add specificity (knowledge base: specific titles get higher CTR)
    "quality_date_bonus": 0.03,
    # Comparison format: "vs" titles get high engagement (knowledge base)
    "quality_comparison_bonus": 0.05,
    # Emotional words: dark/shocking/secret drive CTR in this niche
    "quality_min_emotional_words": 2,
    "quality_emotional_high_bonus": 0.05,   # 2+ emotional words
    "quality_emotional_low_bonus": 0.02,    # 1 emotional word
    # Broad topic penalty
    "quality_broad_penalty": -0.10,
    # Title length: knowledge base says 7-11 words, 45-65 chars is optimal
    "quality_min_title_words": 3,
    "quality_max_title_words": 15,
    "quality_title_length_penalty": -0.05,
    # Quality multiplier clamp range
    "quality_multiplier_min": 0.8,
    "quality_multiplier_max": 1.2,

    # -- Experiment strategy --
    # Eras with fewer than this many videos are "underexplored"
    "experiment_underexplored_videos": 3,

    # -- Queue management --
    # When queue is below low threshold, generate max topics
    # When above high threshold, generate half
    "queue_low_threshold": 5,
    "queue_high_threshold": 15,
    "queue_medium_ratio": 0.75,
    "queue_high_ratio": 0.50,
    "queue_minimum_topics": 10,

    # -- Word matching --
    # Minimum characters for a word to count as "significant" in matching
    "matching_min_word_len": 4,
    # Minimum word matches OR one long word (6+ chars) for audience/trending match
    "matching_min_word_matches": 2,
    "matching_long_word_len": 6,

    # -- Competitive intelligence --
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

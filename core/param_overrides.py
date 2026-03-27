"""
Parameter override system for the Obsidian pipeline.
Reads approved overrides from Supabase `tuning_overrides` table.
Pipeline code uses get_override(key, default) to get the active value.

Architecture:
  - Pipeline uses _pipeline_cache (loaded once at start, never reset by dashboard)
  - Dashboard uses _dashboard_cache (reset on approve/revert, 5s TTL)
  - save_override() validates against PARAM_BOUNDS before writing
  - revert_override() soft-deletes via reverted_at timestamp
"""

import time
from datetime import datetime, timezone

# ── Parameter bounds: authoritative source for all tunable params ─────────────
# Keys must exactly match what pipeline code passes to get_override()

PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    # Long-form Python-side params (Phase A)
    "voice_speed.quote":           (0.60, 0.90),
    "voice_speed.quote_legacy":    (0.70, 0.95),
    "pause.reveal":                (0.5, 5.0),
    "pause.breathing":             (0.3, 3.0),
    "pause.act_transition":        (0.2, 2.0),
    "pause.default":               (0.1, 1.5),
    # Shorts Python-side params (Phase A)
    "short.voice_speed":           (0.78, 1.02),
    "short.hook_speed":            (0.82, 1.05),
    "short.voice_stability":       (0.20, 0.55),
    "short.voice_style":           (0.30, 0.85),
    "short.hook_stability":        (0.15, 0.45),
    "short.hook_style":            (0.40, 0.95),
    "short.similarity_boost":      (0.65, 0.95),
    "short.hook_similarity_boost": (0.70, 0.98),
    "short.tail_buffer_sec":       (0.3, 2.5),
    # TS-side params (Phase B — registered for future use)
    "ducking.speech_volume":       (0.03, 0.15),
    "ducking.silence_volume":      (0.20, 0.50),
    "ducking.ramp_seconds":        (0.35, 1.0),
    "volume.act1":                 (0.50, 1.00),
    "volume.act2":                 (0.80, 1.50),
    "volume.act3":                 (0.30, 0.90),
    "volume.ending":               (1.00, 1.60),
    "short.music_speech_vol":      (0.03, 0.25),
    "short.music_silent_vol":      (0.10, 0.45),
}

PARAM_DEFAULTS: dict[str, float] = {
    "voice_speed.quote": 0.74,
    "voice_speed.quote_legacy": 0.85,
    "pause.reveal": 1.8,
    "pause.breathing": 1.2,
    "pause.act_transition": 0.9,
    "pause.default": 0.4,
    "short.voice_speed": 0.88,
    "short.hook_speed": 0.92,
    "short.voice_stability": 0.38,
    "short.voice_style": 0.60,
    "short.hook_stability": 0.28,
    "short.hook_style": 0.75,
    "short.similarity_boost": 0.82,
    "short.hook_similarity_boost": 0.85,
    "short.tail_buffer_sec": 1.5,
    "ducking.speech_volume": 0.08,
    "ducking.silence_volume": 0.38,
    "ducking.ramp_seconds": 0.5,
    "volume.act1": 0.80,
    "volume.act2": 1.20,
    "volume.act3": 0.60,
    "volume.ending": 1.40,
    "short.music_speech_vol": 0.12,
    "short.music_silent_vol": 0.25,
}

# Minimum perceptual step sizes (below these, changes are inaudible)
PARAM_MIN_STEP: dict[str, float] = {
    "voice_speed.quote": 0.02,
    "voice_speed.quote_legacy": 0.02,
    "pause.reveal": 0.1,
    "pause.breathing": 0.1,
    "pause.act_transition": 0.1,
    "pause.default": 0.05,
    "short.voice_speed": 0.02,
    "short.hook_speed": 0.02,
    "short.voice_stability": 0.05,
    "short.voice_style": 0.05,
    "short.hook_stability": 0.05,
    "short.hook_style": 0.05,
    "short.similarity_boost": 0.03,
    "short.hook_similarity_boost": 0.03,
    "short.tail_buffer_sec": 0.1,
    "short.music_speech_vol": 0.02,
    "short.music_silent_vol": 0.02,
}

# Brand consistency: shorts params that should stay within threshold of LF defaults
BRAND_CONSISTENCY_PAIRS: dict[str, tuple[str, float]] = {
    # shorts_key -> (long_form_default_key_or_value, max_drift)
    "short.voice_stability": ("long_form_default", 0.15),
    "short.voice_style": ("long_form_default", 0.15),
    "short.similarity_boost": ("long_form_default", 0.10),
}


# ── Supabase interaction ─────────────────────────────────────────────────────

def _fetch_from_supabase() -> dict:
    """Fetch active (non-reverted) overrides from Supabase. Returns {key: float}."""
    try:
        from clients.supabase_client import get_client
        sb = get_client()
        resp = sb.table("tuning_overrides") \
            .select("param_key, value") \
            .is_("reverted_at", "null") \
            .execute()
        return {row["param_key"]: float(row["value"]) for row in (resp.data or [])}
    except Exception as e:
        print(f"[Overrides] Supabase unavailable, using defaults: {e}")
        return {}


# ── Dual cache: pipeline vs dashboard ─────────────────────────────────────────
# Pipeline cache: loaded once at pipeline start, never reset by dashboard saves.
# Dashboard cache: reset on approve/revert, 5s TTL to avoid Supabase spam.

_pipeline_cache: dict | None = None
_dashboard_cache: dict | None = None
_dashboard_cache_time: float = 0


def load_overrides_for_pipeline() -> dict:
    """Called once at pipeline start. Cached for entire run."""
    global _pipeline_cache
    if _pipeline_cache is not None:
        return _pipeline_cache
    _pipeline_cache = _fetch_from_supabase()
    return _pipeline_cache


def load_overrides() -> dict:
    """Called by dashboard API. Has 5-second TTL cache."""
    global _dashboard_cache, _dashboard_cache_time
    now = time.time()
    if _dashboard_cache is not None and now - _dashboard_cache_time < 5:
        return _dashboard_cache
    _dashboard_cache = _fetch_from_supabase()
    _dashboard_cache_time = now
    return _dashboard_cache


def get_override(key: str, default: float) -> float:
    """
    Return the active override value for a parameter, or the default.
    Used by pipeline code. Reads from pipeline cache (loaded once at start).
    Never crashes — returns default on any error.
    """
    cache = _pipeline_cache if _pipeline_cache is not None else _fetch_from_supabase()
    val = cache.get(key, default)
    # Clamp to safety bounds
    if key in PARAM_BOUNDS:
        lo, hi = PARAM_BOUNDS[key]
        val = max(lo, min(hi, val))
    return val


def reset_pipeline_cache():
    """Called at pipeline start to load fresh values for the run."""
    global _pipeline_cache
    _pipeline_cache = None


def reset_dashboard_cache():
    """Called after approve/revert to force fresh read on next dashboard load."""
    global _dashboard_cache, _dashboard_cache_time
    _dashboard_cache = None
    _dashboard_cache_time = 0


# ── Save / Revert ────────────────────────────────────────────────────────────

def save_override(key: str, value: float, approved_by: str = "dashboard"):
    """
    Save a parameter override to Supabase. Validates bounds and constraints.
    Raises ValueError if validation fails.
    """
    if key not in PARAM_BOUNDS:
        raise ValueError(f"Unknown parameter: {key}")
    lo, hi = PARAM_BOUNDS[key]
    if not (lo <= value <= hi):
        raise ValueError(f"Value {value} outside bounds [{lo}, {hi}] for {key}")

    # Hook-vs-body contrast validation for shorts
    if key == "short.hook_stability":
        body_stab = get_override("short.voice_stability", 0.38)
        if value > body_stab - 0.05:
            raise ValueError(
                f"Hook stability ({value}) must be at least 0.05 below body ({body_stab})"
            )
    if key == "short.hook_style":
        body_style = get_override("short.voice_style", 0.60)
        if value < body_style + 0.05:
            raise ValueError(
                f"Hook style ({value}) must be at least 0.05 above body ({body_style})"
            )

    previous = get_override(key, PARAM_DEFAULTS.get(key, value))

    from clients.supabase_client import get_client
    get_client().table("tuning_overrides").upsert(
        {
            "param_key": key,
            "value": value,
            "previous_value": previous,
            "approved_by": approved_by,
            "reverted_at": None,
        },
        on_conflict="param_key",
    ).execute()
    reset_dashboard_cache()


def revert_override(key: str):
    """Soft-delete an override by setting reverted_at. Preserves history."""
    from clients.supabase_client import get_client
    get_client().table("tuning_overrides").update(
        {"reverted_at": datetime.now(timezone.utc).isoformat()}
    ).eq("param_key", key).is_("reverted_at", "null").execute()
    reset_dashboard_cache()


# ── Compound safety check ────────────────────────────────────────────────────

def quick_compound_check(proposed_overrides: dict[str, float]) -> str | None:
    """
    Lightweight check: does the combination of overrides produce inaudible music?
    Input: {param_key: float_value} — all currently approved + proposed change.
    Returns warning string if problematic, None if OK.
    """
    for act in ["act1", "act2", "act3", "ending"]:
        act_mul = proposed_overrides.get(
            f"volume.{act}",
            PARAM_DEFAULTS.get(f"volume.{act}", 1.0),
        )
        duck = proposed_overrides.get(
            "ducking.speech_volume",
            PARAM_DEFAULTS.get("ducking.speech_volume", 0.08),
        )
        pos = proposed_overrides.get(
            f"position_volume.{act}",
            0.50,  # default from scene_intent.py
        )
        compound = act_mul * duck * pos
        if compound < 0.01:
            return (
                f"Music inaudible during {act}: "
                f"{act_mul:.2f} × {duck:.2f} × {pos:.2f} = {compound:.4f}"
            )
    return None

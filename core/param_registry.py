"""
Expanded parameter registry for the Obsidian pipeline optimizer.

Wraps param_overrides.py and adds metadata for ~85 tunable parameters.
Single source of truth — if a param is in PARAM_BOUNDS but not here,
build_registry() raises ValueError at import time.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.param_overrides import (
    PARAM_BOUNDS,
    PARAM_DEFAULTS,
    PARAM_MIN_STEP,
    get_override,
)


@dataclass(frozen=True)
class ParamSpec:
    key: str
    category: str       # "voice", "music", "pacing", "image", "shorts"
    bounds: tuple[float, float]
    default: float
    min_step: float
    affects_format: str  # "long", "short", "both"
    learnable: bool      # False → optimizer never auto-tunes this
    ts_side: bool        # True → consumed by Remotion (TypeScript)


# ── Extended parameter definitions ──────────────────────────────────────────
# These define NEW params not yet in PARAM_BOUNDS.
# Voice mood settings (8 moods × 4 tunable params = 32)
_MOODS = ["dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"]
_MOOD_DEFAULTS = {
    "dark":      {"stability": 0.32, "similarity_boost": 0.82, "style": 0.55, "speed": 0.76},
    "tense":     {"stability": 0.28, "similarity_boost": 0.82, "style": 0.65, "speed": 0.84},
    "dramatic":  {"stability": 0.25, "similarity_boost": 0.85, "style": 0.80, "speed": 0.74},
    "cold":      {"stability": 0.55, "similarity_boost": 0.82, "style": 0.25, "speed": 0.80},
    "reverent":  {"stability": 0.48, "similarity_boost": 0.82, "style": 0.35, "speed": 0.72},
    "wonder":    {"stability": 0.35, "similarity_boost": 0.82, "style": 0.55, "speed": 0.78},
    "warmth":    {"stability": 0.42, "similarity_boost": 0.82, "style": 0.50, "speed": 0.76},
    "absurdity": {"stability": 0.28, "similarity_boost": 0.82, "style": 0.70, "speed": 0.82},
}
_MOOD_PARAM_BOUNDS = {
    "stability":       (0.15, 0.70),
    "similarity_boost": (0.70, 0.95),
    "style":           (0.10, 0.95),
    "speed":           (0.65, 0.95),
}
_MOOD_MIN_STEPS = {
    "stability": 0.03,
    "similarity_boost": 0.02,
    "style": 0.05,
    "speed": 0.02,
}

# Narrative arc modulation deltas (5 positions × 3 deltas = 15)
_ARC_POSITIONS = ["hook", "act1", "act2", "act3", "ending"]
_ARC_DELTA_DEFAULTS = {
    "hook":   {"stability_delta": -0.08, "style_delta": 0.15, "speed_delta": 0.08},
    "act1":   {"stability_delta": 0.04, "style_delta": 0.00, "speed_delta": -0.02},
    "act2":   {"stability_delta": -0.04, "style_delta": 0.08, "speed_delta": 0.02},
    "act3":   {"stability_delta": -0.06, "style_delta": 0.12, "speed_delta": -0.06},
    "ending": {"stability_delta": 0.12, "style_delta": 0.05, "speed_delta": -0.08},
}
_ARC_DELTA_BOUNDS = {
    "stability_delta": (-0.15, 0.20),
    "style_delta":     (-0.25, 0.25),
    "speed_delta":     (-0.15, 0.15),
}
_ARC_MIN_STEPS = {
    "stability_delta": 0.02,
    "style_delta": 0.03,
    "speed_delta": 0.02,
}

# Reveal/breathing modifier deltas (2 × 3 = 6)
_MODIFIER_DEFAULTS = {
    "reveal":    {"stability_delta": -0.05, "style_delta": 0.15, "speed_delta": -0.08},
    "breathing": {"stability_delta": 0.15, "style_delta": -0.20, "speed_delta": -0.12},
}
_MODIFIER_BOUNDS = _ARC_DELTA_BOUNDS
_MODIFIER_MIN_STEPS = _ARC_MIN_STEPS

# Act boundaries (3 params)
_ACT_BOUNDARY_SPECS = {
    "act_boundary.act2_start":   (0.15, 0.35, 0.25, 0.02),
    "act_boundary.act3_start":   (0.50, 0.80, 0.65, 0.03),
    "act_boundary.ending_start": (0.80, 0.95, 0.90, 0.02),
}


def _build_extended_specs() -> list[ParamSpec]:
    """Build ParamSpec entries for all extended (new) parameters."""
    specs: list[ParamSpec] = []

    # Voice mood params
    for mood in _MOODS:
        for param, (lo, hi) in _MOOD_PARAM_BOUNDS.items():
            key = f"voice.mood.{mood}.{param}"
            specs.append(ParamSpec(
                key=key,
                category="voice",
                bounds=(lo, hi),
                default=_MOOD_DEFAULTS[mood][param],
                min_step=_MOOD_MIN_STEPS[param],
                affects_format="long",
                learnable=True,
                ts_side=False,
            ))

    # Narrative arc modulation deltas
    for pos in _ARC_POSITIONS:
        for delta_name, (lo, hi) in _ARC_DELTA_BOUNDS.items():
            key = f"voice.arc.{pos}.{delta_name}"
            specs.append(ParamSpec(
                key=key,
                category="voice",
                bounds=(lo, hi),
                default=_ARC_DELTA_DEFAULTS[pos][delta_name],
                min_step=_ARC_MIN_STEPS[delta_name],
                affects_format="long",
                learnable=True,
                ts_side=False,
            ))

    # Reveal/breathing modifiers
    for mod_type in ("reveal", "breathing"):
        for delta_name, (lo, hi) in _MODIFIER_BOUNDS.items():
            key = f"voice.modifier.{mod_type}.{delta_name}"
            specs.append(ParamSpec(
                key=key,
                category="voice",
                bounds=(lo, hi),
                default=_MODIFIER_DEFAULTS[mod_type][delta_name],
                min_step=_MODIFIER_MIN_STEPS[delta_name],
                affects_format="long",
                learnable=True,
                ts_side=False,
            ))

    # Act boundaries
    for key, (lo, hi, default, step) in _ACT_BOUNDARY_SPECS.items():
        specs.append(ParamSpec(
            key=key,
            category="music",
            bounds=(lo, hi),
            default=default,
            min_step=step,
            affects_format="long",
            learnable=True,
            ts_side=True,
        ))

    return specs


# ── Category/format inference for existing PARAM_BOUNDS keys ────────────────

def _infer_category(key: str) -> str:
    if key.startswith("voice") or key.startswith("short.voice") or key.startswith("short.hook"):
        return "voice"
    if key.startswith("pause") or key.startswith("short.tail"):
        return "pacing"
    if key.startswith("ducking") or key.startswith("volume") or key.startswith("short.music"):
        return "music"
    return "voice"


def _infer_format(key: str) -> str:
    if key.startswith("short."):
        return "short"
    if key.startswith("ducking.") or key.startswith("volume."):
        return "both"
    return "long"


def _infer_ts_side(key: str) -> bool:
    return key.startswith("ducking.") or key.startswith("volume.") or key.startswith("short.music")


# ── Registry builder ────────────────────────────────────────────────────────

_registry_cache: dict[str, ParamSpec] | None = None


def build_registry() -> dict[str, ParamSpec]:
    """Build the complete parameter registry.

    Merges existing PARAM_BOUNDS entries with extended specs.
    Raises ValueError if a PARAM_BOUNDS key has no corresponding registry entry.
    """
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    registry: dict[str, ParamSpec] = {}

    # 1. Register all existing PARAM_BOUNDS keys
    for key, (lo, hi) in PARAM_BOUNDS.items():
        default = PARAM_DEFAULTS.get(key, (lo + hi) / 2)
        step = PARAM_MIN_STEP.get(key, (hi - lo) * 0.05)
        registry[key] = ParamSpec(
            key=key,
            category=_infer_category(key),
            bounds=(lo, hi),
            default=default,
            min_step=step,
            affects_format=_infer_format(key),
            learnable=True,
            ts_side=_infer_ts_side(key),
        )

    # 2. Add extended specs (voice mood, arc, modifiers, act boundaries)
    for spec in _build_extended_specs():
        if spec.key in registry:
            raise ValueError(f"Duplicate param key: {spec.key}")
        registry[spec.key] = spec

    # 3. Validate consistency
    for key in PARAM_BOUNDS:
        if key not in registry:
            raise ValueError(
                f"PARAM_BOUNDS key '{key}' not in registry — this is a bug in param_registry.py"
            )

    _registry_cache = registry
    return registry


def get_active_params(format: str = "long") -> dict[str, float]:
    """Return current active value for every registered param.

    Uses override if set, else default. Filtered by format ("long", "short", "both").
    """
    registry = build_registry()
    result: dict[str, float] = {}
    for key, spec in registry.items():
        if format == "both" or spec.affects_format == "both" or spec.affects_format == format:
            result[key] = get_override(key, spec.default)
    return result


def get_learnable_params(format: str = "long") -> list[str]:
    """Return keys of all learnable params for the given format."""
    registry = build_registry()
    return [
        key for key, spec in registry.items()
        if spec.learnable
        and (format == "both" or spec.affects_format == "both" or spec.affects_format == format)
    ]


def reset_registry_cache():
    """Reset the cached registry (call when param_overrides change)."""
    global _registry_cache
    _registry_cache = None

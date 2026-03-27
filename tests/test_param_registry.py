"""Tests for core/param_registry.py — parameter registry consistency."""

import pytest
from core.param_registry import (
    build_registry,
    get_active_params,
    get_learnable_params,
    reset_registry_cache,
)
from core.param_overrides import PARAM_BOUNDS, PARAM_DEFAULTS, PARAM_MIN_STEP


@pytest.fixture(autouse=True)
def _reset():
    reset_registry_cache()
    yield
    reset_registry_cache()


def test_all_param_bounds_in_registry():
    """Every key in PARAM_BOUNDS must have a registry entry."""
    registry = build_registry()
    for key in PARAM_BOUNDS:
        assert key in registry, f"PARAM_BOUNDS key '{key}' missing from registry"


def test_no_duplicate_keys():
    """All keys must be unique (build_registry raises on duplicates)."""
    registry = build_registry()
    assert len(registry) == len(set(registry.keys()))


def test_defaults_within_bounds():
    """Every default value must be within its bounds."""
    registry = build_registry()
    for key, spec in registry.items():
        lo, hi = spec.bounds
        assert lo <= spec.default <= hi, (
            f"{key}: default {spec.default} outside bounds [{lo}, {hi}]"
        )


def test_min_step_smaller_than_range():
    """min_step must be smaller than the parameter range."""
    registry = build_registry()
    for key, spec in registry.items():
        rng = spec.bounds[1] - spec.bounds[0]
        assert spec.min_step < rng, (
            f"{key}: min_step {spec.min_step} >= range {rng}"
        )


def test_min_step_positive():
    """All min_steps must be positive."""
    registry = build_registry()
    for key, spec in registry.items():
        assert spec.min_step > 0, f"{key}: min_step must be positive, got {spec.min_step}"


def test_categories_valid():
    """All categories must be in the allowed set."""
    allowed = {"voice", "music", "pacing", "image", "shorts"}
    registry = build_registry()
    for key, spec in registry.items():
        assert spec.category in allowed, (
            f"{key}: category '{spec.category}' not in {allowed}"
        )


def test_formats_valid():
    """affects_format must be 'long', 'short', or 'both'."""
    registry = build_registry()
    for key, spec in registry.items():
        assert spec.affects_format in ("long", "short", "both"), (
            f"{key}: affects_format '{spec.affects_format}' invalid"
        )


def test_registry_size():
    """Registry should have at least the 24 existing params + extended ones."""
    registry = build_registry()
    assert len(registry) >= 24, f"Registry has only {len(registry)} params"
    # Expected: 24 existing + 32 mood + 15 arc + 6 modifier + 3 boundary = ~80
    assert len(registry) >= 75, f"Expected ~80+ params, got {len(registry)}"


def test_existing_params_preserved():
    """Existing PARAM_BOUNDS entries must have correct bounds/defaults/steps."""
    registry = build_registry()
    for key in PARAM_BOUNDS:
        spec = registry[key]
        assert spec.bounds == PARAM_BOUNDS[key], f"{key}: bounds mismatch"
        if key in PARAM_DEFAULTS:
            assert spec.default == PARAM_DEFAULTS[key], f"{key}: default mismatch"
        if key in PARAM_MIN_STEP:
            assert spec.min_step == PARAM_MIN_STEP[key], f"{key}: min_step mismatch"


def test_mood_params_registered():
    """All 8 moods × 4 params should be registered."""
    registry = build_registry()
    moods = ["dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"]
    params = ["stability", "similarity_boost", "style", "speed"]
    for mood in moods:
        for param in params:
            key = f"voice.mood.{mood}.{param}"
            assert key in registry, f"Missing mood param: {key}"
            assert registry[key].category == "voice"
            assert registry[key].affects_format == "long"


def test_arc_params_registered():
    """All 5 positions × 3 deltas should be registered."""
    registry = build_registry()
    positions = ["hook", "act1", "act2", "act3", "ending"]
    deltas = ["stability_delta", "style_delta", "speed_delta"]
    for pos in positions:
        for delta in deltas:
            key = f"voice.arc.{pos}.{delta}"
            assert key in registry, f"Missing arc param: {key}"


def test_get_active_params_returns_all():
    """get_active_params should return values for all registered params."""
    params = get_active_params(format="both")
    registry = build_registry()
    assert len(params) == len(registry)


def test_get_learnable_params():
    """get_learnable_params should return only learnable params."""
    learnable = get_learnable_params(format="both")
    registry = build_registry()
    for key in learnable:
        assert registry[key].learnable is True


def test_registry_is_cached():
    """build_registry() should return same dict on repeated calls."""
    r1 = build_registry()
    r2 = build_registry()
    assert r1 is r2


def test_reset_cache_clears():
    """reset_registry_cache should force rebuild."""
    r1 = build_registry()
    reset_registry_cache()
    r2 = build_registry()
    assert r1 is not r2
    assert len(r1) == len(r2)

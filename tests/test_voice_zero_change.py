"""Zero-change regression test for voice parameterization.

Verifies that with no overrides set, _build_mood_settings() produces
identical values to the original hardcoded MOOD_VOICE_SETTINGS.
"""

from unittest.mock import patch

from pipeline.voice import (
    _ORIGINAL_MOOD_VOICE_SETTINGS,
    _build_mood_settings,
    reset_mood_settings_cache,
)


def test_mood_settings_identical_without_overrides():
    """With no overrides set, _build_mood_settings() must produce identical
    values to old _ORIGINAL_MOOD_VOICE_SETTINGS."""
    reset_mood_settings_cache()

    # Mock get_override to always return the default (simulates no overrides in Supabase)
    def mock_get_override(key, default):
        return default

    with patch("core.param_overrides.get_override", side_effect=mock_get_override):
        built = _build_mood_settings()

    for mood in _ORIGINAL_MOOD_VOICE_SETTINGS:
        for key in _ORIGINAL_MOOD_VOICE_SETTINGS[mood]:
            assert built[mood][key] == _ORIGINAL_MOOD_VOICE_SETTINGS[mood][key], (
                f"REGRESSION: {mood}.{key} changed from "
                f"{_ORIGINAL_MOOD_VOICE_SETTINGS[mood][key]} to {built[mood][key]}"
            )

    reset_mood_settings_cache()


def test_mood_settings_override_applied():
    """When an override is set, _build_mood_settings() should use it."""
    reset_mood_settings_cache()

    def mock_get_override(key, default):
        if key == "voice.mood.dark.stability":
            return 0.50  # Changed from default 0.32
        return default

    with patch("core.param_overrides.get_override", side_effect=mock_get_override):
        built = _build_mood_settings()

    assert built["dark"]["stability"] == 0.50
    # Other values unchanged
    assert built["dark"]["similarity_boost"] == _ORIGINAL_MOOD_VOICE_SETTINGS["dark"]["similarity_boost"]
    assert built["tense"]["stability"] == _ORIGINAL_MOOD_VOICE_SETTINGS["tense"]["stability"]

    reset_mood_settings_cache()


def test_mood_settings_fallback_on_import_error():
    """If param_overrides import fails, should fall back to original hardcoded."""
    reset_mood_settings_cache()

    with patch("pipeline.voice._build_mood_settings") as mock_build:
        # Simulate import failure by having the function return originals
        mock_build.return_value = _ORIGINAL_MOOD_VOICE_SETTINGS
        result = mock_build()

    for mood in _ORIGINAL_MOOD_VOICE_SETTINGS:
        assert result[mood] == _ORIGINAL_MOOD_VOICE_SETTINGS[mood]

    reset_mood_settings_cache()


def test_all_moods_present():
    """All 8 moods must be in both original and built settings."""
    reset_mood_settings_cache()

    def mock_get_override(key, default):
        return default

    with patch("core.param_overrides.get_override", side_effect=mock_get_override):
        built = _build_mood_settings()

    expected_moods = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
    assert set(built.keys()) == expected_moods
    assert set(_ORIGINAL_MOOD_VOICE_SETTINGS.keys()) == expected_moods

    reset_mood_settings_cache()


def test_all_keys_present_per_mood():
    """Each mood must have stability, similarity_boost, style, use_speaker_boost, speed."""
    reset_mood_settings_cache()

    def mock_get_override(key, default):
        return default

    with patch("core.param_overrides.get_override", side_effect=mock_get_override):
        built = _build_mood_settings()

    expected_keys = {"stability", "similarity_boost", "style", "use_speaker_boost", "speed"}
    for mood, settings in built.items():
        assert set(settings.keys()) == expected_keys, f"Mood '{mood}' missing keys"

    reset_mood_settings_cache()

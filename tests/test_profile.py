"""Tests for core/profile.py — content profile loader."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.profile import (
    get_profile,
    get_style_directive,
    get_profile_field,
    get_mood_palette,
    get_hook_registers,
    get_structure_types,
    reset_profile_cache,
    _load_profile,
    _resolve_profile_name,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset profile cache before each test."""
    reset_profile_cache()
    yield
    reset_profile_cache()


class TestResolveProfileName:
    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_PROFILE", "explainer")
        assert _resolve_profile_name() == "explainer"

    def test_defaults_to_documentary(self, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_PROFILE", raising=False)
        # If no config override, should default to documentary
        name = _resolve_profile_name()
        assert name in ("documentary", "documentary")  # May come from obsidian.yaml


class TestLoadProfile:
    def test_loads_documentary(self):
        profile = _load_profile("documentary")
        assert profile["name"] == "Documentary"
        assert "style_directive" in profile
        assert "cinematic" in profile["style_directive"].lower()

    def test_loads_explainer(self):
        profile = _load_profile("explainer")
        assert profile["name"] == "Explainer"
        assert "educational" in profile["style_directive"].lower()

    def test_loads_true_crime(self):
        profile = _load_profile("true_crime")
        assert profile["name"] == "True Crime"
        assert "investigation" in profile["style_directive"].lower()

    def test_loads_video_essay(self):
        profile = _load_profile("video_essay")
        assert profile["name"] == "Video Essay"
        assert "essay" in profile["style_directive"].lower()

    def test_nonexistent_falls_back_to_documentary(self):
        profile = _load_profile("nonexistent_profile_xyz")
        assert profile["name"] == "Documentary"

    def test_custom_profile_from_tempfile(self):
        custom = {
            "name": "My Custom",
            "style_directive": "CONTENT STYLE: Custom test style",
            "tone": {"primary": "test tone"},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=None) as f:
            yaml.dump(custom, f)
            f.flush()
            # Patch PROFILES_DIR to use the temp directory
            with patch("core.profile.PROFILES_DIR", Path(f.name).parent):
                profile = _load_profile(Path(f.name).stem)
        assert profile["name"] == "My Custom"
        assert "Custom test style" in profile["style_directive"]


class TestGetProfile:
    def test_returns_dict(self):
        profile = get_profile()
        assert isinstance(profile, dict)
        assert "name" in profile

    def test_caches_result(self):
        p1 = get_profile()
        p2 = get_profile()
        assert p1 is p2

    def test_reset_clears_cache(self):
        p1 = get_profile()
        reset_profile_cache()
        p2 = get_profile()
        assert p1 is not p2


class TestGetStyleDirective:
    def test_returns_string(self):
        directive = get_style_directive()
        assert isinstance(directive, str)
        assert len(directive) > 0

    def test_contains_content_style(self):
        directive = get_style_directive()
        assert "CONTENT STYLE:" in directive

    def test_contains_tone(self):
        directive = get_style_directive()
        assert "TONE:" in directive


class TestGetProfileField:
    def test_existing_field(self):
        result = get_profile_field("tone", "primary")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_missing_field_returns_default(self):
        result = get_profile_field("nonexistent", "key", "fallback")
        assert result == "fallback"

    def test_missing_key_in_section_returns_default(self):
        result = get_profile_field("tone", "nonexistent_key", "default_val")
        assert result == "default_val"


class TestGetMoodPalette:
    def test_returns_list(self):
        palette = get_mood_palette()
        assert isinstance(palette, list)
        assert len(palette) > 0

    def test_documentary_has_dark(self):
        palette = get_mood_palette()
        assert "dark" in palette


class TestGetHookRegisters:
    def test_returns_list(self):
        registers = get_hook_registers()
        assert isinstance(registers, list)
        assert len(registers) > 0


class TestGetStructureTypes:
    def test_returns_list(self):
        types = get_structure_types()
        assert isinstance(types, list)
        assert "CLASSIC" in types


class TestDNAIntegration:
    def test_style_directive_injected_into_dna(self):
        """get_dna() should prepend the profile's style directive."""
        from intel.dna_loader import get_dna
        dna = get_dna(["identity"])
        assert "CONTENT PROFILE" in dna
        assert "CONTENT STYLE:" in dna
        # Identity section should also be present
        assert "CHANNEL IDENTITY" in dna

    def test_dna_without_sections_still_has_profile(self):
        from intel.dna_loader import get_dna
        dna = get_dna([])
        assert "CONTENT PROFILE" in dna

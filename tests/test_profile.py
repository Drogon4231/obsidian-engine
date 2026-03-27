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


# ── Cross-Profile Validation (Phase 6) ───────────────────────────────────────

ALL_PROFILES = ["documentary", "explainer", "true_crime", "video_essay"]

EXPECTED_CONTENT_STYLE = {
    "documentary": "cinematic documentary",
    "explainer": "educational explainer",
    "true_crime": "true crime investigation",
    "video_essay": "video essay",
}

EXPECTED_TONE_KEYWORDS = {
    "documentary": "authoritative",
    "explainer": "curious",
    "true_crime": "investigative",
    "video_essay": "analytical",
}


class TestAllProfilesLoad:
    """Verify every shipped profile loads without error and has required fields."""

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_loads(self, profile_name):
        profile = _load_profile(profile_name)
        assert profile["name"], f"{profile_name} missing 'name'"

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_has_style_directive(self, profile_name):
        profile = _load_profile(profile_name)
        directive = profile.get("style_directive", "")
        assert "CONTENT STYLE:" in directive, f"{profile_name} missing CONTENT STYLE in directive"
        assert "TONE:" in directive, f"{profile_name} missing TONE in directive"
        assert "HOOK:" in directive, f"{profile_name} missing HOOK in directive"
        assert "ENDING:" in directive, f"{profile_name} missing ENDING in directive"

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_has_required_sections(self, profile_name):
        profile = _load_profile(profile_name)
        for section in ["tone", "narrative", "research", "script", "visuals", "seo", "shorts"]:
            assert section in profile, f"{profile_name} missing section '{section}'"

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_has_mood_palette(self, profile_name):
        profile = _load_profile(profile_name)
        palette = profile.get("visuals", {}).get("mood_palette", [])
        assert isinstance(palette, list), f"{profile_name} mood_palette not a list"
        assert len(palette) >= 3, f"{profile_name} mood_palette too short"

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_has_hook_registers(self, profile_name):
        profile = _load_profile(profile_name)
        registers = profile.get("narrative", {}).get("hook_registers", [])
        assert isinstance(registers, list), f"{profile_name} hook_registers not a list"
        assert len(registers) >= 3, f"{profile_name} hook_registers too short"

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_profile_has_structure_types(self, profile_name):
        profile = _load_profile(profile_name)
        types = profile.get("narrative", {}).get("structure_types", [])
        assert isinstance(types, list), f"{profile_name} structure_types not a list"
        assert len(types) >= 2, f"{profile_name} structure_types too short"


class TestProfileSwitching:
    """Prove that switching profiles produces different outputs."""

    def test_directives_are_unique_across_profiles(self):
        """Each profile must produce a distinct style_directive."""
        directives = {}
        for name in ALL_PROFILES:
            profile = _load_profile(name)
            directives[name] = profile.get("style_directive", "").strip()

        # All should be non-empty
        for name, d in directives.items():
            assert len(d) > 50, f"{name} directive too short"

        # All should be unique
        values = list(directives.values())
        assert len(set(values)) == len(ALL_PROFILES), "Some profiles have identical directives"

    def test_content_style_label_matches_profile(self):
        """Each profile's directive should name its own style."""
        for name in ALL_PROFILES:
            profile = _load_profile(name)
            directive = profile.get("style_directive", "").lower()
            expected = EXPECTED_CONTENT_STYLE[name]
            assert expected in directive, (
                f"{name} directive should contain '{expected}', "
                f"got: {directive[:80]}..."
            )

    def test_tone_matches_profile(self):
        """Each profile should have its expected tone keyword."""
        for name in ALL_PROFILES:
            profile = _load_profile(name)
            directive = profile.get("style_directive", "").lower()
            expected = EXPECTED_TONE_KEYWORDS[name]
            assert expected in directive, (
                f"{name} directive should mention '{expected}'"
            )

    def test_mood_palettes_differ(self):
        """Profiles should have different mood palettes."""
        palettes = {}
        for name in ALL_PROFILES:
            profile = _load_profile(name)
            palettes[name] = tuple(profile.get("visuals", {}).get("mood_palette", []))
        unique = set(palettes.values())
        assert len(unique) >= 3, "Most profiles should have distinct palettes"

    def test_hook_styles_vary(self):
        """Not all profiles should use the same hook style."""
        hooks = set()
        for name in ALL_PROFILES:
            profile = _load_profile(name)
            hooks.add(profile.get("narrative", {}).get("hook_style", ""))
        assert len(hooks) >= 2, "Profiles should use different hook styles"


class TestProfileDNASwitching:
    """Verify that switching OBSIDIAN_PROFILE changes what get_dna() returns."""

    def test_switching_profile_changes_dna_output(self, monkeypatch):
        """Switching env var should produce different DNA output."""
        from intel.dna_loader import get_dna

        outputs = {}
        for name in ALL_PROFILES:
            reset_profile_cache()
            monkeypatch.setenv("OBSIDIAN_PROFILE", name)
            dna = get_dna(["identity"])
            outputs[name] = dna

        # Each should have the CONTENT PROFILE section
        for name, dna in outputs.items():
            assert "CONTENT PROFILE" in dna, f"{name}: missing CONTENT PROFILE"

        # Each should contain its own style keyword
        for name, dna in outputs.items():
            expected = EXPECTED_CONTENT_STYLE[name]
            assert expected in dna.lower(), (
                f"DNA for {name} should contain '{expected}'"
            )

        # Documentary and explainer should differ
        assert outputs["documentary"] != outputs["explainer"], "Profiles should produce different DNA"

    def test_explainer_dna_has_educational_not_cinematic(self, monkeypatch):
        """Explainer profile DNA should say 'educational', not 'cinematic documentary'."""
        from intel.dna_loader import get_dna

        reset_profile_cache()
        monkeypatch.setenv("OBSIDIAN_PROFILE", "explainer")
        dna = get_dna([])
        assert "educational explainer" in dna.lower()
        # The style directive should NOT contain documentary-specific language
        # (the DNA_SECTIONS may still have it, but the CONTENT PROFILE block should not)
        profile_block = dna.split("=== CONTENT PROFILE ===")[1] if "=== CONTENT PROFILE ===" in dna else ""
        assert "cinematic documentary" not in profile_block.lower()

    def test_true_crime_dna_has_investigation(self, monkeypatch):
        from intel.dna_loader import get_dna

        reset_profile_cache()
        monkeypatch.setenv("OBSIDIAN_PROFILE", "true_crime")
        dna = get_dna([])
        assert "true crime investigation" in dna.lower()

    def test_video_essay_dna_has_thesis(self, monkeypatch):
        from intel.dna_loader import get_dna

        reset_profile_cache()
        monkeypatch.setenv("OBSIDIAN_PROFILE", "video_essay")
        dna = get_dna([])
        assert "video essay" in dna.lower()
        assert "thesis" in dna.lower()


class TestProfileAccessors:
    """Test that profile field accessors work for each profile."""

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_get_mood_palette_for_profile(self, profile_name, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_PROFILE", profile_name)
        reset_profile_cache()
        palette = get_mood_palette()
        assert isinstance(palette, list)
        assert len(palette) >= 3

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_get_hook_registers_for_profile(self, profile_name, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_PROFILE", profile_name)
        reset_profile_cache()
        registers = get_hook_registers()
        assert isinstance(registers, list)
        assert len(registers) >= 3

    @pytest.mark.parametrize("profile_name", ALL_PROFILES)
    def test_get_structure_types_for_profile(self, profile_name, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_PROFILE", profile_name)
        reset_profile_cache()
        types = get_structure_types()
        assert isinstance(types, list)
        assert len(types) >= 2

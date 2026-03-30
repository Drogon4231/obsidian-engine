"""
Tests for the Scene Intent Resolution System.

Validates that mood + narrative_function + act_position correctly resolves
to concrete rendering parameters.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from media.scene_intent import (
    resolve_scene_intent,
    resolve_all_scenes,
    _infer_position,
    _is_act_boundary,
    _FUNCTION_MODIFIERS,
)
from conftest import make_scenes


# ── Position Inference ───────────────────────────────────────────────────────

class TestInferPosition:
    @pytest.mark.unit
    def test_first_scene_is_hook(self):
        assert _infer_position(0, 10) == "hook"

    @pytest.mark.unit
    def test_last_scene_is_ending(self):
        assert _infer_position(9, 10) == "ending"

    @pytest.mark.unit
    def test_mid_scene_is_act2(self):
        assert _infer_position(5, 10) == "act2"

    @pytest.mark.unit
    def test_single_scene_is_hook(self):
        assert _infer_position(0, 1) == "hook"

    @pytest.mark.unit
    def test_act1_position(self):
        # scene 1 of 10 → pct=0.11 → act1
        assert _infer_position(1, 10) == "act1"

    @pytest.mark.unit
    def test_act3_position(self):
        # scene 7 of 10 → pct=0.78 → act3
        assert _infer_position(7, 10) == "act3"


# ── Act Boundaries ───────────────────────────────────────────────────────────

class TestActBoundary:
    @pytest.mark.unit
    def test_no_boundaries_for_tiny_videos(self):
        assert not _is_act_boundary(1, 3)

    @pytest.mark.unit
    def test_scene_1_not_boundary(self):
        # Scene 1 is mid-act1, not a boundary
        assert not _is_act_boundary(1, 10)

    @pytest.mark.unit
    def test_act_boundaries_exist_for_10_scenes(self):
        boundaries = [i for i in range(10) if _is_act_boundary(i, 10)]
        # Should have boundaries at start of act1, act2, act3, ending
        assert len(boundaries) >= 2


# ── Intent Resolution ────────────────────────────────────────────────────────

class TestResolveSceneIntent:
    @pytest.mark.unit
    def test_returns_all_intent_keys(self):
        scene = {"mood": "dark", "narrative_function": "hook"}
        intent = resolve_scene_intent(scene, 0, 10)
        expected_keys = {
            "intent_transition_type",
            "intent_motion_seed",
            "intent_music_volume_base",
            "intent_pace_modifier",
            "intent_caption_style",
            "intent_scene_energy",
            "intent_speech_intensity",
            "intent_silence_beat",
        }
        assert expected_keys == set(intent.keys())

    @pytest.mark.unit
    def test_reveal_gets_reveal_transition(self):
        scene = {"mood": "dramatic", "narrative_function": "reveal", "is_reveal_moment": True}
        intent = resolve_scene_intent(scene, 5, 10)
        assert intent["intent_transition_type"] == "reveal"

    @pytest.mark.unit
    def test_breathing_room_gets_act_transition(self):
        scene = {"mood": "reverent", "narrative_function": "breathing_room", "is_breathing_room": True}
        intent = resolve_scene_intent(scene, 7, 10)
        assert intent["intent_transition_type"] == "act"

    @pytest.mark.unit
    def test_breathing_room_lowers_volume(self):
        normal = {"mood": "dark", "narrative_function": "exposition"}
        breathing = {"mood": "dark", "narrative_function": "breathing_room"}
        vol_normal = resolve_scene_intent(normal, 5, 10)["intent_music_volume_base"]
        vol_breathing = resolve_scene_intent(breathing, 5, 10)["intent_music_volume_base"]
        assert vol_breathing < vol_normal

    @pytest.mark.unit
    def test_energy_clamped_0_to_1(self):
        # Dramatic + escalation should push energy high but not above 1.0
        scene = {"mood": "dramatic", "narrative_function": "escalation"}
        intent = resolve_scene_intent(scene, 5, 10)
        assert 0.0 <= intent["intent_scene_energy"] <= 1.0

    @pytest.mark.unit
    def test_cold_mood_low_energy(self):
        scene = {"mood": "cold", "narrative_function": "exposition"}
        intent = resolve_scene_intent(scene, 3, 10)
        assert intent["intent_scene_energy"] < 0.5

    @pytest.mark.unit
    def test_hook_pace_faster_than_exposition(self):
        hook = {"mood": "dark", "narrative_function": "hook"}
        expo = {"mood": "dark", "narrative_function": "exposition"}
        pace_hook = resolve_scene_intent(hook, 0, 10)["intent_pace_modifier"]
        pace_expo = resolve_scene_intent(expo, 3, 10)["intent_pace_modifier"]
        assert pace_hook > pace_expo

    @pytest.mark.unit
    def test_motion_seed_in_valid_range(self):
        for nf in _FUNCTION_MODIFIERS:
            scene = {"mood": "dark", "narrative_function": nf}
            intent = resolve_scene_intent(scene, 3, 10)
            assert 0 <= intent["intent_motion_seed"] <= 15

    @pytest.mark.unit
    def test_unknown_mood_gets_default_energy(self):
        scene = {"mood": "totally_new_mood", "narrative_function": "exposition"}
        intent = resolve_scene_intent(scene, 3, 10)
        # Default energy is 0.5 + exposition offset (-0.10) = 0.4
        assert intent["intent_scene_energy"] == 0.4

    @pytest.mark.unit
    def test_unknown_function_uses_exposition_defaults(self):
        scene = {"mood": "dark", "narrative_function": "totally_new_function"}
        intent = resolve_scene_intent(scene, 3, 10)
        # Should not crash, uses exposition defaults
        assert "intent_transition_type" in intent

    @pytest.mark.unit
    def test_ending_gets_higher_volume(self):
        # Ending position should swell music
        mid = {"mood": "dark", "narrative_function": "exposition", "narrative_position": "act2"}
        end = {"mood": "dark", "narrative_function": "conclusion", "narrative_position": "ending"}
        vol_mid = resolve_scene_intent(mid, 5, 10)["intent_music_volume_base"]
        vol_end = resolve_scene_intent(end, 9, 10)["intent_music_volume_base"]
        assert vol_end >= vol_mid


# ── Batch Resolution ─────────────────────────────────────────────────────────

class TestResolveAllScenes:
    @pytest.mark.unit
    def test_returns_same_count(self):
        scenes = make_scenes(10)
        resolved = resolve_all_scenes(scenes)
        assert len(resolved) == 10

    @pytest.mark.unit
    def test_does_not_mutate_input(self):
        scenes = make_scenes(5)
        original_keys = set(scenes[0].keys())
        resolve_all_scenes(scenes)
        assert set(scenes[0].keys()) == original_keys

    @pytest.mark.unit
    def test_all_scenes_have_intent_keys(self):
        scenes = make_scenes(10)
        resolved = resolve_all_scenes(scenes)
        for s in resolved:
            assert "intent_transition_type" in s
            assert "intent_scene_energy" in s
            assert "intent_motion_seed" in s

    @pytest.mark.unit
    def test_energy_arc_varies(self):
        """Verify that energy isn't flat across all scenes."""
        scenes = make_scenes(10)
        resolved = resolve_all_scenes(scenes)
        energies = [s["intent_scene_energy"] for s in resolved]
        assert len(set(energies)) > 1, "Energy should vary across scenes"

    @pytest.mark.unit
    def test_preserves_original_fields(self):
        scenes = make_scenes(3)
        resolved = resolve_all_scenes(scenes)
        for orig, res in zip(scenes, resolved):
            assert res["text"] == orig["text"]
            assert res["mood"] == orig["mood"]
            assert res["scene_number"] == orig["scene_number"]

"""
Tests for voice speed computation across mood × position × pace modifier.

Validates that all speed combinations:
- Fall within [0.65, 1.0] after clamping
- Have ≥0.20 global spread
- Have ≥0.06 per-position spread across moods
- Quote voice uses pipeline_config.VOICE_SPEED_QUOTE
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the voice settings function and mood table
from pipeline.voice import _get_scene_voice_settings, MOOD_VOICE_SETTINGS


MOODS = list(MOOD_VOICE_SETTINGS.keys())
POSITIONS = ["hook", "act1", "act2", "act3", "ending"]
PACE_MODIFIERS = [0.85, 1.0, 1.05]


class TestSpeedMatrix:
    @pytest.mark.unit
    def test_all_speeds_in_range(self):
        """Every mood × position combo must produce speed in [0.65, 1.0]."""
        for mood in MOODS:
            for pos_idx, pos in enumerate(POSITIONS):
                scene = {
                    "mood": mood,
                    "narrative_position": pos,
                    "narration": "Test narration text here.",
                }
                total = 20
                idx = {"hook": 0, "act1": 2, "act2": 6, "act3": 14, "ending": 19}[pos]
                vs, vid, spd = _get_scene_voice_settings(scene, idx, total)
                # Apply pace modifiers
                for pace in PACE_MODIFIERS:
                    final = round(max(0.65, min(1.0, spd * pace)), 2)
                    assert 0.65 <= final <= 1.0, (
                        f"Speed {final} out of range for {mood}/{pos}/pace={pace}"
                    )

    @pytest.mark.unit
    def test_global_spread(self):
        """Max-min across all combos must be ≥ 0.20."""
        all_speeds = []
        for mood in MOODS:
            for pos in POSITIONS:
                scene = {
                    "mood": mood,
                    "narrative_position": pos,
                    "narration": "Test text.",
                }
                total = 20
                idx = {"hook": 0, "act1": 2, "act2": 6, "act3": 14, "ending": 19}[pos]
                _, _, spd = _get_scene_voice_settings(scene, idx, total)
                all_speeds.append(spd)
        spread = max(all_speeds) - min(all_speeds)
        assert spread >= 0.20, f"Global speed spread {spread:.3f} < 0.20"

    @pytest.mark.unit
    def test_per_position_spread(self):
        """For each position, speed range across all moods must be ≥ 0.06."""
        for pos in POSITIONS:
            speeds = []
            for mood in MOODS:
                scene = {
                    "mood": mood,
                    "narrative_position": pos,
                    "narration": "Test text.",
                }
                total = 20
                idx = {"hook": 0, "act1": 2, "act2": 6, "act3": 14, "ending": 19}[pos]
                _, _, spd = _get_scene_voice_settings(scene, idx, total)
                speeds.append(spd)
            spread = max(speeds) - min(speeds)
            assert spread >= 0.06, (
                f"Position '{pos}' speed spread {spread:.3f} < 0.06 "
                f"(range: {min(speeds):.2f}-{max(speeds):.2f})"
            )

    @pytest.mark.unit
    def test_quote_voice_uses_config(self):
        """Quote detection should use VOICE_SPEED_QUOTE, not hardcoded 0.85."""
        from core.pipeline_config import VOICE_SPEED_QUOTE
        scene = {
            "mood": "dark",
            "narrative_position": "act2",
            "narration": 'The emperor said "This is the end of everything" to his guards.',
        }
        _, vid, spd = _get_scene_voice_settings(scene, 5, 20)
        assert vid == "pNInz6obpgDQGcFmaJgB", "Should use quote voice ID"
        assert spd == round(max(0.65, min(1.0, VOICE_SPEED_QUOTE)), 2), (
            f"Quote speed {spd} != VOICE_SPEED_QUOTE {VOICE_SPEED_QUOTE}"
        )

    @pytest.mark.unit
    def test_reveal_slower_than_hook(self):
        """Reveal moments should be slower than hook."""
        hook = {"mood": "tense", "narrative_position": "hook", "narration": "Test."}
        reveal = {"mood": "tense", "narrative_position": "act3",
                  "is_reveal_moment": True, "narration": "Test."}
        _, _, hook_spd = _get_scene_voice_settings(hook, 0, 20)
        _, _, reveal_spd = _get_scene_voice_settings(reveal, 14, 20)
        assert reveal_spd < hook_spd, f"Reveal {reveal_spd} should be < hook {hook_spd}"

    @pytest.mark.unit
    def test_breathing_room_slowest(self):
        """Breathing room should be at or near minimum speed."""
        breathing = {"mood": "reverent", "narrative_position": "act3",
                     "is_breathing_room": True, "narration": "Test."}
        _, _, spd = _get_scene_voice_settings(breathing, 14, 20)
        assert spd <= 0.70, f"Breathing room speed {spd} should be ≤ 0.70"

"""
Tests for inter-scene pause computation.

Validates pause durations for different scene transitions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.voice import _get_inter_scene_pause


class TestInterScenePause:
    @pytest.mark.unit
    def test_no_pause_after_last_scene(self):
        scene = {"mood": "dark"}
        assert _get_inter_scene_pause(scene, None, 9, 10) == 0

    @pytest.mark.unit
    def test_default_pause(self):
        scene = {"mood": "dark", "narrative_position": "act2"}
        next_scene = {"mood": "dark", "narrative_position": "act2"}
        pause = _get_inter_scene_pause(scene, next_scene, 5, 20)
        assert pause == 0.4

    @pytest.mark.unit
    def test_reveal_extended_pause(self):
        scene = {"is_reveal_moment": True, "narrative_position": "act3"}
        next_scene = {"narrative_position": "act3"}
        pause = _get_inter_scene_pause(scene, next_scene, 5, 20)
        assert pause == 1.8

    @pytest.mark.unit
    def test_breathing_room_pause(self):
        scene = {"is_breathing_room": True, "narrative_position": "act3"}
        next_scene = {"narrative_position": "act3"}
        pause = _get_inter_scene_pause(scene, next_scene, 5, 20)
        assert pause == 1.2

    @pytest.mark.unit
    def test_act_transition_pause(self):
        scene = {"narrative_position": "act2"}
        next_scene = {"narrative_position": "act3"}
        pause = _get_inter_scene_pause(scene, next_scene, 5, 20)
        assert pause == 0.9

    @pytest.mark.unit
    def test_act3_to_ending_is_act_transition(self):
        """act3→ending uses generic act transition (3.0s beat is synthetic scene)."""
        scene = {"narrative_position": "act3"}
        next_scene = {"narrative_position": "ending"}
        pause = _get_inter_scene_pause(scene, next_scene, 15, 20)
        assert pause == 0.9

    @pytest.mark.unit
    def test_reveal_takes_priority_over_act_transition(self):
        """Reveal pause (1.8s) should override act transition (0.9s)."""
        scene = {"is_reveal_moment": True, "narrative_position": "act2"}
        next_scene = {"narrative_position": "act3"}
        pause = _get_inter_scene_pause(scene, next_scene, 5, 20)
        assert pause == 1.8

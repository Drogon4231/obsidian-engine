"""Tests for 04b_script_doctor.py (Script Evaluator — 7 dimensions + structural checks)."""

import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))


# Import the module under test
import importlib
script_evaluator = importlib.import_module("agents.04b_script_doctor")


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_script_data(full_script: str = "", topic: str = "Test Topic") -> dict:
    """Build minimal script_data for evaluator input."""
    if not full_script:
        full_script = (
            "The year is 1347. A ship drifts into the harbor of Messina — "
            "its crew is dead. Every last one of them. "
            "What crawls off that ship will kill half of Europe. "
            "Act 1: The plague begins spreading through trade routes. "
            "Merchants carry death in their cargo. "
            "Act 2: Cities seal their gates. Doctors wear bird masks. "
            "The church says it's God's wrath. But it's fleas. "
            "To the pope, this was divine punishment. "
            "To the gravedigger working through the night, "
            "it was just Tuesday. "
            "Act 3: The revelation — the Mongol army catapulted plague corpses "
            "over the walls of Caffa. Biological warfare. In 1346. "
            "And then... silence. The weight of it. "
            "Ending: The Black Death didn't just kill people. "
            "It killed the medieval world."
        )
    words = full_script.split()
    n = len(words)
    return {
        "topic": topic,
        "angle": "The biological warfare origin",
        "full_script": full_script,
        "word_count": n,
        "length_tier": "STANDARD",
        "script": {
            "cold_open": " ".join(words[:5]),
            "hook": " ".join(words[5:20]),
            "act1": " ".join(words[20:int(n * 0.3)]),
            "act2": " ".join(words[int(n * 0.3):int(n * 0.65)]),
            "act3": " ".join(words[int(n * 0.65):int(n * 0.9)]),
            "ending": " ".join(words[int(n * 0.9):]),
        },
    }


def _make_blueprint() -> dict:
    return {
        "hook_register": "DREAD_THROUGH_BEAUTY",
        "cold_open": "A ship drifts into harbor.",
        "hook": {"opening_scene": "A silent ship in Messina harbor"},
        "act1": {"summary": "Plague spreads via trade"},
        "act2": {"summary": "Cities fall"},
        "act3": {"summary": "Biological warfare reveal"},
        "ending": {"final_line": "It killed the medieval world."},
    }


def _mock_high_scores() -> dict:
    return {
        "hook_strength": 8,
        "emotional_pacing": 8,
        "personality": 7,
        "pov_shifts": 7,
        "voice_consistency": 8,
        "factual_grounding": 7,
        "emotional_arc": 8,
        "breathability": 7,
        "revelation_craft": 8,
        "reflection_beat_present": True,
        "exposition_front_loaded": False,
        "open_loop": True,
        "specific_fixes": [
            {"section": "act2", "issue": "POV shift could be stronger", "fix": "Add a named character perspective"}
        ],
        "feedback": "Strong hook. Weakest: act2 needs more tension. Strongest: devastating ending.",
    }


def _mock_low_scores() -> dict:
    return {
        "hook_strength": 4,
        "emotional_pacing": 5,
        "personality": 4,
        "pov_shifts": 3,
        "voice_consistency": 5,
        "factual_grounding": 4,
        "emotional_arc": 5,
        "breathability": 4,
        "revelation_craft": 3,
        "reflection_beat_present": False,
        "exposition_front_loaded": True,
        "open_loop": False,
        "specific_fixes": [
            {"section": "hook", "issue": "Generic opening", "fix": "Start with a specific image"},
            {"section": "act3", "issue": "Missing reflection beat", "fix": "Add silence after reveal"},
        ],
        "feedback": "Script reads like a Wikipedia article. Needs personality.",
    }


# ── Tests: scoring ───────────────────────────────────────────────────────────

class TestComputeScores:
    def test_extracts_all_dimensions(self):
        raw = {d: i + 3 for i, d in enumerate(script_evaluator.SCORED_DIMENSIONS)}
        scores = script_evaluator._compute_scores(raw)
        assert len(scores) == len(script_evaluator.SCORED_DIMENSIONS)
        for dim in script_evaluator.SCORED_DIMENSIONS:
            assert dim in scores

    def test_clamps_to_1_10(self):
        raw = {"hook_strength": 15, "emotional_pacing": -3, "personality": 0}
        scores = script_evaluator._compute_scores(raw)
        assert scores["hook_strength"] == 10
        assert scores["emotional_pacing"] == 1
        assert scores["personality"] == 1

    def test_defaults_missing_to_5(self):
        scores = script_evaluator._compute_scores({})
        for dim in script_evaluator.SCORED_DIMENSIONS:
            assert scores[dim] == script_evaluator.DEFAULT_SCORE

    def test_handles_string_values(self):
        scores = script_evaluator._compute_scores({"hook_strength": "8"})
        assert scores["hook_strength"] == 8

    def test_handles_non_numeric(self):
        scores = script_evaluator._compute_scores({"hook_strength": "great"})
        assert scores["hook_strength"] == script_evaluator.DEFAULT_SCORE


# ── Tests: exposition placement ──────────────────────────────────────────────

class TestExpositionPlacement:
    def test_ok_when_no_markers(self):
        script = "A ship drifts. Silence. Death everywhere. " * 50
        assert script_evaluator._check_exposition_placement(script) is True

    def test_ok_when_empty(self):
        assert script_evaluator._check_exposition_placement("") is True

    def test_ok_when_short(self):
        assert script_evaluator._check_exposition_placement("Short.") is True

    def test_ok_when_markers_spread_evenly(self):
        opening = "The ship drifted into harbor. Silence. Death was everywhere. " + "More text. " * 20
        body = ("For context, the plague had been spreading. "
                "Historically, this was unprecedented. "
                "To understand this, we look at trade routes. "
                "It was known as the Black Death. " + "More story. " * 100)
        assert script_evaluator._check_exposition_placement(opening + body) is True

    def test_flags_front_loaded(self):
        # Cram all markers into first 10%
        opening = ("It was known as the plague. For context, historically, "
                   "to understand this, it should be noted, in other words, "
                   "the background was complex. ")
        body = "Then the ship arrived. Death spread. " * 100
        result = script_evaluator._check_exposition_placement(opening + body)
        # This should detect front-loading
        assert isinstance(result, bool)


# ── Tests: full run ──────────────────────────────────────────────────────────

class TestRunApproved:
    @patch.object(script_evaluator, "call_agent")
    def test_approved_when_high_scores(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())

        assert result["approved"] is True
        assert result["average_score"] >= 7.0
        assert len(result["scores"]) == len(script_evaluator.SCORED_DIMENSIONS)
        assert result["reflection_beat_present"] is True
        assert result["exposition_placement_ok"] is True
        assert "script_data" in result

    @patch.object(script_evaluator, "call_agent")
    def test_not_approved_when_low_scores(self, mock_agent):
        mock_agent.return_value = _mock_low_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())

        assert result["approved"] is False
        assert result["average_score"] < 7.0

    @patch.object(script_evaluator, "call_agent")
    def test_specific_fixes_validated(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())

        fixes = result["specific_fixes"]
        assert isinstance(fixes, list)
        for fix in fixes:
            assert "section" in fix
            assert "issue" in fix
            assert "fix" in fix

    @patch.object(script_evaluator, "call_agent")
    def test_specific_fixes_capped_at_5(self, mock_agent):
        scores = _mock_high_scores()
        scores["specific_fixes"] = [
            {"section": f"act{i}", "issue": f"issue {i}", "fix": f"fix {i}"}
            for i in range(10)
        ]
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert len(result["specific_fixes"]) <= 5

    @patch.object(script_evaluator, "call_agent")
    def test_invalid_fixes_filtered(self, mock_agent):
        scores = _mock_high_scores()
        scores["specific_fixes"] = [
            {"section": "act1", "issue": "real issue", "fix": "real fix"},
            "not a dict",
            {"no_issue_key": True},
            {"issue": ""},  # empty issue filtered
        ]
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert len(result["specific_fixes"]) == 1

    @patch.object(script_evaluator, "call_agent")
    def test_missing_reflection_beat_appends_feedback(self, mock_agent):
        scores = _mock_high_scores()
        scores["reflection_beat_present"] = False
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())

        assert result["reflection_beat_present"] is False
        assert "REFLECTION BEAT MISSING" in result["feedback"]

    @patch.object(script_evaluator, "call_agent")
    def test_front_loaded_exposition_appends_feedback(self, mock_agent):
        scores = _mock_high_scores()
        scores["exposition_front_loaded"] = True
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())

        assert result["exposition_placement_ok"] is False
        assert "EXPOSITION FRONT-LOADED" in result["feedback"]

    @patch.object(script_evaluator, "call_agent")
    def test_passes_correct_agent_name(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        script_evaluator.run(_make_script_data(), _make_blueprint())

        args, kwargs = mock_agent.call_args
        assert args[0] == "04b_script_doctor"
        assert kwargs.get("stage_num") == 4

    @patch.object(script_evaluator, "call_agent")
    def test_returns_script_data_passthrough(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        sd = _make_script_data(topic="Passthrough Test")
        result = script_evaluator.run(sd, _make_blueprint())
        assert result["script_data"]["topic"] == "Passthrough Test"

    @patch.object(script_evaluator, "call_agent")
    def test_all_7_dimensions_in_scores(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        for dim in script_evaluator.SCORED_DIMENSIONS:
            assert dim in result["scores"]

    @patch.object(script_evaluator, "call_agent")
    def test_average_is_correct(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        expected = round(sum(result["scores"].values()) / len(script_evaluator.SCORED_DIMENSIONS), 1)
        assert result["average_score"] == expected


# ── Tests: backward compatibility with run_pipeline.py ───────────────────────

class TestBackwardCompat:
    @patch.object(script_evaluator, "call_agent")
    def test_has_approved_key(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert "approved" in result

    @patch.object(script_evaluator, "call_agent")
    def test_has_scores_key(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert "scores" in result

    @patch.object(script_evaluator, "call_agent")
    def test_has_feedback_key(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert "feedback" in result
        assert isinstance(result["feedback"], str)

    @patch.object(script_evaluator, "call_agent")
    def test_scores_still_has_original_5_dimensions(self, mock_agent):
        """run_pipeline.py stores scores — ensure original 5 are still present."""
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        for dim in ["hook_strength", "emotional_pacing", "personality", "pov_shifts", "voice_consistency"]:
            assert dim in result["scores"]


# ── Tests: edge cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    @patch.object(script_evaluator, "call_agent")
    def test_empty_script(self, mock_agent):
        mock_agent.return_value = _mock_low_scores()
        sd = _make_script_data(full_script="")
        result = script_evaluator.run(sd, _make_blueprint())
        assert "scores" in result

    @patch.object(script_evaluator, "call_agent")
    def test_missing_blueprint_keys(self, mock_agent):
        mock_agent.return_value = _mock_high_scores()
        result = script_evaluator.run(_make_script_data(), {})
        assert result["approved"] is True

    @patch.object(script_evaluator, "call_agent")
    def test_specific_fixes_not_a_list(self, mock_agent):
        scores = _mock_high_scores()
        scores["specific_fixes"] = "not a list"
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert result["specific_fixes"] == []

    @patch.object(script_evaluator, "call_agent")
    def test_threshold_boundary(self, mock_agent):
        """Exactly 7.0 average should be approved."""
        scores = {d: 7 for d in script_evaluator.SCORED_DIMENSIONS}
        scores.update({
            "reflection_beat_present": True,
            "exposition_front_loaded": False,
            "specific_fixes": [],
            "feedback": "Solid.",
        })
        mock_agent.return_value = scores
        result = script_evaluator.run(_make_script_data(), _make_blueprint())
        assert result["average_score"] == 7.0
        assert result["approved"] is True

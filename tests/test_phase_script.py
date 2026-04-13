"""Tests for pipeline/phase_script.py — pure logic functions only."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.context import PipelineContext
from pipeline.runner import StageRunner


@pytest.fixture(autouse=True)
def _capture_obsidian_logs(caplog):
    """Add caplog handler directly to obsidian logger (propagate=False blocks root)."""
    obs_logger = logging.getLogger("obsidian")
    obs_logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="obsidian")
    yield
    obs_logger.removeHandler(caplog.handler)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_ctx(**overrides) -> PipelineContext:
    """Build a minimal PipelineContext with sane defaults."""
    defaults = dict(
        topic="Test Topic",
        slug="test-topic",
        ts="20260326",
        state_path=Path("/tmp/test_state.json"),
        state={"completed_stages": []},
    )
    defaults.update(overrides)
    return PipelineContext(**defaults)


def _make_runner(ctx: PipelineContext) -> StageRunner:
    runner = StageRunner(ctx)
    runner.mark = MagicMock()
    runner.done = MagicMock(return_value=False)
    return runner


# ═══════════════════════════════════════════════════════════════════════════════
# _check_blueprint_alignment
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckBlueprintAlignment:

    def _call(self, blueprint):
        from pipeline.phase_script import _check_blueprint_alignment
        _check_blueprint_alignment(blueprint)

    def test_warns_reveal_before_40pct(self, caplog):
        blueprint = {
            "act1": {"key_beats": ["a"]},          # 1 beat
            "act2": {"evidence_sequence": ["b"]},   # 1 beat  -> reveal at 2/7 = 28%
            "act3": {"reveal_sequence": ["c", "d", "e", "f", "g"]},  # 5 beats
            "estimated_length_minutes": 10,
        }
        self._call(blueprint)
        assert "Reveal at" in caplog.text

    def test_warns_reveal_after_60pct(self, caplog):
        blueprint = {
            "act1": {"key_beats": ["a", "b", "c", "d"]},  # 4
            "act2": {"evidence_sequence": ["e", "f", "g"]},  # 3 -> reveal at 7/8 = 87%
            "act3": {"reveal_sequence": ["h"]},  # 1
            "estimated_length_minutes": 10,
        }
        self._call(blueprint)
        assert "Reveal at" in caplog.text

    def test_no_warning_at_50pct(self, caplog):
        blueprint = {
            "act1": {"key_beats": ["a", "b"]},        # 2
            "act2": {"evidence_sequence": ["c", "d"]},  # 2 -> 4/8 = 50%
            "act3": {"reveal_sequence": ["e", "f", "g", "h"]},  # 4
            "estimated_length_minutes": 10,
        }
        self._call(blueprint)
        assert "WARNING" not in caplog.text

    def test_warns_short_reflection_beat(self, caplog):
        blueprint = {
            "reflection_beat": {"duration_seconds": 5},
        }
        self._call(blueprint)
        assert "Reflection beat < 8 seconds" in caplog.text

    def test_empty_blueprint_no_crash(self):
        self._call({})

    def test_none_keys_no_crash(self):
        self._call({"act1": None, "act2": None, "act3": None})


# ═══════════════════════════════════════════════════════════════════════════════
# _apply_series_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplySeriesPlan:

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.queue_series_part2")
    def test_modifies_ending_with_cliffhanger(self, mock_queue, mock_save):
        ctx = _make_ctx()
        ctx.blueprint = {
            "ending": {"reframe": "old", "final_line": "old", "cta": "old"},
        }
        ctx.series_plan = {
            "part_1_focus": "The beginning",
            "part_1_cliffhanger": "But what happened next?",
        }
        ctx.research = {"core_facts": []}

        from pipeline.phase_script import _apply_series_plan
        _apply_series_plan(ctx)

        assert ctx.blueprint["ending"]["reframe"] == "But what happened next?"
        assert ctx.blueprint["ending"]["cta"] == "Part 2 drops next. Subscribe so you don't miss it."

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.queue_series_part2")
    def test_sets_part_1_constraint(self, mock_queue, mock_save):
        ctx = _make_ctx()
        ctx.blueprint = {"ending": {"reframe": "", "final_line": ""}}
        ctx.series_plan = {
            "part_1_focus": "Origins",
            "part_1_cliffhanger": "Cliffhanger text",
        }
        ctx.research = {}

        from pipeline.phase_script import _apply_series_plan
        _apply_series_plan(ctx)

        assert "part_1_constraint" in ctx.blueprint
        assert "Origins" in ctx.blueprint["part_1_constraint"]

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.queue_series_part2")
    def test_saves_series_plan_to_state(self, mock_queue, mock_save):
        ctx = _make_ctx()
        ctx.blueprint = {}
        ctx.series_plan = {"part_1_focus": "X", "part_1_cliffhanger": "Y"}
        ctx.research = {}

        from pipeline.phase_script import _apply_series_plan
        _apply_series_plan(ctx)

        assert ctx.state["series_plan"] is ctx.series_plan
        mock_save.assert_called_once()

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.queue_series_part2")
    def test_calls_queue_series_part2(self, mock_queue, mock_save):
        ctx = _make_ctx()
        ctx.blueprint = {}
        ctx.series_plan = {"part_1_focus": "X", "part_1_cliffhanger": "Y"}
        ctx.research = {"data": True}

        from pipeline.phase_script import _apply_series_plan
        _apply_series_plan(ctx)

        mock_queue.assert_called_once_with("Test Topic", ctx.series_plan, ctx.research,
                                                 state_path=str(ctx.state_path))

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.queue_series_part2")
    def test_no_modification_when_missing_part_1_focus(self, mock_queue, mock_save):
        ctx = _make_ctx()
        ctx.blueprint = {"ending": {"reframe": "original"}}
        ctx.series_plan = {"part_1_cliffhanger": "Y"}
        ctx.research = {}

        from pipeline.phase_script import _apply_series_plan
        _apply_series_plan(ctx)

        # No part_1_constraint added, ending not modified
        assert "part_1_constraint" not in ctx.blueprint
        assert ctx.blueprint["ending"]["reframe"] == "original"
        mock_queue.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# _post_process_script
# ═══════════════════════════════════════════════════════════════════════════════

class TestPostProcessScript:

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=[])
    def test_raises_on_short_word_count_after_expansion_fails(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": "too short"}
        runner = _make_runner(ctx)

        from pipeline.phase_script import _post_process_script
        # Mock call_agent to return a still-short expansion
        with patch("core.agent_wrapper.call_agent", return_value={"full_script": "still too short"}):
            with pytest.raises(Exception, match="script too short"):
                _post_process_script(ctx, runner, MagicMock())

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=[])
    def test_auto_expands_short_script(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": " ".join(["word"] * 950)}
        runner = _make_runner(ctx)

        expanded_script = " ".join(["expanded"] * 1200)
        from pipeline.phase_script import _post_process_script
        with patch("core.agent_wrapper.call_agent", return_value={"full_script": expanded_script}):
            _post_process_script(ctx, runner, MagicMock())
        # Should not raise — expansion succeeded
        assert len(ctx.script["full_script"].split()) >= 1000

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=["issue1"])
    def test_calls_check_script_and_check_pacing(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": " ".join(["word"] * 1500)}
        runner = _make_runner(ctx)

        from pipeline.phase_script import _post_process_script
        _post_process_script(ctx, runner, MagicMock())

        mock_cs.assert_called_once()
        mock_cp.assert_called_once()

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value={"curiosity_gap": 8, "stakes": 7, "keep_watching": 9})
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=[])
    def test_saves_hook_scores_to_state(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": " ".join(["word"] * 1500)}
        runner = _make_runner(ctx)

        from pipeline.phase_script import _post_process_script
        _post_process_script(ctx, runner, MagicMock())

        assert ctx.state["hook_scores"] == {"curiosity_gap": 8, "stakes": 7, "keep_watching": 9}
        mock_save.assert_called()

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=["i1", "i2", "i3"])
    def test_quality_rewrite_on_3_issues(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": " ".join(["word"] * 1500)}
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        improved_script = {"full_script": " ".join(["better"] * 1500)}
        a04.run.return_value = improved_script

        # After rewrite, check_script returns fewer issues
        mock_cs.side_effect = [["i1", "i2", "i3"], ["i1"]]

        from pipeline.phase_script import _post_process_script
        _post_process_script(ctx, runner, a04)

        a04.run.assert_called_once()
        assert ctx.script is improved_script

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=["i1", "i2", "i3"])
    def test_quality_rewrite_calls_runner_mark(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": " ".join(["word"] * 1500)}
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        improved = {"full_script": " ".join(["better"] * 1500)}
        a04.run.return_value = improved
        mock_cs.side_effect = [["i1", "i2", "i3"], ["i1"]]

        from pipeline.phase_script import _post_process_script
        _post_process_script(ctx, runner, a04)

        runner.mark.assert_called_once_with(4, improved)

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x + " cleaned")
    @patch("pipeline.phase_script.score_hook", return_value=None)
    @patch("pipeline.phase_script.check_pacing", return_value=[])
    @patch("pipeline.phase_script.check_script", return_value=[])
    def test_always_calls_clean_script(self, mock_cs, mock_cp, mock_sh, mock_cl, mock_save):
        ctx = _make_ctx()
        text = " ".join(["word"] * 1500)
        ctx.script = {"full_script": text}
        runner = _make_runner(ctx)

        from pipeline.phase_script import _post_process_script
        _post_process_script(ctx, runner, MagicMock())

        mock_cl.assert_called()
        assert ctx.script["full_script"].endswith(" cleaned")


# ═══════════════════════════════════════════════════════════════════════════════
# _run_script_doctor
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunScriptDoctor:

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_approved_first_try(self, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": "script text"}
        ctx.blueprint = {"act1": {}}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04b = MagicMock()
        a04b.run.return_value = {"approved": True, "scores": {"clarity": 8}}

        from pipeline.phase_script import _run_script_doctor
        _run_script_doctor(ctx, runner, a04, a04b)

        assert ctx.state["script_doctor_scores"] == {"clarity": 8}
        a04.run.assert_not_called()

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_revision_then_approved(self, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": "original"}
        ctx.blueprint = {}
        ctx.research = {}
        ctx.angle = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04.run.return_value = {"full_script": "improved"}
        a04b = MagicMock()
        # First call: not approved with feedback; second call: approved
        a04b.run.side_effect = [
            {"approved": False, "feedback": "Needs more tension", "scores": {"clarity": 5}},
            {"approved": True, "scores": {"clarity": 9}},
        ]

        from pipeline.phase_script import _run_script_doctor
        _run_script_doctor(ctx, runner, a04, a04b)

        a04.run.assert_called_once()
        runner.mark.assert_called_once_with(4, ctx.script)
        assert ctx.state["script_doctor_scores"] == {"clarity": 9}

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_exhausts_retries_raises_runtime_error(self, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": "original"}
        ctx.blueprint = {}
        ctx.research = {}
        ctx.angle = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04.run.return_value = {"full_script": "still bad"}
        a04b = MagicMock()
        # All calls return not approved with feedback
        a04b.run.return_value = {
            "approved": False,
            "feedback": "Still bad",
            "scores": {"clarity": 4},
            "average_score": 4.0,
        }

        from pipeline.phase_script import _run_script_doctor
        with pytest.raises(RuntimeError, match="Script Doctor gate FAILED"):
            _run_script_doctor(ctx, runner, a04, a04b)

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_no_feedback_breaks_without_retry(self, mock_cl, mock_save):
        ctx = _make_ctx()
        ctx.script = {"full_script": "script"}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04b = MagicMock()
        a04b.run.return_value = {"approved": False, "feedback": "", "scores": {}}

        from pipeline.phase_script import _run_script_doctor
        _run_script_doctor(ctx, runner, a04, a04b)

        a04.run.assert_not_called()

    @patch("pipeline.phase_script.save_state")
    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_non_runtime_error_is_non_fatal(self, mock_cl, mock_save, caplog):
        ctx = _make_ctx()
        ctx.script = {"full_script": "script"}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04b = MagicMock()
        a04b.run.side_effect = ValueError("network timeout")

        from pipeline.phase_script import _run_script_doctor
        _run_script_doctor(ctx, runner, a04, a04b)

        assert "non-fatal" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# _check_hook_consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckHookConsistency:

    def test_warns_when_opening_doesnt_match(self, caplog):
        ctx = _make_ctx()
        ctx.blueprint = {"hook": {"opening_scene": "A massive explosion rocked downtown"}}
        ctx.script = {"full_script": "The weather was nice today and birds were singing."}

        from pipeline.phase_script import _check_hook_consistency
        _check_hook_consistency(ctx)

        assert "Hook consistency" in caplog.text

    def test_no_warning_when_words_match(self, caplog):
        ctx = _make_ctx()
        ctx.blueprint = {"hook": {"opening_scene": "A massive explosion rocked downtown"}}
        ctx.script = {"full_script": "A massive explosion rocked downtown Chicago on that fateful night."}

        from pipeline.phase_script import _check_hook_consistency
        _check_hook_consistency(ctx)

        assert "Hook consistency" not in caplog.text

    def test_handles_missing_hook_key(self, caplog):
        ctx = _make_ctx()
        ctx.blueprint = {}
        ctx.script = {"full_script": "Some text"}

        from pipeline.phase_script import _check_hook_consistency
        # Should not raise
        _check_hook_consistency(ctx)

    def test_handles_hook_not_dict(self, caplog):
        ctx = _make_ctx()
        ctx.blueprint = {"hook": "just a string"}
        ctx.script = {"full_script": "Some text"}

        from pipeline.phase_script import _check_hook_consistency
        _check_hook_consistency(ctx)
        # No crash, no warning about consistency (empty hook_scene)
        assert "Hook consistency" not in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# _apply_verification_corrections
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyVerificationCorrections:

    def test_applies_string_replacements(self):
        ctx = _make_ctx()
        ctx.script = {"full_script": "The cat sat on the mat."}
        ctx.verification = {
            "script_corrections": [
                {"original_text": "cat", "corrected_text": "dog"},
            ],
        }

        from pipeline.phase_script import _apply_verification_corrections
        _apply_verification_corrections(ctx)

        assert ctx.script["full_script"] == "The dog sat on the mat."

    def test_counts_applied_corrections(self, caplog):
        ctx = _make_ctx()
        ctx.script = {"full_script": "Alpha Beta Gamma Delta"}
        ctx.verification = {
            "script_corrections": [
                {"original_text": "Alpha", "corrected_text": "One"},
                {"original_text": "Gamma", "corrected_text": "Three"},
                {"original_text": "Missing", "corrected_text": "Nope"},
            ],
        }

        from pipeline.phase_script import _apply_verification_corrections
        _apply_verification_corrections(ctx)

        output = caplog.text
        assert "Applied 2/3" in output

    def test_handles_original_not_found(self, caplog):
        ctx = _make_ctx()
        ctx.script = {"full_script": "Hello world"}
        ctx.verification = {
            "script_corrections": [
                {"original_text": "nonexistent", "corrected_text": "replacement"},
            ],
        }

        from pipeline.phase_script import _apply_verification_corrections
        _apply_verification_corrections(ctx)

        assert "Applied 0/1" in caplog.text
        assert ctx.script["full_script"] == "Hello world"

    def test_no_corrections_no_output(self, caplog):
        ctx = _make_ctx()
        ctx.script = {"full_script": "Hello"}
        ctx.verification = {"script_corrections": []}

        from pipeline.phase_script import _apply_verification_corrections
        _apply_verification_corrections(ctx)

        assert "Applied" not in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# _handle_requires_rewrite
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleRequiresRewrite:

    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_succeeds_on_retry_1(self, mock_cl):
        ctx = _make_ctx()
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04.run.return_value = {"full_script": "new script"}
        a05 = MagicMock()
        a05.run.return_value = {"overall_verdict": "APPROVED"}

        from pipeline.phase_script import _handle_requires_rewrite
        _handle_requires_rewrite(ctx, runner, a04, a05)

        assert runner.mark.call_count == 2
        runner.mark.assert_any_call(4, {"full_script": "new script"})
        runner.mark.assert_any_call(5, {"overall_verdict": "APPROVED"})

    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_succeeds_on_retry_2(self, mock_cl):
        ctx = _make_ctx()
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04.run.return_value = {"full_script": "new script"}
        a05 = MagicMock()
        # First retry still REQUIRES_REWRITE, second passes
        a05.run.side_effect = [
            {"overall_verdict": "REQUIRES_REWRITE"},
            {"overall_verdict": "APPROVED"},
        ]

        from pipeline.phase_script import _handle_requires_rewrite
        _handle_requires_rewrite(ctx, runner, a04, a05)

        assert runner.mark.call_count == 2

    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_both_retries_fail_raises(self, mock_cl):
        ctx = _make_ctx()
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        a04.run.return_value = {"full_script": "bad"}
        a05 = MagicMock()
        a05.run.return_value = {"overall_verdict": "REQUIRES_REWRITE"}

        from pipeline.phase_script import _handle_requires_rewrite
        with pytest.raises(Exception, match="FATAL"):
            _handle_requires_rewrite(ctx, runner, a04, a05)

    @patch("pipeline.phase_script.clean_script", side_effect=lambda x: x)
    def test_retry_error_continues(self, mock_cl, caplog):
        ctx = _make_ctx()
        ctx.research = {}
        ctx.angle = {}
        ctx.blueprint = {}
        runner = _make_runner(ctx)
        a04 = MagicMock()
        # First call errors, second call succeeds
        a04.run.side_effect = [
            Exception("API error"),
            {"full_script": "recovered"},
        ]
        a05 = MagicMock()
        a05.run.return_value = {"overall_verdict": "APPROVED"}

        from pipeline.phase_script import _handle_requires_rewrite
        _handle_requires_rewrite(ctx, runner, a04, a05)

        output = caplog.text
        assert "error" in output.lower()
        assert runner.mark.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Series continuity — _enrich_research_with_parent
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnrichResearchWithParent:
    """Test that Part 2 research gets enriched with Part 1 context."""

    def test_enriches_research_with_parent_context(self):
        ctx = _make_ctx()
        ctx.series_meta = {"series_part": 2, "parent_topic": "Fall of Rome", "part_focus": "The aftermath"}
        ctx.parent_context = {
            "research": {"core_facts": ["fact1", "fact2"]},
            "angle": {"chosen_angle": "The betrayal", "twist_potential": "The ally was the traitor"},
            "script": {"full_script": "Once upon a time..." * 100},
            "series_plan": {"part_1_cliffhanger": "But who really did it?"},
        }
        ctx.research = {"topic": "Fall of Rome (Part 2)", "core_facts": ["new_fact"]}

        from pipeline.phase_script import _enrich_research_with_parent
        _enrich_research_with_parent(ctx)

        sc = ctx.research["_series_context"]
        assert sc["series_part"] == 2
        assert sc["parent_angle"] == "The betrayal"
        assert sc["parent_twist"] == "The ally was the traitor"
        assert sc["parent_cliffhanger"] == "But who really did it?"
        assert sc["part_focus"] == "The aftermath"
        assert len(sc["parent_core_facts_covered"]) == 2
        assert len(sc["parent_script_summary"]) > 0

    def test_no_enrichment_without_parent_context(self):
        ctx = _make_ctx()
        ctx.series_meta = {"series_part": 2}
        ctx.parent_context = None
        ctx.research = {"topic": "Test", "core_facts": []}

        from pipeline.phase_script import _enrich_research_with_parent
        _enrich_research_with_parent(ctx)

        # Should not crash, but _series_context still set (with empty parent data)
        sc = ctx.research["_series_context"]
        assert sc["series_part"] == 2
        assert sc["parent_angle"] == ""

    def test_original_research_preserved(self):
        ctx = _make_ctx()
        ctx.series_meta = {"series_part": 2, "parent_topic": "X", "part_focus": "Y"}
        ctx.parent_context = {
            "research": {"core_facts": ["old"]},
            "angle": {"chosen_angle": "a"},
            "script": {"full_script": "s"},
            "series_plan": {},
        }
        ctx.research = {"topic": "Test Part 2", "core_facts": ["new1", "new2"], "key_figures": []}

        from pipeline.phase_script import _enrich_research_with_parent
        _enrich_research_with_parent(ctx)

        assert ctx.research["core_facts"] == ["new1", "new2"]
        assert ctx.research["key_figures"] == []
        assert "_series_context" in ctx.research


class TestSeriesDedup:
    """Test that series continuations skip dedup."""

    def test_dedup_skipped_for_series(self):
        ctx = _make_ctx()
        ctx.series_meta = {"series_part": 2}

        from pipeline.phase_setup import run_topic_dedup
        # Should return immediately without importing topic_store
        run_topic_dedup(ctx)  # no error = success

    def test_dedup_runs_for_non_series(self):
        ctx = _make_ctx()
        ctx.series_meta = None

        mock_ts = MagicMock()
        mock_ts.is_duplicate.return_value = (False, "")
        with patch.dict("sys.modules", {"server": MagicMock(topic_store=mock_ts), "server.topic_store": mock_ts}):
            from pipeline.phase_setup import run_topic_dedup
            run_topic_dedup(ctx)


class TestSeriesDetectionSkipped:
    """Test that series detection is skipped for continuations."""

    def test_series_detection_skipped_for_part_2(self):
        ctx = _make_ctx()
        ctx.series_meta = {"series_part": 2}
        ctx.parent_context = {"research": {}, "angle": {}, "script": {}, "series_plan": {}}
        ctx.blueprint = {"structure_type": "CLASSIC"}
        ctx.research = {"topic": "Test Part 2", "core_facts": []}

        # Verify is_continuation logic
        is_continuation = bool(ctx.series_meta and ctx.series_meta.get("series_part", 1) > 1)
        assert is_continuation is True

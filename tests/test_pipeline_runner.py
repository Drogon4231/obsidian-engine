"""Tests for pipeline/runner.py (StageRunner) and pipeline/context.py (PipelineContext)."""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.context import PipelineContext
from pipeline.runner import StageRunner


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineContext
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipelineContextDefaults:
    def test_defaults_are_sensible(self):
        ctx = PipelineContext()
        assert ctx.topic == ""
        assert ctx.slug == ""
        assert ctx.resume is False
        assert ctx.from_stage == 1
        assert ctx.budget_cap == 0.0
        assert ctx.is_experiment is False
        assert isinstance(ctx.state, dict)
        assert isinstance(ctx.state_path, Path)
        assert isinstance(ctx.run_id, str)
        assert len(ctx.run_id) == 8

    def test_stage_lock_is_real_lock(self):
        ctx = PipelineContext()
        assert hasattr(ctx.stage_lock, "acquire") and hasattr(ctx.stage_lock, "release")
        # Lock should be acquirable
        assert ctx.stage_lock.acquire(timeout=0.1)
        ctx.stage_lock.release()

    def test_state_dict_independent_per_instance(self):
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        ctx1.state["foo"] = "bar"
        assert "foo" not in ctx2.state


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.done()
# ═══════════════════════════════════════════════════════════════════════════════


class TestDone:
    def test_false_when_not_resuming(self):
        ctx = PipelineContext(resume=False, state={"completed_stages": [1]})
        runner = StageRunner(ctx)
        assert runner.done(1) is False

    def test_false_when_stage_not_in_completed(self):
        ctx = PipelineContext(resume=True, state={"completed_stages": [2, 3]})
        runner = StageRunner(ctx)
        assert runner.done(1) is False

    @patch("pipeline.validators.validate_stage_output", return_value=True)
    def test_true_when_resuming_and_completed_and_valid(self, mock_val):
        ctx = PipelineContext(
            resume=True,
            state={"completed_stages": [1], "stage_1": {"core_facts": ["a"], "key_figures": ["b"]}},
        )
        runner = StageRunner(ctx)
        assert runner.done(1) is True
        mock_val.assert_called_once_with(1, ctx.state["stage_1"])

    @patch("pipeline.validators.validate_stage_output", return_value=False)
    def test_false_when_resuming_but_validation_fails(self, mock_val):
        ctx = PipelineContext(
            resume=True,
            state={"completed_stages": [1], "stage_1": {}},
        )
        runner = StageRunner(ctx)
        assert runner.done(1) is False


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.mark()
# ═══════════════════════════════════════════════════════════════════════════════


class TestMark:
    @patch("pipeline.runner.save_state")
    def test_records_stage_data(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark(3, {"some": "data"}, elapsed=1.5)
        assert ctx.state["stage_3"] == {"some": "data"}

    @patch("pipeline.runner.save_state")
    def test_appends_to_completed_stages_no_dups(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": [3]})
        runner = StageRunner(ctx)
        runner.mark(3, "data", elapsed=0.5)
        assert ctx.state["completed_stages"] == [3]
        runner.mark(4, "data2", elapsed=0.5)
        assert ctx.state["completed_stages"] == [3, 4]

    @patch("pipeline.runner.save_state")
    def test_records_elapsed_timing(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark(2, "data", elapsed=4.2)
        assert ctx.state["stage_timings"]["2"] == 4.2

    @patch("pipeline.runner.save_state")
    def test_no_timing_when_elapsed_is_none(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark(2, "data", elapsed=None)
        assert "stage_timings" not in ctx.state

    @patch("pipeline.runner.save_state")
    def test_saves_state_to_disk(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark(1, "data")
        mock_save.assert_called_once_with(ctx.state, ctx.state_path)

    @patch("pipeline.runner.save_state")
    def test_thread_safe_concurrent_marks(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        errors = []

        def mark_stage(n):
            try:
                for _ in range(50):
                    runner.mark(n, f"data_{n}", elapsed=float(n))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mark_stage, args=(i,)) for i in range(1, 6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All 5 stages should be recorded
        for i in range(1, 6):
            assert i in ctx.state["completed_stages"]
            assert ctx.state[f"stage_{i}"] == f"data_{i}"


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.mark_metadata()
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarkMetadata:
    @patch("pipeline.runner.save_state")
    def test_sets_arbitrary_key_under_lock(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark_metadata("custom_key", {"x": 1})
        assert ctx.state["custom_key"] == {"x": 1}

    @patch("pipeline.runner.save_state")
    def test_saves_state(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.mark_metadata("k", "v")
        mock_save.assert_called_once_with(ctx.state, ctx.state_path)


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.save_state_unlocked()
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveStateUnlocked:
    @patch("pipeline.runner.save_state")
    def test_calls_save_state_without_lock(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        runner.save_state_unlocked()
        mock_save.assert_called_once_with(ctx.state, ctx.state_path)


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.run_stage()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunStage:
    @patch("pipeline.runner.save_state")
    def test_normal_execution(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        fn = MagicMock(return_value={"result": "ok"})
        result = runner.run_stage(1, "Research", fn, "arg1", "arg2")
        fn.assert_called_once_with("arg1", "arg2")
        assert result == {"result": "ok"}
        assert ctx.state["stage_1"] == {"result": "ok"}
        assert 1 in ctx.state["completed_stages"]

    @patch("pipeline.runner.save_state")
    def test_skip_when_num_below_from_stage(self, mock_save):
        ctx = PipelineContext(from_stage=5, state={"completed_stages": [], "stage_3": "cached"})
        runner = StageRunner(ctx)
        fn = MagicMock()
        result = runner.run_stage(3, "Narrative", fn)
        fn.assert_not_called()
        assert result == "cached"

    @patch("pipeline.validators.validate_stage_output", return_value=True)
    @patch("pipeline.runner.save_state")
    def test_skip_when_done_returns_true(self, mock_save, mock_val):
        ctx = PipelineContext(
            resume=True,
            state={"completed_stages": [1], "stage_1": {"core_facts": ["a"], "key_figures": ["b"]}},
        )
        runner = StageRunner(ctx)
        fn = MagicMock()
        result = runner.run_stage(1, "Research", fn)
        fn.assert_not_called()
        assert result == ctx.state["stage_1"]

    @patch("pipeline.runner.save_state")
    def test_pipeline_doctor_recovery(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        original_err = ValueError("boom")
        fn = MagicMock(side_effect=original_err)

        mock_doctor = MagicMock()
        mock_doctor.intervene.return_value = {"recovered": True}
        with patch("core.pipeline_doctor", mock_doctor, create=True):
            result = runner.run_stage(1, "Research", fn)

        assert result == {"recovered": True}
        mock_doctor.intervene.assert_called_once()
        call_args = mock_doctor.intervene.call_args
        assert call_args[0][0] == 1
        assert call_args[0][1] == "Research"

    @patch("pipeline.runner.save_state")
    def test_pipeline_doctor_import_fails(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        original_err = ValueError("stage failed")
        fn = MagicMock(side_effect=original_err)

        # Make pipeline_doctor unimportable by removing it from sys.modules
        # and ensuring the import raises ImportError
        saved = sys.modules.pop("core.pipeline_doctor", None)
        saved_core = sys.modules.pop("core", None)
        try:
            with pytest.raises(ValueError, match="stage failed"):
                runner.run_stage(1, "Research", fn)
        finally:
            if saved_core is not None:
                sys.modules["core"] = saved_core
            if saved is not None:
                sys.modules["core.pipeline_doctor"] = saved

    @patch("pipeline.runner.save_state")
    def test_pipeline_doctor_also_fails(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        original_err = ValueError("original error")
        fn = MagicMock(side_effect=original_err)

        mock_doctor = MagicMock()
        mock_doctor.intervene.side_effect = RuntimeError("doctor failed")
        with patch("core.pipeline_doctor", mock_doctor, create=True):
            with pytest.raises(ValueError, match="original error"):
                runner.run_stage(1, "Research", fn)

    @patch("pipeline.runner.save_state")
    def test_budget_check_after_completion(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []}, budget_cap=10.0)
        runner = StageRunner(ctx)
        fn = MagicMock(return_value="ok")
        mock_check = MagicMock()

        mock_cost_tracker = MagicMock()
        mock_cost_tracker.check_budget = mock_check
        with patch.dict("sys.modules", {"core.cost_tracker": mock_cost_tracker}):
            runner.run_stage(1, "Research", fn)

        mock_check.assert_called_once_with(10.0, "Research")

    @patch("pipeline.runner.save_state")
    def test_no_budget_check_when_cap_zero(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []}, budget_cap=0.0)
        runner = StageRunner(ctx)
        fn = MagicMock(return_value="ok")

        mock_cost_tracker = MagicMock()
        with patch.dict("sys.modules", {"core.cost_tracker": mock_cost_tracker}):
            runner.run_stage(1, "Research", fn)
            # budget_cap is 0 so the code should never enter the budget check block
            mock_cost_tracker.check_budget.assert_not_called()

    @patch("pipeline.runner.save_state")
    def test_prints_stage_banners(self, mock_save, capsys):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        fn = MagicMock(return_value="ok")
        runner.run_stage(3, "Narrative Architect", fn)
        captured = capsys.readouterr().out
        assert "STAGE 03" in captured
        assert "NARRATIVE ARCHITECT" in captured
        assert "Done in" in captured


# ═══════════════════════════════════════════════════════════════════════════════
# StageRunner.run_short_stage()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunShortStage:
    @patch("pipeline.runner.save_state")
    def test_normal_execution_with_key_tracking(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        fn = MagicMock(return_value={"short": "result"})
        result = runner.run_short_stage("convert", "Convert Video", fn, "a", "b")
        fn.assert_called_once_with("a", "b")
        assert result == {"short": "result"}
        assert ctx.state["stage_convert"] == {"short": "result"}
        assert "convert" in ctx.state["completed_short_stages"]

    @patch("pipeline.runner.save_state")
    def test_skip_on_resume_when_key_completed(self, mock_save):
        ctx = PipelineContext(
            state={
                "completed_stages": [],
                "completed_short_stages": ["convert"],
                "stage_convert": {"cached": True},
            },
        )
        runner = StageRunner(ctx)
        fn = MagicMock()
        result = runner.run_short_stage("convert", "Convert Video", fn)
        fn.assert_not_called()
        assert result == {"cached": True}

    @patch("pipeline.runner.save_state")
    def test_state_recorded_under_lock(self, mock_save):
        ctx = PipelineContext(state={"completed_stages": []})
        runner = StageRunner(ctx)
        fn = MagicMock(return_value="result")
        runner.run_short_stage("render", "Render", fn)
        assert ctx.state["stage_render"] == "result"
        mock_save.assert_called_once()

    @patch("pipeline.runner.save_state")
    def test_warning_when_resumed_but_state_key_missing(self, mock_save, capsys):
        ctx = PipelineContext(
            state={
                "completed_stages": [],
                "completed_short_stages": ["convert"],
                # NOTE: no "stage_convert" key
            },
        )
        runner = StageRunner(ctx)
        fn = MagicMock()
        result = runner.run_short_stage("convert", "Convert Video", fn)
        fn.assert_not_called()
        assert result is None
        captured = capsys.readouterr().out
        assert "missing on resume" in captured

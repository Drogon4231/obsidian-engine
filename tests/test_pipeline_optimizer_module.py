"""Tests for core/pipeline_optimizer.py — post-run quality analysis."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from core.pipeline_optimizer import (
    _timing_analysis,
    _cross_run_trends,
    _scoring_config_analysis,
    _save_report,
    _load_agent_prompt,
    _load_recent_states,
    STAGE_META,
    STAGE_NAMES,
)


@pytest.mark.unit
class TestStageMetadata:
    """Verify stage metadata is well-formed."""

    def test_all_stages_present(self):
        expected_stages = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
        assert set(STAGE_META.keys()) == expected_stages

    def test_each_stage_has_name(self):
        for num, meta in STAGE_META.items():
            assert "name" in meta, f"Stage {num} missing 'name'"

    def test_stage_names_dict_matches(self):
        for num, meta in STAGE_META.items():
            assert STAGE_NAMES[num] == meta["name"]


@pytest.mark.unit
class TestTimingAnalysis:
    """Test per-stage timing analysis."""

    def test_no_timings_returns_unavailable(self):
        result = _timing_analysis({}, [])
        assert result["available"] is False

    def test_basic_analysis(self):
        state = {"stage_timings": {"1": 15.0, "2": 8.0, "3": 12.0}}
        result = _timing_analysis(state, [])
        assert result["available"] is True
        assert result["total_seconds"] == 35.0
        assert "1" in result["stages"]

    def test_compares_against_history(self):
        state = {"stage_timings": {"1": 60.0}}
        past = [
            {"stage_timings": {"1": 20.0}},
            {"stage_timings": {"1": 25.0}},
        ]
        result = _timing_analysis(state, past)
        stage_1 = result["stages"]["1"]
        assert stage_1["delta_vs_avg"] > 0
        assert stage_1["flag"] == "⚠ SLOW"

    def test_faster_than_average_flagged(self):
        state = {"stage_timings": {"1": 5.0}}
        past = [{"stage_timings": {"1": 50.0}}]
        result = _timing_analysis(state, past)
        assert result["stages"]["1"]["flag"] == "✓ FASTER"

    def test_pct_of_total(self):
        state = {"stage_timings": {"1": 50.0, "2": 50.0}}
        result = _timing_analysis(state, [])
        assert result["stages"]["1"]["pct_of_total"] == 50.0


@pytest.mark.unit
class TestCrossRunTrends:
    """Test cross-run trend computation."""

    def test_no_past_states(self):
        result = _cross_run_trends({}, [])
        assert result["runs_available"] == 0

    def test_computes_averages(self):
        state = {
            "stage_4": {"full_script": "word " * 1200},
            "stage_8": {"total_duration_seconds": 600},
            "stage_timings": {"1": 100},
        }
        past = [{
            "stage_4": {"full_script": "word " * 800},
            "stage_8": {"total_duration_seconds": 480},
            "stage_timings": {"1": 80},
        }]
        result = _cross_run_trends(state, past)
        assert result["runs_available"] == 1
        assert result["avg_word_count"] == 1000  # avg of 1200 and 800
        assert result["this_run"]["word_count"] == 1200


@pytest.mark.unit
class TestScoringConfigAnalysis:
    """Test scoring config threshold analysis."""

    def test_unavailable_without_thresholds(self):
        with patch("core.pipeline_optimizer.SCORING_THRESHOLDS", {}):
            result = _scoring_config_analysis({})
        assert result["available"] is False

    def test_unavailable_without_insights_file(self, tmp_path):
        with patch("core.pipeline_optimizer.SCORING_THRESHOLDS", {"key": 1}), \
             patch("core.pipeline_optimizer.BASE_DIR", tmp_path):
            result = _scoring_config_analysis({})
        assert result["available"] is False


@pytest.mark.unit
class TestLoadAgentPrompt:
    """Test system prompt extraction from agent files."""

    def test_extracts_system_prompt(self, tmp_path):
        agent_file = tmp_path / "test_agent.py"
        agent_file.write_text('SYSTEM_PROMPT = """You are a research agent."""\n')
        with patch("core.pipeline_optimizer.BASE_DIR", tmp_path):
            result = _load_agent_prompt("test_agent.py")
        assert "research agent" in result

    def test_nonexistent_file_returns_empty(self):
        result = _load_agent_prompt("nonexistent_agent.py")
        assert result == ""

    def test_truncates_long_prompts(self, tmp_path):
        agent_file = tmp_path / "long_agent.py"
        agent_file.write_text(f'SYSTEM_PROMPT = """{"x" * 5000}"""\n')
        with patch("core.pipeline_optimizer.BASE_DIR", tmp_path):
            result = _load_agent_prompt("long_agent.py")
        assert len(result) <= 3000


@pytest.mark.unit
class TestLoadRecentStates:
    """Test loading historical state files."""

    def test_empty_outputs_dir(self, tmp_path):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        with patch("core.pipeline_optimizer.OUTPUT_DIR", outputs):
            result = _load_recent_states(Path("/fake_current.json"))
        assert result == []

    def test_excludes_current_run(self, tmp_path):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        current = outputs / "current_state.json"
        current.write_text('{"topic": "current"}')
        other = outputs / "other_state.json"
        other.write_text('{"topic": "other"}')
        with patch("core.pipeline_optimizer.OUTPUT_DIR", outputs):
            result = _load_recent_states(current)
        assert len(result) == 1
        assert result[0]["topic"] == "other"


@pytest.mark.unit
class TestSaveReport:
    """Test report persistence to lessons_learned.json."""

    def test_creates_file(self, tmp_path):
        lessons = tmp_path / "lessons_learned.json"
        with patch("core.pipeline_optimizer.LESSONS_FILE", lessons):
            _save_report(
                {"topic": "Test"}, {"overall_grade": "B", "summary": "Good"},
                {"total_seconds": 300}, {"overall_score": 7},
            )
        assert lessons.exists()
        data = json.loads(lessons.read_text())
        assert len(data["optimizer_runs"]) == 1
        assert data["optimizer_runs"][0]["overall_grade"] == "B"

    def test_appends_to_existing(self, tmp_path):
        lessons = tmp_path / "lessons_learned.json"
        lessons.write_text('{"optimizer_runs": [{"topic": "old"}]}')
        with patch("core.pipeline_optimizer.LESSONS_FILE", lessons):
            _save_report(
                {"topic": "New"}, {}, {"total_seconds": 0}, {"overall_score": 5},
            )
        data = json.loads(lessons.read_text())
        assert len(data["optimizer_runs"]) == 2

    def test_caps_at_100_runs(self, tmp_path):
        lessons = tmp_path / "lessons_learned.json"
        existing = {"optimizer_runs": [{"topic": f"run_{i}"} for i in range(105)]}
        lessons.write_text(json.dumps(existing))
        with patch("core.pipeline_optimizer.LESSONS_FILE", lessons):
            _save_report({"topic": "new"}, {}, {"total_seconds": 0}, {"overall_score": 5})
        data = json.loads(lessons.read_text())
        assert len(data["optimizer_runs"]) == 100

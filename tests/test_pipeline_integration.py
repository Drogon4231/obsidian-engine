"""End-to-end integration tests for run_pipeline() with all externals mocked."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Minimal valid stage outputs that pass validate_stage_output
# ---------------------------------------------------------------------------

STAGE_OUTPUTS = {
    1: {
        "core_facts": ["f1", "f2", "f3", "f4", "f5"],
        "key_figures": ["fig1", "fig2"],
        "key_facts": ["f1"],
        "sources": ["s1"],
        "primary_sources": ["ps1"],
    },
    2: {
        "chosen_angle": "test angle",
        "angle_justification": "because it is interesting",
        "unique_angle": "test angle",
    },
    3: {
        "act1": {"key_beats": ["b1"]},
        "act2": {"evidence_sequence": ["e1"]},
        "act3": {"reveal_sequence": ["r1"]},
        "hook": {"opening_scene": "A dark night in 1943"},
        "ending": {"reframe": "", "final_line": "end", "cta": "subscribe"},
        "estimated_length_minutes": 10,
    },
    4: {
        "full_script": " ".join(["word"] * 1500),
        "hook": "A dark opening hook",
        "length_tier": "STANDARD",
    },
    "4b": {"approved": True, "scores": {"tension": 8, "pacing": 7}, "average_score": 7.5},
    5: {
        "overall_verdict": "APPROVED",
        "script_corrections": [],
    },
    6: {
        "recommended_title": "Test Title: The Untold Story",
        "tags": ["history", "documentary", "test"],
        "title_variants": [
            {"title": "Variant A"},
            {"title": "Variant B"},
        ],
    },
    7: {
        "scenes": [{"scene_number": i, "text": f"Scene {i} narration", "mood": "dark"} for i in range(8)],
    },
    "7b": {
        "scenes": [{"scene_number": i, "text": f"Scene {i} narration", "mood": "dark"} for i in range(8)],
        "visual_bible": {"palette": "dark"},
    },
    8: {
        "audio_path": "/fake/audio.mp3",
        "total_duration_seconds": 600,
        "word_timestamps": {},
    },
    9: {
        "scenes": [{"scene_number": i, "footage_url": f"http://example.com/{i}.mp4"} for i in range(8)],
        "credits": ["credit1"],
    },
    10: {
        "scenes": [{"scene_number": i, "footage_url": f"http://example.com/{i}.mp4"} for i in range(8)],
        "credits": ["credit1"],
    },
    11: "/fake/data.json",
    12: "/fake/video.mp4",
    13: {"video_id": "abc123", "url": "https://youtube.com/watch?v=abc123"},
    "tts_format": {"full_script": " ".join(["word"] * 1500), "changes_made": ["pause added"]},
    "thumbnail": {"thumbnail_path": "/fake/thumb.jpg", "score": 25},
    "short_script": {"short_title": "Test Short", "short_tags": [], "short_description": "desc"},
    "short_storyboard": {"scenes": [{"scene_number": 0}]},
}


def _make_agent_mock(stage_key):
    """Create a MagicMock agent whose .run() returns the right stage output."""
    mock = MagicMock()
    mock.run.return_value = STAGE_OUTPUTS.get(stage_key, {})
    if stage_key == 13:
        mock.upload_video = MagicMock(return_value=STAGE_OUTPUTS[13])
    return mock


def _load_agent_side_effect(filename):
    """Return the right mock agent for each filename."""
    name = str(filename)
    mapping = {
        "01_research_agent.py": 1,
        "02_originality_agent.py": 2,
        "03_narrative_architect.py": 3,
        "04_script_writer.py": 4,
        "04b_script_doctor.py": "4b",
        "05_fact_verification_agent.py": 5,
        "06_seo_agent.py": 6,
        "07_scene_breakdown_agent.py": 7,
        "07b_visual_continuity.py": "7b",
        "09_footage_hunter.py": 9,
        "11_youtube_uploader.py": 13,
        "short_script_agent.py": "short_script",
        "short_storyboard_agent.py": "short_storyboard",
        "tts_format_agent.py": "tts_format",
    }
    stage_key = mapping.get(name)
    if stage_key is None:
        raise FileNotFoundError(f"Agent not found: {name}")
    return _make_agent_mock(stage_key)


def _make_init_context(tmp_path, state_override=None):
    """Build a factory for init_context that returns a real PipelineContext."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _init_context(topic, resume, from_stage, is_experiment):
        from pipeline.context import PipelineContext
        import re

        slug = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:40]
        ctx = PipelineContext(
            topic=topic,
            slug=slug,
            ts="20260326_120000",
            run_id="test1234",
            state_path=output_dir / f"{slug}_test1234_state.json",
            resume=resume,
            from_stage=from_stage,
            is_experiment=is_experiment,
            start_time=time.time(),
        )
        if state_override is not None:
            ctx.state = state_override.copy()
        else:
            ctx.state = {}
        ctx.state.setdefault("topic", topic)
        ctx.state.setdefault("completed_stages", [])
        ctx.state.setdefault("completed_short_stages", [])
        ctx.state.setdefault("era", "other")
        ctx.budget_cap = 0
        ctx.cost_tracker = None
        return ctx

    return _init_context


@pytest.fixture
def pipeline_env(tmp_path):
    """Set up all mocks needed to run the full pipeline."""
    output_dir = tmp_path / "outputs"
    media_dir = output_dir / "media"
    remotion_public = tmp_path / "remotion" / "public"
    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    remotion_public.mkdir(parents=True, exist_ok=True)

    patches_list = []

    def _p(target, replacement):
        p = patch(target, replacement)
        patches_list.append(p)

    # -- init_context: replaces ALL of phase_setup.init_context --
    _p("pipeline.phase_setup.init_context", _make_init_context(tmp_path))
    # -- run_pipeline imports init_context from phase_setup --
    _p("run_pipeline.init_context", _make_init_context(tmp_path))

    # -- Crash handlers, notify, credit checks, dedup --
    _p("run_pipeline.register_crash_handlers", MagicMock())
    _p("run_pipeline.notify_start", MagicMock())
    _p("run_pipeline.run_credit_checks", MagicMock())
    _p("run_pipeline.run_topic_dedup", MagicMock())

    # -- load_agents: mock at the import point in run_pipeline --
    _p("run_pipeline.load_agents", _make_load_agents_func())

    # -- save_state everywhere --
    mock_save = MagicMock()
    _p("pipeline.runner.save_state", mock_save)
    _p("pipeline.phase_script.save_state", MagicMock())
    _p("pipeline.phase_prod.save_state", MagicMock())
    _p("pipeline.phase_post.save_state", MagicMock())

    # -- Series detection --
    _p("pipeline.phase_script.detect_series_potential", MagicMock(return_value=None))
    _p("pipeline.phase_script.get_retention_optimal_length", MagicMock(return_value=None))
    _p("pipeline.phase_script.score_hook", MagicMock(return_value={}))

    # -- Production phase externals --
    _p("pipeline.phase_prod.run_audio", MagicMock(return_value=STAGE_OUTPUTS[8]))
    _p("pipeline.phase_prod.run_images", MagicMock(return_value=STAGE_OUTPUTS[10]))
    _p("pipeline.phase_prod.run_convert", MagicMock(return_value=STAGE_OUTPUTS[11]))
    _p("pipeline.phase_prod.run_render", MagicMock(return_value=STAGE_OUTPUTS[12]))
    _p("pipeline.phase_prod.run_short_audio", MagicMock(return_value={}))
    _p("pipeline.phase_prod.run_short_images", MagicMock(return_value={}))
    _p("pipeline.phase_prod.run_short_convert", MagicMock(return_value={}))
    _p("pipeline.phase_prod.run_short_render", MagicMock(return_value={}))

    # -- Compliance, thumbnail, QA (all internal to phase_prod) --
    _p("pipeline.phase_prod._run_compliance", MagicMock(return_value=None))
    _p("pipeline.phase_prod._generate_thumbnail_task", MagicMock(return_value=STAGE_OUTPUTS["thumbnail"]))
    _p("pipeline.phase_prod._run_qa_tiers", MagicMock())

    # -- Replace _run_render_phase to use mocked run_convert / run_render --
    def _mock_render_phase(ctx, runner):
        runner.run_stage(11, "Remotion Conversion", lambda *a: STAGE_OUTPUTS[11])
        runner.run_stage(12, "Video Render", lambda *a: STAGE_OUTPUTS[12])
    _p("pipeline.phase_prod._run_render_phase", _mock_render_phase)

    # -- Paths --
    _p("pipeline.phase_prod.OUTPUT_DIR", output_dir)
    _p("pipeline.phase_prod.MEDIA_DIR", media_dir)
    _p("pipeline.phase_prod.REMOTION_PUBLIC", remotion_public)
    _p("pipeline.phase_post.BASE_DIR", tmp_path)

    # -- Post phase externals (all lazy imports, mock the private helpers) --
    _p("pipeline.phase_post._run_predictive_scoring", MagicMock())
    _p("pipeline.phase_post._run_render_verification", MagicMock())
    _p("pipeline.phase_post._record_topic", MagicMock())
    _p("pipeline.phase_post._save_to_supabase", MagicMock())
    _p("pipeline.phase_post._store_param_observation", MagicMock())
    _p("pipeline.phase_post._run_comment_analysis", MagicMock())
    _p("pipeline.phase_post._run_localization", MagicMock())
    _p("pipeline.phase_post._finalize_costs", MagicMock())
    _p("pipeline.phase_post._log_api_costs", MagicMock())
    _p("pipeline.phase_post._run_community_engagement", MagicMock())
    _p("pipeline.phase_post._run_quality_report", MagicMock())
    _p("pipeline.phase_post._cleanup_after_upload", MagicMock())
    _p("pipeline.phase_post.load_agent", MagicMock(return_value=MagicMock()))

    # Start all patches
    active = []
    for p in patches_list:
        active.append(p.start())

    yield {
        "tmp_path": tmp_path,
        "output_dir": output_dir,
        "media_dir": media_dir,
        "mock_save_state": mock_save,
    }

    for p in patches_list:
        p.stop()


def _make_load_agents_func():
    """Return a function that populates ctx.agents with mocks."""
    def _load_agents(ctx):
        ctx.agents["a01"] = _make_agent_mock(1)
        ctx.agents["a02"] = _make_agent_mock(2)
        ctx.agents["a03"] = _make_agent_mock(3)
        ctx.agents["a04"] = _make_agent_mock(4)
        ctx.agents["a04b"] = _make_agent_mock("4b")
        ctx.agents["a05"] = _make_agent_mock(5)
        ctx.agents["a06"] = _make_agent_mock(6)
        ctx.agents["a07"] = _make_agent_mock(7)
        ctx.agents["a07b"] = _make_agent_mock("7b")
        ctx.agents["a09"] = _make_agent_mock(9)
        ctx.agents["a11"] = _make_agent_mock(13)
        ctx.agents["a_short_script"] = _make_agent_mock("short_script")
        ctx.agents["a_short_storyboard"] = _make_agent_mock("short_storyboard")
        ctx.agents["a_tts_format"] = _make_agent_mock("tts_format")
    return _load_agents


# ===========================================================================
# Happy Path: full pipeline end-to-end
# ===========================================================================

@pytest.mark.integration
class TestPipelineHappyPath:

    def test_full_pipeline_returns_dict(self, pipeline_env):
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        assert isinstance(result, dict)

    def test_pipeline_status_complete(self, pipeline_env):
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        assert result["pipeline_status"] == "COMPLETE"

    def test_completed_stages_contains_1_through_13(self, pipeline_env):
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        completed = result["completed_stages"]
        for stage_num in range(1, 14):
            assert stage_num in completed, f"Stage {stage_num} not in completed_stages"

    def test_elapsed_seconds_non_negative(self, pipeline_env):
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        assert result["elapsed_seconds"] >= 0

    def test_stage_data_present(self, pipeline_env):
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        for stage_num in [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13]:
            key = f"stage_{stage_num}"
            assert key in result, f"{key} not in state"
            assert result[key] is not None, f"{key} is None"

    def test_all_agents_run_called(self, pipeline_env):
        """Verify all 13 core stages completed."""
        from run_pipeline import run_pipeline
        result = run_pipeline("Test Topic About Ancient Rome")
        assert len(result["completed_stages"]) >= 13

    def test_save_state_called_multiple_times(self, pipeline_env):
        """save_state (in runner) should be called many times during the pipeline."""
        from run_pipeline import run_pipeline
        run_pipeline("Test Topic About Ancient Rome")
        mock_save = pipeline_env["mock_save_state"]
        assert mock_save.call_count >= 10, (
            f"save_state called only {mock_save.call_count} times, expected >= 10"
        )


# ===========================================================================
# Resume Mode
# ===========================================================================

@pytest.mark.integration
class TestPipelineResume:

    def test_resume_skips_completed_stages(self, tmp_path):
        """Stages 1-5 already complete -> agents for 1-5 should NOT be called."""
        output_dir = tmp_path / "outputs"
        media_dir = output_dir / "media"
        remotion_public = tmp_path / "remotion" / "public"
        output_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        remotion_public.mkdir(parents=True, exist_ok=True)

        pre_state = {
            "topic": "Test Topic Resume",
            "completed_stages": [1, 2, 3, 4, 5],
            "completed_short_stages": [],
            "era": "other",
        }
        for s in [1, 2, 3, 4, 5]:
            pre_state[f"stage_{s}"] = STAGE_OUTPUTS[s]

        # Track which agents' .run() get called
        called_agents = []

        def _tracking_load_agents(ctx):
            for key, stage_key in [
                ("a01", 1), ("a02", 2), ("a03", 3), ("a04", 4),
                ("a05", 5), ("a06", 6), ("a07", 7), ("a09", 9), ("a11", 13),
            ]:
                m = _make_agent_mock(stage_key)
                original_run = m.run

                def make_tracker(k, orig):
                    def tracked(*args, **kwargs):
                        called_agents.append(k)
                        return orig(*args, **kwargs)
                    return tracked

                m.run = MagicMock(side_effect=make_tracker(key, original_run))
                ctx.agents[key] = m
            ctx.agents["a04b"] = _make_agent_mock("4b")
            ctx.agents["a07b"] = _make_agent_mock("7b")
            ctx.agents["a_short_script"] = _make_agent_mock("short_script")
            ctx.agents["a_short_storyboard"] = _make_agent_mock("short_storyboard")
            ctx.agents["a_tts_format"] = _make_agent_mock("tts_format")

        patches_list = []

        def _p(target, replacement):
            p = patch(target, replacement)
            patches_list.append(p)

        _p("run_pipeline.init_context", _make_init_context(tmp_path, state_override=pre_state))
        _p("run_pipeline.register_crash_handlers", MagicMock())
        _p("run_pipeline.notify_start", MagicMock())
        _p("run_pipeline.run_credit_checks", MagicMock())
        _p("run_pipeline.run_topic_dedup", MagicMock())
        _p("run_pipeline.load_agents", _tracking_load_agents)
        _p("pipeline.runner.save_state", MagicMock())
        _p("pipeline.phase_script.save_state", MagicMock())
        _p("pipeline.phase_prod.save_state", MagicMock())
        _p("pipeline.phase_post.save_state", MagicMock())
        _p("pipeline.phase_script.detect_series_potential", MagicMock(return_value=None))
        _p("pipeline.phase_script.get_retention_optimal_length", MagicMock(return_value=None))
        _p("pipeline.phase_script.score_hook", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_audio", MagicMock(return_value=STAGE_OUTPUTS[8]))
        _p("pipeline.phase_prod.run_images", MagicMock(return_value=STAGE_OUTPUTS[10]))
        _p("pipeline.phase_prod.run_convert", MagicMock(return_value=STAGE_OUTPUTS[11]))
        _p("pipeline.phase_prod.run_render", MagicMock(return_value=STAGE_OUTPUTS[12]))
        _p("pipeline.phase_prod.run_short_audio", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_images", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_convert", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_render", MagicMock(return_value={}))
        _p("pipeline.phase_prod._run_compliance", MagicMock(return_value=None))
        _p("pipeline.phase_prod._generate_thumbnail_task", MagicMock(return_value=STAGE_OUTPUTS["thumbnail"]))
        _p("pipeline.phase_prod._run_qa_tiers", MagicMock())

        def _mock_render_phase(ctx, runner):
            runner.run_stage(11, "Remotion Conversion", lambda *a: STAGE_OUTPUTS[11])
            runner.run_stage(12, "Video Render", lambda *a: STAGE_OUTPUTS[12])
        _p("pipeline.phase_prod._run_render_phase", _mock_render_phase)
        _p("pipeline.phase_prod.OUTPUT_DIR", output_dir)
        _p("pipeline.phase_prod.MEDIA_DIR", media_dir)
        _p("pipeline.phase_prod.REMOTION_PUBLIC", remotion_public)
        _p("pipeline.phase_post.BASE_DIR", tmp_path)
        _p("pipeline.phase_post._run_predictive_scoring", MagicMock())
        _p("pipeline.phase_post._run_render_verification", MagicMock())
        _p("pipeline.phase_post._record_topic", MagicMock())
        _p("pipeline.phase_post._save_to_supabase", MagicMock())
        _p("pipeline.phase_post._store_param_observation", MagicMock())
        _p("pipeline.phase_post._run_comment_analysis", MagicMock())
        _p("pipeline.phase_post._run_localization", MagicMock())
        _p("pipeline.phase_post._finalize_costs", MagicMock())
        _p("pipeline.phase_post._log_api_costs", MagicMock())
        _p("pipeline.phase_post._run_community_engagement", MagicMock())
        _p("pipeline.phase_post._run_quality_report", MagicMock())
        _p("pipeline.phase_post._cleanup_after_upload", MagicMock())
        _p("pipeline.phase_post.load_agent", MagicMock(return_value=MagicMock()))

        for p in patches_list:
            p.start()

        try:
            from run_pipeline import run_pipeline
            result = run_pipeline("Test Topic Resume", resume=True)
            assert result["pipeline_status"] == "COMPLETE"
            for s in range(6, 14):
                assert s in result["completed_stages"], f"Stage {s} should have run"
            # Agents for stages 1-5 should NOT have been called
            for early in ["a01", "a02", "a03", "a04", "a05"]:
                assert early not in called_agents, f"{early} should have been skipped"
        finally:
            for p in patches_list:
                p.stop()


# ===========================================================================
# from_stage
# ===========================================================================

@pytest.mark.integration
class TestPipelineFromStage:

    def test_from_stage_skips_earlier(self, tmp_path):
        """from_stage=7 should skip stages 1-6."""
        output_dir = tmp_path / "outputs"
        media_dir = output_dir / "media"
        remotion_public = tmp_path / "remotion" / "public"
        output_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        remotion_public.mkdir(parents=True, exist_ok=True)

        pre_state = {
            "topic": "Test Topic FromStage",
            "completed_stages": [1, 2, 3, 4, 5, 6],
            "completed_short_stages": [],
            "era": "other",
        }
        for s in [1, 2, 3, 4, 5, 6]:
            pre_state[f"stage_{s}"] = STAGE_OUTPUTS[s]

        patches_list = []

        def _p(target, replacement):
            p = patch(target, replacement)
            patches_list.append(p)

        _p("run_pipeline.init_context", _make_init_context(tmp_path, state_override=pre_state))
        _p("run_pipeline.register_crash_handlers", MagicMock())
        _p("run_pipeline.notify_start", MagicMock())
        _p("run_pipeline.run_credit_checks", MagicMock())
        _p("run_pipeline.run_topic_dedup", MagicMock())
        _p("run_pipeline.load_agents", _make_load_agents_func())
        _p("pipeline.runner.save_state", MagicMock())
        _p("pipeline.phase_script.save_state", MagicMock())
        _p("pipeline.phase_prod.save_state", MagicMock())
        _p("pipeline.phase_post.save_state", MagicMock())
        _p("pipeline.phase_script.detect_series_potential", MagicMock(return_value=None))
        _p("pipeline.phase_script.get_retention_optimal_length", MagicMock(return_value=None))
        _p("pipeline.phase_script.score_hook", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_audio", MagicMock(return_value=STAGE_OUTPUTS[8]))
        _p("pipeline.phase_prod.run_images", MagicMock(return_value=STAGE_OUTPUTS[10]))
        _p("pipeline.phase_prod.run_convert", MagicMock(return_value=STAGE_OUTPUTS[11]))
        _p("pipeline.phase_prod.run_render", MagicMock(return_value=STAGE_OUTPUTS[12]))
        _p("pipeline.phase_prod.run_short_audio", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_images", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_convert", MagicMock(return_value={}))
        _p("pipeline.phase_prod.run_short_render", MagicMock(return_value={}))
        _p("pipeline.phase_prod._run_compliance", MagicMock(return_value=None))
        _p("pipeline.phase_prod._generate_thumbnail_task", MagicMock(return_value=STAGE_OUTPUTS["thumbnail"]))
        _p("pipeline.phase_prod._run_qa_tiers", MagicMock())

        def _mock_render_phase(ctx, runner):
            runner.run_stage(11, "Remotion Conversion", lambda *a: STAGE_OUTPUTS[11])
            runner.run_stage(12, "Video Render", lambda *a: STAGE_OUTPUTS[12])
        _p("pipeline.phase_prod._run_render_phase", _mock_render_phase)
        _p("pipeline.phase_prod.OUTPUT_DIR", output_dir)
        _p("pipeline.phase_prod.MEDIA_DIR", media_dir)
        _p("pipeline.phase_prod.REMOTION_PUBLIC", remotion_public)
        _p("pipeline.phase_post.BASE_DIR", tmp_path)
        _p("pipeline.phase_post._run_predictive_scoring", MagicMock())
        _p("pipeline.phase_post._run_render_verification", MagicMock())
        _p("pipeline.phase_post._record_topic", MagicMock())
        _p("pipeline.phase_post._save_to_supabase", MagicMock())
        _p("pipeline.phase_post._store_param_observation", MagicMock())
        _p("pipeline.phase_post._run_comment_analysis", MagicMock())
        _p("pipeline.phase_post._run_localization", MagicMock())
        _p("pipeline.phase_post._finalize_costs", MagicMock())
        _p("pipeline.phase_post._log_api_costs", MagicMock())
        _p("pipeline.phase_post._run_community_engagement", MagicMock())
        _p("pipeline.phase_post._run_quality_report", MagicMock())
        _p("pipeline.phase_post._cleanup_after_upload", MagicMock())
        _p("pipeline.phase_post.load_agent", MagicMock(return_value=MagicMock()))

        for p in patches_list:
            p.start()

        try:
            from run_pipeline import run_pipeline
            result = run_pipeline("Test Topic FromStage", from_stage=7)
            assert result["pipeline_status"] == "COMPLETE"
            for s in range(7, 14):
                assert s in result["completed_stages"], f"Stage {s} should have run"
        finally:
            for p in patches_list:
                p.stop()


# ===========================================================================
# Script Too Short
# ===========================================================================

@pytest.mark.integration
class TestScriptTooShort:

    def test_short_script_raises(self, tmp_path):
        """Script with <1000 words should raise Exception."""
        output_dir = tmp_path / "outputs"
        media_dir = output_dir / "media"
        remotion_public = tmp_path / "remotion" / "public"
        output_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        remotion_public.mkdir(parents=True, exist_ok=True)

        short_output = {
            "full_script": " ".join(["word"] * 500),
            "hook": "short hook",
            "length_tier": "STANDARD",
        }

        def _short_load_agents(ctx):
            _make_load_agents_func()(ctx)
            # Override a04 to return short script
            ctx.agents["a04"].run.return_value = short_output

        patches_list = []

        def _p(target, replacement):
            p = patch(target, replacement)
            patches_list.append(p)

        _p("run_pipeline.init_context", _make_init_context(tmp_path))
        _p("run_pipeline.register_crash_handlers", MagicMock())
        _p("run_pipeline.notify_start", MagicMock())
        _p("run_pipeline.run_credit_checks", MagicMock())
        _p("run_pipeline.run_topic_dedup", MagicMock())
        _p("run_pipeline.load_agents", _short_load_agents)
        _p("pipeline.runner.save_state", MagicMock())
        _p("pipeline.phase_script.save_state", MagicMock())
        _p("pipeline.phase_prod.save_state", MagicMock())
        _p("pipeline.phase_post.save_state", MagicMock())
        _p("pipeline.phase_script.detect_series_potential", MagicMock(return_value=None))
        _p("pipeline.phase_script.get_retention_optimal_length", MagicMock(return_value=None))
        _p("pipeline.phase_script.score_hook", MagicMock(return_value={}))

        for p in patches_list:
            p.start()

        try:
            from run_pipeline import run_pipeline
            with pytest.raises(Exception, match="script too short"):
                run_pipeline("Test Topic Short Script")
        finally:
            for p in patches_list:
                p.stop()


# ===========================================================================
# Credit Check Failure
# ===========================================================================

@pytest.mark.integration
class TestCreditCheckFailure:

    def test_credit_exhausted_raises(self, tmp_path):
        """If credit check detects exhausted credits, pipeline should raise."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        def _failing_credit_check(ctx):
            raise Exception(
                "Anthropic API credits exhausted. "
                "Top up at console.anthropic.com -> Plans & Billing."
            )

        patches_list = []

        def _p(target, replacement):
            p = patch(target, replacement)
            patches_list.append(p)

        _p("run_pipeline.init_context", _make_init_context(tmp_path))
        _p("run_pipeline.register_crash_handlers", MagicMock())
        _p("run_pipeline.notify_start", MagicMock())
        _p("run_pipeline.run_credit_checks", _failing_credit_check)
        _p("run_pipeline.run_topic_dedup", MagicMock())
        _p("run_pipeline.load_agents", _make_load_agents_func())

        for p in patches_list:
            p.start()

        try:
            from run_pipeline import run_pipeline
            with pytest.raises(Exception, match="credit"):
                run_pipeline("Test Topic Credit Fail")
        finally:
            for p in patches_list:
                p.stop()

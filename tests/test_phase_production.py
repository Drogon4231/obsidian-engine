"""Tests for pipeline/phase_prod.py and pipeline/phase_post.py — pure logic functions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from pipeline.context import PipelineContext
from pipeline.runner import StageRunner


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_ctx(tmp_path=None, **overrides) -> PipelineContext:
    """Build a minimal PipelineContext with sane defaults."""
    defaults = dict(
        topic="Test Topic",
        slug="test-topic",
        ts="20260326",
        state_path=Path("/tmp/test_state.json"),
        state={"completed_stages": []},
    )
    if tmp_path:
        defaults["state_path"] = tmp_path / "state.json"
    defaults.update(overrides)
    return PipelineContext(**defaults)


def _make_runner(ctx: PipelineContext) -> StageRunner:
    runner = StageRunner(ctx)
    runner.mark = MagicMock()
    runner.mark_metadata = MagicMock()
    runner.done = MagicMock(return_value=False)
    return runner


def _fake_module(name, **attrs):
    """Create a fake module with given attributes."""
    mod = ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# ═══════════════════════════════════════════════════════════════════════════════
# _check_and_warn
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckAndWarn:

    def _call(self, issues, stage_name):
        from pipeline.phase_prod import _check_and_warn
        _check_and_warn(issues, stage_name)

    def test_prints_warnings_when_issues_exist(self, capsys):
        self._call(["Bad title length", "Missing tags"], "SEO")
        out = capsys.readouterr().out
        assert "SEO quality issues" in out
        assert "Bad title length" in out
        assert "Missing tags" in out

    def test_silent_when_no_issues(self, capsys):
        self._call([], "SEO")
        assert capsys.readouterr().out == ""

    def test_silent_when_none(self, capsys):
        self._call(None, "SEO")
        assert capsys.readouterr().out == ""


# ═══════════════════════════════════════════════════════════════════════════════
# _run_compliance
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunCompliance:

    def _call(self, ctx, runner, mock_checker):
        """Call _run_compliance with a mocked compliance_checker module."""
        fake_core = _fake_module("core")
        fake_cc = _fake_module("core.compliance_checker", run=mock_checker)
        with patch.dict("sys.modules", {"core": fake_core, "core.compliance_checker": fake_cc}):
            from pipeline.phase_prod import _run_compliance
            return _run_compliance(ctx, runner)

    def test_returns_none_when_script_is_none(self):
        ctx = _make_ctx(script=None)
        runner = _make_runner(ctx)
        from pipeline.phase_prod import _run_compliance
        assert _run_compliance(ctx, runner) is None

    def test_returns_none_when_done(self):
        ctx = _make_ctx(script={"full_script": "some text"})
        runner = _make_runner(ctx)
        runner.done = MagicMock(return_value=True)
        from pipeline.phase_prod import _run_compliance
        assert _run_compliance(ctx, runner) is None

    def test_green_risk(self, capsys):
        mock_run = MagicMock(return_value={"risk_level": "green", "flags": []})
        ctx = _make_ctx(script={"full_script": "safe text"})
        runner = _make_runner(ctx)

        result = self._call(ctx, runner, mock_run)

        assert result == {"risk": "green", "flags": []}
        runner.mark_metadata.assert_called_once_with(
            "compliance", {"risk_level": "green", "flag_count": 0}
        )
        assert "GREEN" in capsys.readouterr().out

    def test_yellow_risk(self, capsys):
        flags = [{"category": "violence", "suggestion": "tone down"}]
        mock_run = MagicMock(return_value={"risk_level": "yellow", "flags": flags})
        ctx = _make_ctx(script={"full_script": "edgy text"})
        runner = _make_runner(ctx)

        result = self._call(ctx, runner, mock_run)

        assert result["risk"] == "yellow"
        assert len(result["flags"]) == 1
        runner.mark_metadata.assert_called_once()
        assert "YELLOW" in capsys.readouterr().out

    def test_red_risk_with_safe_script(self):
        safe = "word " * 501
        mock_run = MagicMock(return_value={
            "risk_level": "red",
            "flags": [{"severity": "high", "category": "drugs", "text_excerpt": "bad stuff"}],
            "safe_script": safe,
        })
        ctx = _make_ctx(script={"full_script": "risky"})
        runner = _make_runner(ctx)

        result = self._call(ctx, runner, mock_run)

        assert result["safe_script"] == safe
        assert result["risk"] == "red"

    def test_red_risk_without_safe_script(self, capsys):
        flags = [
            {"severity": "high", "category": "drugs", "text_excerpt": "bad stuff"},
            {"severity": "high", "category": "violence", "text_excerpt": "more bad"},
        ]
        mock_run = MagicMock(return_value={
            "risk_level": "red",
            "flags": flags,
            "safe_script": "",
        })
        ctx = _make_ctx(script={"full_script": "risky"})
        runner = _make_runner(ctx)

        result = self._call(ctx, runner, mock_run)

        assert result["risk"] == "red"
        assert "Could not auto-fix" in capsys.readouterr().out

    def test_exception_returns_none(self, capsys):
        mock_run = MagicMock(side_effect=RuntimeError("API down"))
        ctx = _make_ctx(script={"full_script": "text"})
        runner = _make_runner(ctx)

        result = self._call(ctx, runner, mock_run)

        assert result is None
        assert "Check skipped" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════════
# _build_manifest
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildManifest:

    def _call(self, ctx, runner):
        from pipeline.phase_prod import _build_manifest
        _build_manifest(ctx, runner)

    @patch("pipeline.phase_prod.save_state")
    def test_builds_manifest_when_not_done(self, mock_save, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Rome",
            seo={"recommended_title": "Fall of Rome"},
            audio_data={"total_duration_seconds": 600},
            footage_data={"scenes": [{"id": 1}], "credits": ["pexels"]},
            scenes_data={"visual_bible": {"palette": "warm"}},
        )
        runner = _make_runner(ctx)

        with patch("pipeline.phase_prod.MEDIA_DIR", media_dir):
            self._call(ctx, runner)

        assert ctx.manifest["topic"] == "Rome"
        assert ctx.manifest["title"] == "Fall of Rome"
        assert ctx.manifest["total_duration_seconds"] == 600
        assert ctx.manifest["scenes"] == [{"id": 1}]
        assert ctx.manifest["visual_bible"] == {"palette": "warm"}
        assert ctx.state["manifest"] == ctx.manifest

        manifest_file = media_dir / "media_manifest.json"
        assert manifest_file.exists()
        loaded = json.loads(manifest_file.read_text())
        assert loaded["topic"] == "Rome"

    def test_loads_from_file_when_done(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        manifest_data = {"topic": "Rome", "scenes": [{"id": 1}]}
        (media_dir / "media_manifest.json").write_text(json.dumps(manifest_data))

        ctx = _make_ctx(tmp_path=tmp_path)
        runner = _make_runner(ctx)
        runner.done = MagicMock(side_effect=lambda s: s == 9)

        with patch("pipeline.phase_prod.MEDIA_DIR", media_dir):
            self._call(ctx, runner)

        assert ctx.manifest == manifest_data

    def test_loads_from_state_when_done_no_file(self, tmp_path):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        saved_manifest = {"topic": "Rome", "scenes": [{"id": 2}]}
        ctx = _make_ctx(
            tmp_path=tmp_path,
            state={"completed_stages": [], "manifest": saved_manifest},
        )
        runner = _make_runner(ctx)
        runner.done = MagicMock(side_effect=lambda s: s == 9)

        with patch("pipeline.phase_prod.MEDIA_DIR", media_dir):
            self._call(ctx, runner)

        assert ctx.manifest == saved_manifest

    def test_reconstructs_from_stage9_when_no_manifest(self, tmp_path, capsys):
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Rome",
            seo={"recommended_title": "Fall of Rome"},
            state={
                "completed_stages": [],
                "manifest": {},
                "stage_9": {"scenes": [{"id": 3}], "credits": ["archive"]},
                "stage_8": {"total_duration_seconds": 500},
            },
        )
        runner = _make_runner(ctx)
        runner.done = MagicMock(side_effect=lambda s: s == 9)

        with patch("pipeline.phase_prod.MEDIA_DIR", media_dir):
            self._call(ctx, runner)

        assert ctx.manifest["scenes"] == [{"id": 3}]
        assert ctx.manifest["total_duration_seconds"] == 500
        assert "Reconstructed manifest" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════════
# _run_qa_tiers
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunQaTiers:

    def _call(self, ctx, runner):
        from pipeline.phase_prod import _run_qa_tiers
        _run_qa_tiers(ctx, runner)

    @patch("pipeline.phase_prod.save_state")
    def test_tier1_passes(self, mock_save, capsys):
        t1_result = {"passed": True, "errors": [], "warnings": [], "metrics": {}}
        t2_result = {"passed": True, "warnings": [], "sync_score": 0.95}
        fake_qg = _fake_module(
            "core.quality_gates",
            run_tier1_postrender=MagicMock(return_value=t1_result),
            run_tier2_content=MagicMock(return_value=t2_result),
        )
        with patch.dict("sys.modules", {"core.quality_gates": fake_qg}):
            ctx = _make_ctx(state={"completed_stages": [], "stage_12": "/video.mp4"})
            runner = _make_runner(ctx)
            self._call(ctx, runner)

        assert ctx.state["qa_tier1"] == t1_result
        assert "Post-render validation passed" in capsys.readouterr().out

    @patch("pipeline.phase_prod.save_state")
    def test_tier1_fails_prints_errors(self, mock_save, capsys):
        t1_result = {
            "passed": False,
            "errors": ["Duration mismatch"],
            "warnings": ["Low bitrate"],
            "metrics": {"bitrate": 1000},
        }
        t2_result = {"passed": True, "warnings": [], "sync_score": 0.9}
        fake_qg = _fake_module(
            "core.quality_gates",
            run_tier1_postrender=MagicMock(return_value=t1_result),
            run_tier2_content=MagicMock(return_value=t2_result),
        )
        with patch.dict("sys.modules", {"core.quality_gates": fake_qg}):
            ctx = _make_ctx(state={"completed_stages": [], "stage_12": "/video.mp4"})
            runner = _make_runner(ctx)
            self._call(ctx, runner)

        assert ctx.state["qa_tier1"] == t1_result
        out = capsys.readouterr().out
        assert "Duration mismatch" in out
        assert "Low bitrate" in out

    @patch("pipeline.phase_prod.save_state")
    def test_tier2_passes_prints_sync(self, mock_save, capsys):
        t1_result = {"passed": True, "errors": [], "warnings": [], "metrics": {}}
        t2_result = {"passed": True, "warnings": [], "sync_score": 0.95}
        fake_qg = _fake_module(
            "core.quality_gates",
            run_tier1_postrender=MagicMock(return_value=t1_result),
            run_tier2_content=MagicMock(return_value=t2_result),
        )
        with patch.dict("sys.modules", {"core.quality_gates": fake_qg}):
            ctx = _make_ctx(state={"completed_stages": [], "stage_12": "/video.mp4"})
            runner = _make_runner(ctx)
            self._call(ctx, runner)

        assert ctx.state["qa_tier2"] == t2_result
        assert "95%" in capsys.readouterr().out

    def test_import_error_silently_skips(self):
        """When quality_gates can't be imported, QA is silently skipped."""
        real_import = __import__

        def blocker(name, *args, **kwargs):
            if name == "core.quality_gates":
                raise ImportError(f"Mocked: {name} not available")
            return real_import(name, *args, **kwargs)

        saved = sys.modules.pop("core.quality_gates", "_MISSING")
        try:
            with patch("builtins.__import__", side_effect=blocker):
                ctx = _make_ctx(state={"completed_stages": []})
                runner = _make_runner(ctx)
                self._call(ctx, runner)
            assert "qa_tier1" not in ctx.state
            assert "qa_tier2" not in ctx.state
        finally:
            if saved != "_MISSING":
                sys.modules["core.quality_gates"] = saved


# ═══════════════════════════════════════════════════════════════════════════════
# _run_predictive_scoring (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunPredictiveScoring:

    def _call(self, ctx):
        from pipeline.phase_post import _run_predictive_scoring
        _run_predictive_scoring(ctx)

    @patch("pipeline.phase_post.save_state")
    def test_era_match_adds_score(self, mock_save, tmp_path):
        insights = {"era_performance_ranking": [{"era": "Rome"}]}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Fall of Rome",
            seo={"recommended_title": "x" * 55, "tags": []},
            script={"full_script": "word " * 100},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert any("Era match" in r for r in ps["reasons"])
        assert ps["score"] >= 5

    @patch("pipeline.phase_post.save_state")
    def test_optimal_title_length(self, mock_save, tmp_path):
        insights = {"era_performance_ranking": []}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Test",
            seo={"recommended_title": "x" * 55, "tags": []},
            script={"full_script": "word " * 100},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert any("Optimal title" in r for r in ps["reasons"])
        assert ps["score"] >= 3

    @patch("pipeline.phase_post.save_state")
    def test_short_title_subtracts(self, mock_save, tmp_path):
        insights = {"era_performance_ranking": []}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Test",
            seo={"recommended_title": "Short", "tags": []},
            script={"full_script": "word " * 100},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert any("too short" in r for r in ps["reasons"])
        assert ps["score"] <= -1

    @patch("pipeline.phase_post.save_state")
    def test_good_script_length(self, mock_save, tmp_path):
        insights = {"era_performance_ranking": []}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Test",
            seo={"recommended_title": "x" * 35, "tags": []},
            script={"full_script": "word " * 1500},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert any("Good script length" in r for r in ps["reasons"])

    @patch("pipeline.phase_post.save_state")
    def test_strong_tag_coverage(self, mock_save, tmp_path):
        insights = {"era_performance_ranking": []}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Test",
            seo={"recommended_title": "x" * 35, "tags": ["t"] * 12},
            script={"full_script": "word " * 100},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert any("Strong tag" in r for r in ps["reasons"])

    @patch("pipeline.phase_post.save_state")
    def test_saves_predictive_score_to_state(self, mock_save, tmp_path):
        """Verify save_state is called after scoring."""
        insights = {"era_performance_ranking": []}
        (tmp_path / "channel_insights.json").write_text(json.dumps(insights))

        ctx = _make_ctx(
            tmp_path=tmp_path,
            topic="Test",
            seo={"recommended_title": "x" * 55, "tags": ["t"] * 12},
            script={"full_script": "word " * 1600},
        )

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        ps = ctx.state["predictive_score"]
        assert ps["max"] == 11
        mock_save.assert_called_once()

    def test_no_insights_file_no_error(self, tmp_path):
        ctx = _make_ctx(tmp_path=tmp_path, topic="Test")

        with patch("pipeline.phase_post.BASE_DIR", tmp_path):
            self._call(ctx)

        assert "predictive_score" not in ctx.state


# ═══════════════════════════════════════════════════════════════════════════════
# _record_topic (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordTopic:

    def _call(self, ctx):
        from pipeline.phase_post import _record_topic
        _record_topic(ctx)

    def test_calls_topic_store(self):
        mock_record = MagicMock()
        fake_ts = _fake_module("server.topic_store", record_topic=mock_record)
        fake_server = _fake_module("server", topic_store=fake_ts)

        ctx = _make_ctx(
            topic="Rome",
            angle={"unique_angle": "military decline"},
            seo={"recommended_title": "Fall of Rome"},
            state={"completed_stages": [], "stage_13": {"video_id": "abc123"}},
        )

        with patch.dict("sys.modules", {"server": fake_server, "server.topic_store": fake_ts}):
            self._call(ctx)

        mock_record.assert_called_once_with(
            topic="Rome",
            angle="military decline",
            title="Fall of Rome",
            youtube_id="abc123",
        )

    def test_uses_chosen_angle_fallback(self):
        mock_record = MagicMock()
        fake_ts = _fake_module("server.topic_store", record_topic=mock_record)
        fake_server = _fake_module("server", topic_store=fake_ts)

        ctx = _make_ctx(
            topic="Rome",
            angle={"chosen_angle": "economic collapse"},
            seo={"recommended_title": "Fall of Rome"},
            state={"completed_stages": [], "stage_13": {"video_id": "abc123"}},
        )

        with patch.dict("sys.modules", {"server": fake_server, "server.topic_store": fake_ts}):
            self._call(ctx)

        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["angle"] == "economic collapse"

    def test_exception_prints_warning(self, capsys):
        mock_record = MagicMock(side_effect=RuntimeError("DB down"))
        fake_ts = _fake_module("server.topic_store", record_topic=mock_record)
        fake_server = _fake_module("server", topic_store=fake_ts)

        ctx = _make_ctx(
            topic="Rome",
            state={"completed_stages": [], "stage_13": {}},
        )

        with patch.dict("sys.modules", {"server": fake_server, "server.topic_store": fake_ts}):
            self._call(ctx)

        assert "topic_store warning" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════════
# _save_to_supabase (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveToSupabase:

    def _call(self, ctx):
        from pipeline.phase_post import _save_to_supabase
        _save_to_supabase(ctx)

    def test_calls_save_video(self):
        mock_save_video = MagicMock()
        fake_sb = _fake_module("clients.supabase_client", save_video=mock_save_video)
        fake_clients = _fake_module("clients", supabase_client=fake_sb)

        ctx = _make_ctx(
            topic="Rome",
            seo={"recommended_title": "Fall of Rome"},
            audio_data={"total_duration_seconds": 600},
            script={"full_script": "word " * 1500, "word_count": 1500},
            state={
                "completed_stages": [],
                "stage_13": {"url": "https://yt/abc", "video_id": "abc"},
                "script_path": "/out/script.txt",
            },
        )

        with patch.dict("sys.modules", {"clients": fake_clients, "clients.supabase_client": fake_sb}):
            self._call(ctx)

        mock_save_video.assert_called_once()
        kw = mock_save_video.call_args.kwargs
        assert kw["topic"] == "Rome"
        assert kw["title"] == "Fall of Rome"
        assert kw["youtube_id"] == "abc"
        assert kw["duration_seconds"] == 600

    def test_no_upload_result_skips(self):
        mock_save_video = MagicMock()
        fake_sb = _fake_module("clients.supabase_client", save_video=mock_save_video)
        fake_clients = _fake_module("clients", supabase_client=fake_sb)

        ctx = _make_ctx(
            topic="Rome",
            state={"completed_stages": [], "stage_13": {}},
        )

        with patch.dict("sys.modules", {"clients": fake_clients, "clients.supabase_client": fake_sb}):
            self._call(ctx)

        mock_save_video.assert_not_called()

    def test_exception_prints_warning(self, capsys):
        mock_save_video = MagicMock(side_effect=RuntimeError("DB error"))
        fake_sb = _fake_module("clients.supabase_client", save_video=mock_save_video)
        fake_clients = _fake_module("clients", supabase_client=fake_sb)

        ctx = _make_ctx(
            topic="Rome",
            state={
                "completed_stages": [],
                "stage_13": {"url": "https://yt/abc", "video_id": "abc"},
            },
        )

        with patch.dict("sys.modules", {"clients": fake_clients, "clients.supabase_client": fake_sb}):
            self._call(ctx)

        assert "could not save video to Supabase" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════════
# _store_param_observation (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreParamObservation:

    def _call(self, ctx):
        from pipeline.phase_post import _store_param_observation
        _store_param_observation(ctx)

    def test_calls_store_observation(self):
        mock_store = MagicMock()
        fake_ph = _fake_module("core.param_history", store_observation=mock_store)

        ctx = _make_ctx(
            state={
                "completed_stages": [],
                "stage_13": {"video_id": "abc123"},
                "production_params": {"voice_speed": 0.88},
                "era": "roman",
                "render_verification": {"compliance": 0.95},
            },
        )

        with patch.dict("sys.modules", {"core.param_history": fake_ph}):
            self._call(ctx)

        mock_store.assert_called_once_with(
            video_id="abc123",
            youtube_id="abc123",
            params={"voice_speed": 0.88},
            era="roman",
            render_verification={"compliance": 0.95},
        )

    def test_no_upload_result_skips(self):
        mock_store = MagicMock()
        fake_ph = _fake_module("core.param_history", store_observation=mock_store)

        ctx = _make_ctx(state={"completed_stages": [], "stage_13": {}})

        with patch.dict("sys.modules", {"core.param_history": fake_ph}):
            self._call(ctx)

        mock_store.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# _finalize_costs (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinalizeCosts:

    def _call(self, ctx):
        from pipeline.phase_post import _finalize_costs
        _finalize_costs(ctx)

    def test_when_cost_tracker_exists(self, capsys):
        mock_tracker = MagicMock()
        mock_tracker.get_cost_estimate.return_value = {"total_cost": 1.50}

        mock_get_costs = MagicMock(return_value={"usd_total": 1.23})
        fake_cc = _fake_module("clients.claude_client", get_session_costs=mock_get_costs)

        ctx = _make_ctx(
            state={"completed_stages": [], "stage_13": {"video_id": "abc"}},
        )
        ctx.cost_tracker = mock_tracker
        ctx.cost_run_id = "run_001"

        with patch.dict("sys.modules", {"clients.claude_client": fake_cc}):
            self._call(ctx)

        mock_tracker.log_usd_cost.assert_called_once_with("run_001", "pipeline_total", "claude_all", 1.23)
        mock_tracker.end_run.assert_called_once_with("run_001", video_id="abc")
        mock_tracker.get_cost_estimate.assert_called_once_with("run_001")
        assert ctx.state["cost_estimate"] == {"total_cost": 1.50}
        assert "$1.50" in capsys.readouterr().out

    def test_when_cost_tracker_is_none(self):
        ctx = _make_ctx()
        ctx.cost_tracker = None
        # Should do nothing, no crash
        self._call(ctx)

    def test_zero_usd_skips_log(self):
        """When usd_total is 0, log_usd_cost should NOT be called."""
        mock_tracker = MagicMock()
        mock_tracker.get_cost_estimate.return_value = None

        mock_get_costs = MagicMock(return_value={"usd_total": 0.0})
        fake_cc = _fake_module("clients.claude_client", get_session_costs=mock_get_costs)

        ctx = _make_ctx(
            state={"completed_stages": [], "stage_13": {}},
        )
        ctx.cost_tracker = mock_tracker
        ctx.cost_run_id = "run_002"

        with patch.dict("sys.modules", {"clients.claude_client": fake_cc}):
            self._call(ctx)

        mock_tracker.log_usd_cost.assert_not_called()
        mock_tracker.end_run.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _log_api_costs (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogApiCosts:

    def _call(self, ctx):
        from pipeline.phase_post import _log_api_costs
        _log_api_costs(ctx)

    def test_merges_cost_estimate(self, capsys):
        mock_get_costs = MagicMock(return_value={"usd_total": 0.50, "calls": 10})
        fake_cc = _fake_module("clients.claude_client", get_session_costs=mock_get_costs)

        ctx = _make_ctx(
            state={
                "completed_stages": [],
                "cost_estimate": {
                    "total_cost": 1.75,
                    "per_stage": {"stage_1": 0.10},
                    "per_service": {"claude": 1.50},
                },
            },
        )

        with patch.dict("sys.modules", {"clients.claude_client": fake_cc}):
            self._call(ctx)

        costs = ctx.state["costs"]
        assert costs["usd_total"] == 1.75
        assert costs["per_stage"] == {"stage_1": 0.10}
        assert costs["per_service"] == {"claude": 1.50}

    def test_sets_costs_without_estimate(self, capsys):
        mock_get_costs = MagicMock(return_value={"usd_total": 0.50, "calls": 10})
        fake_cc = _fake_module("clients.claude_client", get_session_costs=mock_get_costs)

        ctx = _make_ctx(state={"completed_stages": []})

        with patch.dict("sys.modules", {"clients.claude_client": fake_cc}):
            self._call(ctx)

        assert ctx.state["costs"]["usd_total"] == 0.50


# ═══════════════════════════════════════════════════════════════════════════════
# _run_quality_report (phase_post.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunQualityReport:

    def _call(self, ctx):
        from pipeline.phase_post import _run_quality_report
        _run_quality_report(ctx)

    def _make_state_with_stages(self):
        return {
            "completed_stages": [],
            "stage_1": {"era": "rome"},
            "stage_2": {"angle": "decline"},
            "stage_4": {"full_script": "text"},
            "stage_6": {"tags": []},
            "stage_7": {"scenes": []},
            "stage_8": {"audio": "ok"},
            "stage_9": {"footage": "ok"},
            "stage_12": "/video.mp4",
            "manifest": {"scenes": []},
        }

    def test_prints_warnings_when_present(self, capsys):
        mock_run_all = MagicMock(return_value={
            "warnings": ["Audio peak too loud"],
            "total_warnings": 1,
            "metrics": {"score": 85},
        })
        fake_qg = _fake_module("core.quality_gates", run_all_quality_checks=mock_run_all)
        fake_core = _fake_module("core", quality_gates=fake_qg)

        ctx = _make_ctx(state=self._make_state_with_stages())

        with patch.dict("sys.modules", {"core": fake_core, "core.quality_gates": fake_qg}):
            self._call(ctx)

        out = capsys.readouterr().out
        assert "Audio peak too loud" in out
        assert "1 warning" in out

    def test_all_checks_passed(self, capsys):
        mock_run_all = MagicMock(return_value={
            "warnings": [],
            "total_warnings": 0,
            "metrics": {"score": 100},
        })
        fake_qg = _fake_module("core.quality_gates", run_all_quality_checks=mock_run_all)
        fake_core = _fake_module("core", quality_gates=fake_qg)

        ctx = _make_ctx(state=self._make_state_with_stages())

        with patch.dict("sys.modules", {"core": fake_core, "core.quality_gates": fake_qg}):
            self._call(ctx)

        assert "All checks passed" in capsys.readouterr().out

    def test_calls_with_correct_pipeline_outputs(self):
        mock_run_all = MagicMock(return_value={
            "warnings": [],
            "total_warnings": 0,
            "metrics": {},
        })
        fake_qg = _fake_module("core.quality_gates", run_all_quality_checks=mock_run_all)
        fake_core = _fake_module("core", quality_gates=fake_qg)

        state = self._make_state_with_stages()
        ctx = _make_ctx(state=state)

        with patch.dict("sys.modules", {"core": fake_core, "core.quality_gates": fake_qg}):
            self._call(ctx)

        call_args = mock_run_all.call_args[0][0]
        assert call_args["research"] == {"era": "rome"}
        assert call_args["angle"] == {"angle": "decline"}
        assert call_args["script"] == {"full_script": "text"}
        assert call_args["seo"] == {"tags": []}
        assert call_args["video_path"] == "/video.mp4"
        assert call_args["images"] == {"scenes": []}

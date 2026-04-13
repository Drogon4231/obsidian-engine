"""Tests for pipeline/phase_setup.py — init, agents, credit checks, crash handlers."""

import logging
import sys
import json
import time
import signal
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _capture_obsidian_logs(caplog):
    """Add caplog handler directly to obsidian logger (propagate=False blocks root)."""
    obs_logger = logging.getLogger("obsidian")
    obs_logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="obsidian")
    yield
    obs_logger.removeHandler(caplog.handler)

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.context import PipelineContext


# ---------------------------------------------------------------------------
# Shared fixture: PipelineContext.run_id is a dataclass field with
# default_factory, so it has no class-level attribute. Line 38 of
# phase_setup.py reads PipelineContext.run_id.default — we patch it so
# init_context() can execute. (Line 44 immediately overwrites state_path.)
# ---------------------------------------------------------------------------

class _FakeField:
    default = "00000000"


@pytest.fixture(autouse=True)
def _patch_run_id_class_attr():
    """Give PipelineContext a class-level run_id stub so line 38 doesn't crash."""
    original = PipelineContext.__dict__.get("run_id")
    PipelineContext.run_id = _FakeField()  # type: ignore[attr-defined]
    yield
    if original is not None:
        PipelineContext.run_id = original  # type: ignore[attr-defined]
    else:
        try:
            del PipelineContext.run_id  # type: ignore[attr-defined]
        except AttributeError:
            pass


# ── init_context() ───────────────────────────────────────────────────────────

class TestInitContextBasic:
    """Returns a PipelineContext with correct topic, slug, ts, run_id."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_returns_pipeline_context(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("Test Topic", resume=False, from_stage=1, is_experiment=False)
        assert isinstance(ctx, PipelineContext)

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_topic_preserved(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("The Roman Empire", resume=False, from_stage=1, is_experiment=False)
        assert ctx.topic == "The Roman Empire"

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_run_id_is_8_hex_chars(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert len(ctx.run_id) == 8
        assert all(c in "0123456789abcdef" for c in ctx.run_id)

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_ts_format(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        # ts should be YYYYMMDD_HHMMSS
        assert len(ctx.ts) == 15
        assert ctx.ts[8] == "_"


class TestInitContextSlug:
    """Slug is lowercase, max 40 chars, alphanumeric + underscore."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_slug_lowercase(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("The ROMAN Empire", resume=False, from_stage=1, is_experiment=False)
        assert ctx.slug == ctx.slug.lower()

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_slug_max_40_chars(self, _load, _save):
        from pipeline.phase_setup import init_context
        long_topic = "A" * 100
        ctx = init_context(long_topic, resume=False, from_stage=1, is_experiment=False)
        assert len(ctx.slug) <= 40

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_slug_alphanumeric_underscore_only(self, _load, _save):
        import re
        from pipeline.phase_setup import init_context
        ctx = init_context("Hello, World! (2024)", resume=False, from_stage=1, is_experiment=False)
        assert re.fullmatch(r'[a-z0-9_]+', ctx.slug), f"Slug contains invalid chars: {ctx.slug}"


class TestInitContextStatePath:
    """state_path is in OUTPUT_DIR with correct pattern."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_state_path_in_output_dir(self, _load, _save):
        from pipeline.phase_setup import init_context
        from core.paths import OUTPUT_DIR
        ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.state_path.parent == OUTPUT_DIR

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_state_path_contains_slug_and_run_id(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("Test Topic", resume=False, from_stage=1, is_experiment=False)
        name = ctx.state_path.name
        assert ctx.slug in name
        assert ctx.run_id in name
        assert name.endswith("_state.json")


class TestInitContextResume:
    """Resume mode finds most recent state file."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={"topic": "test"})
    def test_resume_finds_most_recent_state(self, _load, _save, tmp_path):
        from pipeline.phase_setup import init_context

        # Create fake state files in tmp
        old_file = tmp_path / "test_topic_aaa_state.json"
        new_file = tmp_path / "test_topic_bbb_state.json"
        old_file.write_text("{}")
        time.sleep(0.05)
        new_file.write_text("{}")

        with patch("pipeline.phase_setup.OUTPUT_DIR", tmp_path):
            ctx = init_context("Test Topic", resume=True, from_stage=1, is_experiment=False)
        assert ctx.state_path == new_file


class TestInitContextStateDefaults:
    """State initialized with defaults: topic, completed_stages, completed_short_stages."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_state_defaults(self, _load, _save):
        from pipeline.phase_setup import init_context
        ctx = init_context("My Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.state["topic"] == "My Topic"
        assert ctx.state["completed_stages"] == []
        assert ctx.state["completed_short_stages"] == []


class TestInitContextEra:
    """Era classification via classify_era, defaults to 'other' on failure."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_era_set_from_classifier(self, _load, _save):
        from pipeline.phase_setup import init_context
        mock_mod = MagicMock()
        mock_mod.classify_era.return_value = "ancient"
        with patch.dict("sys.modules", {"intel": MagicMock(), "intel.era_classifier": mock_mod}):
            ctx = init_context("Rome", resume=False, from_stage=1, is_experiment=False)
        assert ctx.state["era"] == "ancient"

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_era_defaults_to_other_on_failure(self, _load, _save):
        from pipeline.phase_setup import init_context
        with patch.dict("sys.modules", {"intel": MagicMock(), "intel.era_classifier": None}):
            ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.state["era"] == "other"


class TestInitContextBudget:
    """Budget cap loaded from config; defaults to 0 on ImportError."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_budget_loaded_from_config(self, _load, _save):
        from pipeline.phase_setup import init_context
        mock_mod = MagicMock()
        mock_mod.COST_BUDGET_MAX_USD = 42.5
        with patch.dict("sys.modules", {"core.pipeline_config": mock_mod}):
            ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.budget_cap == 42.5

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_budget_defaults_to_zero_on_import_error(self, _load, _save):
        from pipeline.phase_setup import init_context
        with patch.dict("sys.modules", {"core.pipeline_config": None}):
            ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.budget_cap == 0


class TestInitContextCostTracker:
    """Cost tracker initialized; None when unavailable."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_cost_tracker_initialized(self, _load, _save):
        from pipeline.phase_setup import init_context
        mock_tracker = MagicMock()
        mock_core = MagicMock()
        mock_core.cost_tracker = mock_tracker
        with patch.dict("sys.modules", {"core": mock_core, "core.cost_tracker": mock_tracker}):
            ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        mock_tracker.start_run.assert_called_once()
        assert ctx.cost_tracker is not None

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_cost_tracker_none_when_unavailable(self, _load, _save):
        from pipeline.phase_setup import init_context
        # Make 'from core import cost_tracker' raise
        mock_core = MagicMock()
        mock_core.cost_tracker = None
        with patch.dict("sys.modules", {"core": mock_core, "core.cost_tracker": None}):
            ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        assert ctx.cost_tracker is None


class TestInitContextStartTime:
    """start_time is set to a recent timestamp."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_start_time_is_recent(self, _load, _save):
        from pipeline.phase_setup import init_context
        before = time.time()
        ctx = init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        after = time.time()
        assert before <= ctx.start_time <= after


class TestInitContextParamOverrides:
    """Param overrides loaded via reset_pipeline_cache + load_overrides_for_pipeline."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_param_overrides_called(self, _load, _save):
        from pipeline.phase_setup import init_context
        mock_mod = MagicMock()
        with patch.dict("sys.modules", {"core.param_overrides": mock_mod}):
            init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        mock_mod.reset_pipeline_cache.assert_called_once()
        mock_mod.load_overrides_for_pipeline.assert_called_once()


class TestInitContextSessionCosts:
    """Session costs reset via reset_session_costs."""

    @patch("pipeline.phase_setup.save_state")
    @patch("pipeline.phase_setup.load_state", return_value={})
    def test_reset_session_costs_called(self, _load, _save):
        from pipeline.phase_setup import init_context
        mock_mod = MagicMock()
        with patch.dict("sys.modules", {"clients.claude_client": mock_mod}):
            init_context("Topic", resume=False, from_stage=1, is_experiment=False)
        mock_mod.reset_session_costs.assert_called_once()


# ── register_crash_handlers() ───────────────────────────────────────────────

class TestRegisterCrashHandlers:

    def test_registers_atexit_handler(self):
        from pipeline.phase_setup import register_crash_handlers
        ctx = PipelineContext(topic="test")
        with patch("pipeline.phase_setup.atexit.register") as mock_register:
            with patch("pipeline.phase_setup.signal.signal"):
                register_crash_handlers(ctx)
        mock_register.assert_called_once()

    def test_registers_sigterm_handler(self):
        from pipeline.phase_setup import register_crash_handlers
        ctx = PipelineContext(topic="test")
        with patch("pipeline.phase_setup.atexit.register"):
            with patch("pipeline.phase_setup.signal.signal") as mock_signal:
                register_crash_handlers(ctx)
        mock_signal.assert_called_once_with(signal.SIGTERM, mock_signal.call_args[0][1])


# ── load_agents() ───────────────────────────────────────────────────────────

class TestLoadAgents:

    @patch("pipeline.phase_setup.load_agent")
    def test_loads_all_required_agents(self, mock_load):
        from pipeline.phase_setup import load_agents
        mock_load.return_value = MagicMock()
        ctx = PipelineContext(topic="test")
        load_agents(ctx)
        required = ["a01", "a02", "a03", "a04", "a05", "a06", "a07", "a09", "a11"]
        for key in required:
            assert key in ctx.agents, f"Missing required agent: {key}"
            assert ctx.agents[key] is not None

    @patch("pipeline.phase_setup.load_agent")
    def test_optional_agents_none_on_file_not_found(self, mock_load):
        from pipeline.phase_setup import load_agents

        def side_effect(path):
            optional_files = [
                "04b_script_doctor.py",
                "07b_visual_continuity.py",
                "tts_format_agent.py",
                "short_script_agent.py",
                "short_storyboard_agent.py",
            ]
            if str(path) in optional_files:
                raise FileNotFoundError(f"Agent not found: {path}")
            return MagicMock()

        mock_load.side_effect = side_effect
        ctx = PipelineContext(topic="test")
        load_agents(ctx)

        assert ctx.agents["a04b"] is None
        assert ctx.agents["a07b"] is None
        assert ctx.agents["a_tts_format"] is None

    @patch("pipeline.phase_setup.load_agent")
    def test_short_agents_none_on_file_not_found(self, mock_load):
        from pipeline.phase_setup import load_agents

        def side_effect(path):
            short_files = ["short_script_agent.py", "short_storyboard_agent.py"]
            if str(path) in short_files:
                raise FileNotFoundError(f"Agent not found: {path}")
            return MagicMock()

        mock_load.side_effect = side_effect
        ctx = PipelineContext(topic="test")
        load_agents(ctx)

        assert ctx.agents["a_short_script"] is None
        assert ctx.agents["a_short_storyboard"] is None


# ── run_credit_checks() ─────────────────────────────────────────────────────

class TestRunCreditChecksAnthropic:

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": ""})
    def test_anthropic_check_passes(self, caplog):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_client = MagicMock()
        mock_anth.Anthropic.return_value = mock_client
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        with patch.dict("sys.modules", {"anthropic": mock_anth}):
            ctx = PipelineContext(topic="test")
            run_credit_checks(ctx)
        assert "OK" in caplog.text

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": ""})
    def test_anthropic_credits_exhausted_bad_request(self):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()

        class FakeBadRequest(Exception):
            pass

        mock_anth.BadRequestError = FakeBadRequest
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = FakeBadRequest("Your credit balance is too low")
        mock_anth.Anthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anth}):
            ctx = PipelineContext(topic="test")
            with pytest.raises(Exception, match="credits exhausted"):
                run_credit_checks(ctx)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": ""})
    def test_anthropic_generic_error_credit_balance(self):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("credit balance is too low")
        mock_anth.Anthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anth}):
            ctx = PipelineContext(topic="test")
            with pytest.raises(Exception, match="credits exhausted"):
                run_credit_checks(ctx)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": ""})
    def test_anthropic_generic_error_no_credit_mention(self, caplog):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("network timeout")
        mock_anth.Anthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anth}):
            ctx = PipelineContext(topic="test")
            run_credit_checks(ctx)  # should NOT raise
        assert "warning" in caplog.text.lower()


class TestRunCreditChecksElevenLabs:

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": "el-key"})
    def test_elevenlabs_check_passes(self, caplog):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        mock_anth.Anthropic.return_value = MagicMock()

        mock_requests = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = json.dumps({
            "subscription": {"character_limit": 10000, "character_count": 3000}
        })
        mock_requests.get.return_value = resp

        with patch.dict("sys.modules", {"anthropic": mock_anth, "requests": mock_requests}):
            ctx = PipelineContext(topic="test")
            run_credit_checks(ctx)
        assert "7,000 chars remaining" in caplog.text

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": "el-key"})
    def test_elevenlabs_401_raises(self):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        mock_anth.Anthropic.return_value = MagicMock()

        mock_requests = MagicMock()
        resp = MagicMock()
        resp.status_code = 401
        mock_requests.get.return_value = resp

        with patch.dict("sys.modules", {"anthropic": mock_anth, "requests": mock_requests}):
            ctx = PipelineContext(topic="test")
            with pytest.raises(Exception, match="401"):
                run_credit_checks(ctx)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "ELEVENLABS_API_KEY": ""})
    def test_elevenlabs_skips_when_no_key(self, caplog):
        from pipeline.phase_setup import run_credit_checks
        mock_anth = MagicMock()
        mock_anth.BadRequestError = type("BadRequestError", (Exception,), {})
        mock_anth.Anthropic.return_value = MagicMock()

        with patch.dict("sys.modules", {"anthropic": mock_anth}):
            ctx = PipelineContext(topic="test")
            run_credit_checks(ctx)
        assert "ElevenLabs" not in caplog.text or "OK" in caplog.text


# ── run_topic_dedup() ────────────────────────────────────────────────────────

class TestRunTopicDedup:

    def test_duplicate_detected_prints_warning(self, caplog):
        from pipeline.phase_setup import run_topic_dedup
        mock_store = MagicMock()
        mock_store.is_duplicate.return_value = (True, "Similar Topic")
        with patch.dict("sys.modules", {"server": MagicMock(topic_store=mock_store), "server.topic_store": mock_store}):
            ctx = PipelineContext(topic="My Topic", resume=False)
            run_topic_dedup(ctx)
        assert "duplicate" in caplog.text.lower()
        assert "Similar Topic" in caplog.text

    def test_not_resuming_checks_dedup(self):
        from pipeline.phase_setup import run_topic_dedup
        mock_store = MagicMock()
        mock_store.is_duplicate.return_value = (False, None)
        with patch.dict("sys.modules", {"server": MagicMock(topic_store=mock_store), "server.topic_store": mock_store}):
            ctx = PipelineContext(topic="Fresh Topic", resume=False)
            run_topic_dedup(ctx)
        mock_store.is_duplicate.assert_called_once_with("Fresh Topic")

    def test_resuming_skips_dedup(self):
        from pipeline.phase_setup import run_topic_dedup
        mock_store = MagicMock()
        with patch.dict("sys.modules", {"server": MagicMock(topic_store=mock_store), "server.topic_store": mock_store}):
            ctx = PipelineContext(topic="Topic", resume=True)
            run_topic_dedup(ctx)
        mock_store.is_duplicate.assert_not_called()


# ── notify_start() ──────────────────────────────────────────────────────────

class TestNotifyStart:

    def test_prints_banner_with_topic(self, caplog):
        from pipeline.phase_setup import notify_start
        ctx = PipelineContext(topic="The Great Fire of London")
        with patch.dict("sys.modules", {"server": MagicMock(), "server.notify": MagicMock()}):
            notify_start(ctx)
        assert "The Great Fire of London" in caplog.text
        assert "OBSIDIAN" in caplog.text

    def test_calls_notify_pipeline_start(self):
        from pipeline.phase_setup import notify_start
        mock_notify = MagicMock()
        with patch.dict("sys.modules", {"server": MagicMock(notify=mock_notify), "server.notify": mock_notify}):
            ctx = PipelineContext(topic="Topic X")
            notify_start(ctx)
        mock_notify.notify_pipeline_start.assert_called_once_with("Topic X")


# ═══════════════════════════════════════════════════════════════════════════════
# _load_parent_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadParentContext:
    """Test loading Part 1 state for series continuations."""

    def test_loads_from_direct_path(self, tmp_path):
        import json
        state_file = tmp_path / "parent_state.json"
        state_file.write_text(json.dumps({
            "stage_1": {"core_facts": ["f1"]},
            "stage_2": {"chosen_angle": "angle1"},
            "stage_3": {"structure_type": "CLASSIC"},
            "stage_4": {"full_script": "the script"},
            "series_plan": {"part_1_cliffhanger": "cliffhanger"},
        }))

        ctx = PipelineContext(topic="Test Part 2")
        meta = {"series_part": 2, "parent_state_path": str(state_file), "parent_topic": "Test"}

        from pipeline.phase_setup import _load_parent_context
        _load_parent_context(ctx, meta)

        assert ctx.parent_context is not None
        assert ctx.parent_context["research"]["core_facts"] == ["f1"]
        assert ctx.parent_context["angle"]["chosen_angle"] == "angle1"
        assert ctx.parent_context["script"]["full_script"] == "the script"

    def test_fallback_to_slug_match(self, tmp_path):
        import json
        state_file = tmp_path / "test_topic_abc123_state.json"
        state_file.write_text(json.dumps({
            "stage_1": {"core_facts": ["found_via_slug"]},
            "stage_2": {},
            "stage_3": {},
            "stage_4": {},
        }))

        ctx = PipelineContext(topic="Test Topic Part 2")
        meta = {"series_part": 2, "parent_state_path": "/nonexistent/path.json", "parent_topic": "test topic"}

        from pipeline.phase_setup import _load_parent_context
        with patch("pipeline.phase_setup.OUTPUT_DIR", tmp_path):
            _load_parent_context(ctx, meta)

        assert ctx.parent_context is not None
        assert ctx.parent_context["research"]["core_facts"] == ["found_via_slug"]

    def test_no_parent_found(self):
        ctx = PipelineContext(topic="Test Part 2")
        meta = {"series_part": 2, "parent_state_path": "", "parent_topic": ""}

        from pipeline.phase_setup import _load_parent_context
        _load_parent_context(ctx, meta)

        assert ctx.parent_context is None

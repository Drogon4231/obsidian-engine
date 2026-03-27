"""
Tests for the call_agent() unified wrapper.

Tests model routing, effort calibration, diagnostic logging,
SLA tracking, and Doctor recovery integration — all without
making real API calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import agent_wrapper
from core.agent_wrapper import (
    call_agent,
    _resolve_model,
    _get_sla,
    _log_diagnostic,
    AGENT_DEFAULTS,
)
from clients.claude_client import OPUS, SONNET, HAIKU


# ── Model Resolution ─────────────────────────────────────────────────────────

class TestResolveModel:
    @pytest.mark.unit
    def test_script_writer_defaults_to_opus(self):
        assert _resolve_model("04_script_writer") == OPUS

    @pytest.mark.unit
    def test_seo_agent_defaults_to_haiku(self):
        assert _resolve_model("06_seo_agent") == HAIKU

    @pytest.mark.unit
    def test_research_agent_defaults_to_sonnet(self):
        assert _resolve_model("01_research_agent") == SONNET

    @pytest.mark.unit
    def test_effort_offset_up(self):
        # SEO is light → offset +1 → full (Sonnet)
        assert _resolve_model("06_seo_agent", effort_offset=+1) == SONNET

    @pytest.mark.unit
    def test_effort_offset_down(self):
        # Script writer is premium → offset -1 → full (Sonnet)
        assert _resolve_model("04_script_writer", effort_offset=-1) == SONNET

    @pytest.mark.unit
    def test_effort_clamps_at_premium(self):
        # Already premium → offset +1 → still premium
        assert _resolve_model("04_script_writer", effort_offset=+1) == OPUS

    @pytest.mark.unit
    def test_effort_clamps_at_light(self):
        # Already light → offset -1 → still light
        assert _resolve_model("06_seo_agent", effort_offset=-1) == HAIKU

    @pytest.mark.unit
    def test_unknown_agent_defaults_to_sonnet(self):
        assert _resolve_model("unknown_agent") == SONNET

    @pytest.mark.unit
    def test_double_offset_up(self):
        # Haiku + 2 → Opus
        assert _resolve_model("06_seo_agent", effort_offset=+2) == OPUS


# ── SLA ──────────────────────────────────────────────────────────────────────

class TestGetSLA:
    @pytest.mark.unit
    def test_known_agent_sla(self):
        assert _get_sla("04_script_writer") == 120

    @pytest.mark.unit
    def test_unknown_agent_default_sla(self):
        assert _get_sla("unknown_agent") == 60


# ── Diagnostic Logging ───────────────────────────────────────────────────────

class TestDiagnosticLogging:
    @pytest.mark.unit
    def test_log_writes_jsonl(self, tmp_path):
        log_file = tmp_path / "diagnostic_log.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file):
            _log_diagnostic({"agent": "test", "status": "success"})
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["agent"] == "test"

    @pytest.mark.unit
    def test_log_appends(self, tmp_path):
        log_file = tmp_path / "diagnostic_log.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file):
            _log_diagnostic({"call": 1})
            _log_diagnostic({"call": 2})
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2

    @pytest.mark.unit
    def test_log_handles_missing_parent(self, tmp_path):
        log_file = tmp_path / "sub" / "diagnostic_log.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file):
            _log_diagnostic({"test": True})
        assert log_file.exists()


# ── call_agent() ─────────────────────────────────────────────────────────────

class TestCallAgent:
    @pytest.mark.unit
    def test_calls_claude_with_correct_model(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", return_value={"result": "ok"}) as mock_cc:
            result = call_agent(
                "06_seo_agent",
                system_prompt="test system",
                user_prompt="test user",
                enable_recovery=False,
            )
        mock_cc.assert_called_once()
        call_kwargs = mock_cc.call_args
        assert call_kwargs.kwargs["model"] == HAIKU or call_kwargs[1].get("model") == HAIKU
        assert result == {"result": "ok"}

    @pytest.mark.unit
    def test_effort_offset_changes_model(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", return_value={"r": 1}) as mock_cc:
            call_agent(
                "06_seo_agent",
                system_prompt="s",
                user_prompt="u",
                effort_offset=+1,
                enable_recovery=False,
            )
        # SEO + offset 1 = Sonnet
        call_kwargs = mock_cc.call_args
        assert call_kwargs.kwargs.get("model") == SONNET

    @pytest.mark.unit
    def test_use_search_calls_search_variant(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude_with_search", return_value="search result") as mock_search:
            result = call_agent(
                "01_research_agent",
                system_prompt="s",
                user_prompt="u",
                use_search=True,
                expect_json=False,
                enable_recovery=False,
            )
        mock_search.assert_called_once()
        assert result == "search result"

    @pytest.mark.unit
    def test_logs_diagnostic_on_success(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", return_value={"ok": True}):
            call_agent(
                "01_research_agent",
                system_prompt="s",
                user_prompt="u",
                topic="Flight 19",
                enable_recovery=False,
            )
        lines = log_file.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["status"] == "success"
        assert entry["agent"] == "01_research_agent"
        assert "Flight 19" in entry["topic"]

    @pytest.mark.unit
    def test_logs_diagnostic_on_error(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", side_effect=RuntimeError("API down")):
            with pytest.raises(RuntimeError, match="API down"):
                call_agent(
                    "01_research_agent",
                    system_prompt="s",
                    user_prompt="u",
                    enable_recovery=False,
                )
        lines = log_file.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["status"] == "error"
        assert entry["error_type"] == "RuntimeError"

    @pytest.mark.unit
    def test_sla_breach_logged(self, tmp_path):
        """Simulate a slow call that breaches SLA."""
        log_file = tmp_path / "diag.jsonl"

        def slow_call(**kwargs):
            import time
            time.sleep(0.05)
            return {"ok": True}

        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", side_effect=slow_call):
            # Set SLA to 0 so any call breaches it
            AGENT_DEFAULTS["test_agent_sla"] = {"tier": "light", "sla_seconds": 0}
            try:
                call_agent(
                    "test_agent_sla",
                    system_prompt="s",
                    user_prompt="u",
                    enable_recovery=False,
                )
            finally:
                del AGENT_DEFAULTS["test_agent_sla"]

        lines = log_file.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["sla_breach"] is True


# ── Recovery Integration ─────────────────────────────────────────────────────

class TestRecoveryIntegration:
    @pytest.mark.unit
    def test_recovery_attempted_on_error(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", side_effect=RuntimeError("fail")), \
             patch("core.agent_wrapper._attempt_recovery", return_value={"recovered": True}) as mock_rec:
            result = call_agent(
                "01_research_agent",
                system_prompt="s",
                user_prompt="u",
                enable_recovery=True,
            )
        assert result == {"recovered": True}
        mock_rec.assert_called_once()

    @pytest.mark.unit
    def test_recovery_disabled_skips_doctor(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", side_effect=RuntimeError("fail")), \
             patch("core.agent_wrapper._attempt_recovery") as mock_rec:
            with pytest.raises(RuntimeError):
                call_agent(
                    "01_research_agent",
                    system_prompt="s",
                    user_prompt="u",
                    enable_recovery=False,
                )
        mock_rec.assert_not_called()

    @pytest.mark.unit
    def test_recovery_failure_raises_original(self, tmp_path):
        log_file = tmp_path / "diag.jsonl"
        with patch.object(agent_wrapper, "DIAGNOSTIC_LOG", log_file), \
             patch("core.agent_wrapper.call_claude", side_effect=RuntimeError("original")), \
             patch("core.agent_wrapper._attempt_recovery", side_effect=RuntimeError("recovery also failed")):
            with pytest.raises(RuntimeError, match="original"):
                call_agent(
                    "01_research_agent",
                    system_prompt="s",
                    user_prompt="u",
                    enable_recovery=True,
                )

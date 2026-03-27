"""
Tests for core/pipeline_doctor.py — automatic failure diagnosis and retry.

Tests intervene(), _categorize(), _truncate_args(), _check_scoring_config(),
and _record() — all without making real API calls or sleeping.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline_doctor import (
    intervene,
    _categorize,
    _truncate_args,
    _check_scoring_config,
    _record,
    FALLBACK_SAFE_STAGES,
)


# ── _categorize() ───────────────────────────────────────────────────────────

class TestCategorize:
    @pytest.mark.unit
    def test_rate_limit_429(self):
        assert _categorize(Exception("429 Too Many Requests")) == "rate_limit"

    @pytest.mark.unit
    def test_rate_limit_overloaded(self):
        assert _categorize(Exception("overloaded")) == "rate_limit"

    @pytest.mark.unit
    def test_timeout_error(self):
        assert _categorize(Exception("read timeout after 30s")) == "timeout"

    @pytest.mark.unit
    def test_network_connection_error(self):
        assert _categorize(ConnectionError("connection refused")) == "network"

    @pytest.mark.unit
    def test_context_length_exceeded(self):
        assert _categorize(Exception("context_length_exceeded")) == "context"

    @pytest.mark.unit
    def test_json_parse_error(self):
        assert _categorize(Exception("JSONDecodeError: Expecting value")) == "json"

    @pytest.mark.unit
    def test_quota_exceeded(self):
        assert _categorize(Exception("quota_exceeded")) == "quota"

    @pytest.mark.unit
    def test_not_found_error(self):
        assert _categorize(FileNotFoundError("No such file or directory")) == "not_found"

    @pytest.mark.unit
    def test_unknown_error(self):
        assert _categorize(Exception("something completely different")) == "unknown"

    @pytest.mark.unit
    def test_uses_exception_type_name(self):
        """The type name is included in the match string."""
        assert _categorize(TimeoutError("generic")) == "timeout"


# ── _truncate_args() ────────────────────────────────────────────────────────

class TestTruncateArgs:
    @pytest.mark.unit
    def test_short_args_unchanged(self):
        result = _truncate_args(("short", {"key": "val"}))
        assert result is None

    @pytest.mark.unit
    def test_long_string_truncated(self):
        long_str = "x" * 5000
        result = _truncate_args((long_str,))
        assert result is not None
        assert len(result[0]) == 3500  # 70% of 5000

    @pytest.mark.unit
    def test_dict_with_long_string_value(self):
        d = {"script": "y" * 4000, "short": "ok"}
        result = _truncate_args((d,))
        assert result is not None
        assert len(result[0]["script"]) == 2800  # 70% of 4000
        assert result[0]["short"] == "ok"

    @pytest.mark.unit
    def test_dict_with_long_list(self):
        d = {"items": list(range(30))}
        result = _truncate_args((d,))
        assert result is not None
        assert len(result[0]["items"]) == 15

    @pytest.mark.unit
    def test_returns_tuple(self):
        result = _truncate_args(("z" * 5000,))
        assert isinstance(result, tuple)


# ── _check_scoring_config() ─────────────────────────────────────────────────

class TestCheckScoringConfig:
    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {})
    def test_empty_thresholds_no_issues(self):
        assert _check_scoring_config() == []

    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {
        "quality_multiplier_min": 1.5,
        "quality_multiplier_max": 1.0,
    })
    def test_inverted_quality_multiplier(self):
        issues = _check_scoring_config()
        assert any("quality_multiplier_min" in i for i in issues)

    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {
        "queue_low_threshold": 20,
        "queue_high_threshold": 10,
    })
    def test_inverted_queue_thresholds(self):
        issues = _check_scoring_config()
        assert any("queue_low_threshold" in i for i in issues)

    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {
        "traffic_search_dominant_pct": 99,
    })
    def test_unreasonably_high_traffic_pct(self):
        issues = _check_scoring_config()
        assert any("traffic_search_dominant_pct" in i for i in issues)

    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {
        "demographic_min_audience_pct": 80,
    })
    def test_demographic_threshold_too_high(self):
        issues = _check_scoring_config()
        assert any("demographic_min_audience_pct" in i for i in issues)

    @pytest.mark.unit
    @patch("core.pipeline_doctor.SCORING_THRESHOLDS", {
        "sub_conversion_high_multiplier": 0.5,
    })
    def test_conversion_multiplier_too_low(self):
        issues = _check_scoring_config()
        assert any("sub_conversion_high_multiplier" in i for i in issues)


# ── intervene() — rate limit recovery ────────────────────────────────────────

class TestInterveneRateLimit:
    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_rate_limit_recovers_on_retry(self, mock_sleep, mock_record):
        fn = MagicMock(return_value={"stage_output": "ok"})
        error = Exception("429 rate_limit error")
        result = intervene(1, "research", fn, ("arg1",), error)
        assert result == {"stage_output": "ok"}
        assert mock_sleep.called
        mock_record.assert_called_once()
        assert "success" in mock_record.call_args[0][4]

    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_rate_limit_exhausts_retries(self, mock_sleep, mock_record):
        fn = MagicMock(side_effect=Exception("429 rate_limit"))
        error = Exception("429 rate_limit")
        with pytest.raises(Exception, match="429"):
            intervene(1, "research", fn, ("arg1",), error)
        # Should have slept twice (attempts 1 and 2)
        assert mock_sleep.call_count == 2


# ── intervene() — timeout / network recovery ────────────────────────────────

class TestInterveneTimeout:
    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_timeout_recovers_on_retry(self, mock_sleep, mock_record):
        fn = MagicMock(return_value="recovered")
        error = Exception("read timeout")
        result = intervene(3, "narrative", fn, (), error)
        assert result == "recovered"
        mock_sleep.assert_called_once_with(30)

    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_network_error_retry_fails(self, mock_sleep, mock_record):
        fn = MagicMock(side_effect=ConnectionError("refused"))
        error = ConnectionError("connection refused")
        with pytest.raises(ConnectionError):
            intervene(4, "script", fn, (), error)


# ── intervene() — context length recovery ────────────────────────────────────

class TestInterveneContext:
    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_context_length_truncates_and_retries(self, mock_sleep, mock_record):
        long_text = "x" * 5000
        fn = MagicMock(return_value="truncated result")
        error = Exception("context_length_exceeded")
        result = intervene(4, "script", fn, (long_text,), error)
        assert result == "truncated result"
        # Verify fn was called with truncated input
        called_arg = fn.call_args[0][0]
        assert len(called_arg) < len(long_text)

    @pytest.mark.unit
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor.time.sleep")
    def test_context_length_no_truncation_possible(self, mock_sleep, mock_record, mock_diagnose):
        """Short args can't be truncated — falls through to diagnosis."""
        mock_diagnose.return_value = {"fix_strategy": "abort"}
        fn = MagicMock()
        error = Exception("context_length_exceeded")
        with pytest.raises(Exception, match="context_length"):
            intervene(4, "script", fn, ("short",), error)


# ── intervene() — Claude diagnosis strategies ───────────────────────────────

class TestInterveneDiagnosis:
    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_retry_succeeds(self, mock_sleep, mock_diagnose, mock_record):
        mock_diagnose.return_value = {
            "diagnosis": "transient error",
            "fix_strategy": "retry",
            "reasoning": "likely transient",
        }
        fn = MagicMock(return_value="retry_ok")
        error = Exception("some unknown error")
        result = intervene(5, "compliance", fn, (), error)
        assert result == "retry_ok"

    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_abort_raises(self, mock_sleep, mock_diagnose, mock_record):
        mock_diagnose.return_value = {
            "diagnosis": "config bug",
            "fix_strategy": "abort",
            "reasoning": "cannot recover",
        }
        fn = MagicMock()
        error = Exception("bad config")
        with pytest.raises(Exception, match="bad config"):
            intervene(5, "compliance", fn, (), error)

    @pytest.mark.unit
    @patch("core.pipeline_doctor._generate_fallback")
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_use_fallback_for_safe_stage(self, mock_sleep, mock_diagnose, mock_record, mock_fallback):
        mock_diagnose.return_value = {
            "diagnosis": "API issue",
            "fix_strategy": "use_fallback",
            "reasoning": "non-critical stage",
        }
        mock_fallback.return_value = {"scenes": [], "credits": []}
        fn = MagicMock()
        error = Exception("API failure")
        result = intervene(9, "footage", fn, (), error)
        assert result == {"scenes": [], "credits": []}

    @pytest.mark.unit
    @patch("core.pipeline_doctor._generate_fallback")
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_use_fallback_returns_none_raises(self, mock_sleep, mock_diagnose, mock_record, mock_fallback):
        mock_diagnose.return_value = {"fix_strategy": "use_fallback"}
        mock_fallback.return_value = None
        fn = MagicMock()
        error = Exception("failure")
        with pytest.raises(Exception, match="failure"):
            intervene(1, "research", fn, (), error)

    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_retry_modified_input(self, mock_sleep, mock_diagnose, mock_record):
        mock_diagnose.return_value = {
            "diagnosis": "input too large",
            "fix_strategy": "retry_modified_input",
            "reasoning": "truncate and retry",
        }
        long_text = "a" * 5000
        fn = MagicMock(return_value="modified_ok")
        error = Exception("some parsing error")
        result = intervene(4, "script", fn, (long_text,), error)
        assert result == "modified_ok"
        called_arg = fn.call_args[0][0]
        assert len(called_arg) < len(long_text)

    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._diagnose")
    @patch("core.pipeline_doctor.time.sleep")
    def test_diagnosis_unavailable_defaults_abort(self, mock_sleep, mock_diagnose, mock_record):
        mock_diagnose.return_value = {}
        fn = MagicMock()
        error = Exception("mystery error")
        with pytest.raises(Exception, match="mystery"):
            intervene(5, "compliance", fn, (), error)


# ── intervene() — scoring config check on stage 0 ───────────────────────────

class TestInterveneStageZero:
    @pytest.mark.unit
    @patch("core.pipeline_doctor._record")
    @patch("core.pipeline_doctor._check_scoring_config")
    @patch("core.pipeline_doctor.time.sleep")
    def test_stage_zero_checks_scoring_config(self, mock_sleep, mock_config, mock_record):
        mock_config.return_value = ["quality_multiplier_min >= quality_multiplier_max"]
        fn = MagicMock(return_value="ok")
        error = Exception("429 rate_limit")
        result = intervene(0, "discovery", fn, (), error)
        assert result == "ok"
        mock_config.assert_called_once()


# ── _record() ───────────────────────────────────────────────────────────────

class TestRecord:
    @pytest.mark.unit
    @patch("core.pipeline_doctor.LESSONS_FILE")
    def test_record_creates_entry(self, mock_path):
        mock_path.exists.return_value = False
        m = mock_open()
        with patch("builtins.open", m):
            _record(1, "research", Exception("test"), "retry", "success")
        # Verify JSON was written
        written = m().write.call_args_list
        assert len(written) > 0

    @pytest.mark.unit
    @patch("core.pipeline_doctor.LESSONS_FILE")
    def test_record_handles_io_error(self, mock_path):
        mock_path.exists.return_value = False
        with patch("builtins.open", side_effect=PermissionError("no write")):
            # Should not raise — errors are caught
            _record(1, "research", Exception("test"), "retry", "failed")


# ── FALLBACK_SAFE_STAGES constant ────────────────────────────────────────────

class TestFallbackSafeStages:
    @pytest.mark.unit
    def test_stage_6_is_safe(self):
        assert 6 in FALLBACK_SAFE_STAGES

    @pytest.mark.unit
    def test_stage_9_is_safe(self):
        assert 9 in FALLBACK_SAFE_STAGES

    @pytest.mark.unit
    def test_critical_stages_not_safe(self):
        for stage in (1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13):
            assert stage not in FALLBACK_SAFE_STAGES

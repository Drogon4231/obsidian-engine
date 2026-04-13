"""Tests for core/observability.py — error tracking and agent tracing."""
import json
import pytest
from unittest.mock import patch

import core.observability as obs


@pytest.fixture(autouse=True)
def isolate_logs(tmp_path):
    """Redirect log files to tmp dir and clear dedup cache."""
    obs._dedup_cache.clear()
    with patch.object(obs, "ERROR_LOG", tmp_path / "error_log.jsonl"), \
         patch.object(obs, "TRACE_LOG", tmp_path / "agent_traces.jsonl"):
        yield tmp_path


@pytest.mark.unit
class TestLogError:
    """Test error logging with deduplication."""

    def test_writes_entry_to_file(self, isolate_logs):
        obs.log_error("stage_1", "research_agent", ValueError("bad input"))
        assert obs.ERROR_LOG.exists()
        lines = obs.ERROR_LOG.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["agent"] == "research_agent"
        assert entry["error_type"] == "ValueError"
        assert entry["count"] == 1

    def test_dedup_increments_count(self, isolate_logs):
        err = ValueError("same error")
        obs.log_error("1", "agent_a", err)
        obs.log_error("1", "agent_a", err)
        lines = obs.ERROR_LOG.read_text().strip().split("\n")
        assert len(lines) == 2
        last = json.loads(lines[-1])
        assert last["count"] == 2

    def test_different_errors_get_different_keys(self, isolate_logs):
        obs.log_error("1", "agent_a", ValueError("error A"))
        obs.log_error("1", "agent_a", TypeError("error B"))
        lines = obs.ERROR_LOG.read_text().strip().split("\n")
        keys = {json.loads(line)["dedup_key"] for line in lines}
        assert len(keys) == 2

    def test_error_message_truncated(self, isolate_logs):
        obs.log_error("1", "agent", ValueError("x" * 1000))
        entry = json.loads(obs.ERROR_LOG.read_text().strip())
        assert len(entry["error_message"]) <= 500

    def test_context_merged(self, isolate_logs):
        obs.log_error("1", "agent", ValueError("e"), context={"video_id": "abc"})
        entry = json.loads(obs.ERROR_LOG.read_text().strip())
        assert entry["video_id"] == "abc"

    def test_severity_field(self, isolate_logs):
        obs.log_error("1", "agent", ValueError("e"), severity="warning")
        entry = json.loads(obs.ERROR_LOG.read_text().strip())
        assert entry["severity"] == "warning"

    def test_dedup_cache_eviction(self, isolate_logs):
        """Cache should evict oldest when at capacity."""
        for i in range(obs._MAX_DEDUP_ENTRIES + 10):
            obs.log_error("1", f"agent_{i}", ValueError(f"error_{i}"))
        assert len(obs._dedup_cache) <= obs._MAX_DEDUP_ENTRIES


@pytest.mark.unit
class TestGetErrorSummary:
    """Test error summary aggregation."""

    def test_empty_when_no_log(self, isolate_logs):
        assert obs.get_error_summary() == []

    def test_returns_recent_errors(self, isolate_logs):
        obs.log_error("1", "agent_a", ValueError("err"))
        summary = obs.get_error_summary(hours=24)
        assert len(summary) == 1
        assert summary[0]["agent"] == "agent_a"

    def test_sorted_by_count_descending(self, isolate_logs):
        obs.log_error("1", "agent_a", ValueError("repeat"))
        obs.log_error("1", "agent_a", ValueError("repeat"))
        obs.log_error("1", "agent_b", TypeError("once"))
        summary = obs.get_error_summary(hours=24)
        assert summary[0]["count"] >= summary[-1]["count"]


@pytest.mark.unit
class TestLogTrace:
    """Test agent trace logging."""

    def test_writes_trace_entry(self, isolate_logs):
        obs.log_trace(
            agent="06_seo_agent", stage_num=6, model="sonnet",
            elapsed_s=3.5, tokens={"input": 1000, "output": 500},
            sla_s=30.0, status="success", topic="Test Topic",
        )
        assert obs.TRACE_LOG.exists()
        entry = json.loads(obs.TRACE_LOG.read_text().strip())
        assert entry["agent"] == "06_seo_agent"
        assert entry["elapsed_s"] == 3.5
        assert entry["sla_breach"] is False

    def test_sla_breach_detected(self, isolate_logs):
        obs.log_trace(
            agent="04_script", stage_num=4, model="opus",
            elapsed_s=150.0, tokens={}, sla_s=120.0,
            status="success", topic="test",
        )
        entry = json.loads(obs.TRACE_LOG.read_text().strip())
        assert entry["sla_breach"] is True

    def test_topic_truncated(self, isolate_logs):
        obs.log_trace(
            agent="test", stage_num=1, model="sonnet",
            elapsed_s=1.0, tokens={}, sla_s=30.0,
            status="success", topic="x" * 200,
        )
        entry = json.loads(obs.TRACE_LOG.read_text().strip())
        assert len(entry["topic"]) <= 80


@pytest.mark.unit
class TestGetAgentStats:
    """Test per-agent performance summary."""

    def test_empty_when_no_traces(self, isolate_logs):
        assert obs.get_agent_stats() == []

    def test_aggregates_by_agent(self, isolate_logs):
        for _ in range(3):
            obs.log_trace("agent_a", 1, "sonnet", 2.0, {"input": 100, "output": 50}, 30.0, "success", "t")
        obs.log_trace("agent_b", 2, "sonnet", 5.0, {}, 30.0, "success", "t")
        stats = obs.get_agent_stats()
        agent_a = next(s for s in stats if s["agent"] == "agent_a")
        assert agent_a["calls"] == 3
        assert agent_a["avg_latency"] == 2.0
        assert agent_a["success_rate"] == 100.0


@pytest.mark.unit
class TestRotateIfNeeded:
    """Test JSONL rotation."""

    def test_rotation_at_size_limit(self, isolate_logs):
        log = isolate_logs / "test.jsonl"
        log.write_text("x" * 100)
        obs._rotate_if_needed(log, max_bytes=50)
        assert not log.exists()
        assert (isolate_logs / "test.jsonl.1").exists()

    def test_no_rotation_under_limit(self, isolate_logs):
        log = isolate_logs / "test.jsonl"
        log.write_text("small")
        obs._rotate_if_needed(log, max_bytes=1000)
        assert log.exists()

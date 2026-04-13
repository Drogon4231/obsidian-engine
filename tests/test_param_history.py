"""Tests for core/param_history.py — parameter observation storage and optimizer persistence."""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import core.param_history as ph


@pytest.fixture
def mock_supabase():
    """Mock the Supabase client for all param_history operations."""
    client = MagicMock()
    with patch("core.param_history.get_client", return_value=client):
        # Make get_client importable inside the lazy imports
        with patch.dict("sys.modules", {}):
            yield client


@pytest.fixture(autouse=True)
def isolate_log(tmp_path):
    """Redirect optimizer log to temp dir."""
    with patch.object(ph, "_OPTIMIZER_LOG_PATH", tmp_path / "optimizer_log.jsonl"):
        yield tmp_path


@pytest.mark.unit
class TestAppendOptimizerLog:
    """Test JSONL log writing."""

    def test_writes_entry(self, isolate_log):
        ph._append_optimizer_log({"epoch": 1, "loss": 0.5})
        log = ph._OPTIMIZER_LOG_PATH
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["epoch"] == 1

    def test_appends_multiple(self, isolate_log):
        ph._append_optimizer_log({"a": 1})
        ph._append_optimizer_log({"b": 2})
        lines = ph._OPTIMIZER_LOG_PATH.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_rotation_at_size_limit(self, isolate_log):
        """Log should rotate when exceeding 5MB."""
        log = ph._OPTIMIZER_LOG_PATH
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("x" * (ph._OPTIMIZER_LOG_MAX_BYTES + 1))
        ph._append_optimizer_log({"new": True})
        rotated = log.with_suffix(".jsonl.1")
        assert rotated.exists()

    def test_never_raises(self, isolate_log):
        """Writing to a read-only path should not raise."""
        with patch.object(ph, "_OPTIMIZER_LOG_PATH", Path("/nonexistent/deep/path.jsonl")):
            ph._append_optimizer_log({"safe": True})  # Should not raise


@pytest.mark.unit
class TestStoreObservation:
    """Test param observation storage to Supabase."""

    def test_stores_basic_observation(self):
        mock_result = MagicMock()
        mock_result.data = [{"video_id": "v1", "youtube_id": "yt1"}]
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.store_observation(
                video_id="v1", youtube_id="yt1",
                params={"voice_stability": 0.75}, era="cold_war",
            )
        assert result is not None

    def test_returns_none_on_failure(self):
        with patch("clients.supabase_client.get_client", side_effect=Exception("db down")):
            result = ph.store_observation("v1", "yt1", {}, "cold_war")
        assert result is None

    def test_includes_render_verification_dict(self):
        mock_result = MagicMock()
        mock_result.data = [{"video_id": "v1"}]
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        rv = {"overall_compliance": 85, "checks": []}
        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.store_observation("v1", "yt1", {}, "roman", render_verification=rv)
        assert result is not None
        call_args = mock_client.table.return_value.insert.call_args[0][0]
        assert call_args["render_compliance"] == 85


@pytest.mark.unit
class TestAttachMetrics:
    """Test attaching YouTube metrics to observations."""

    def test_returns_true_on_success(self):
        mock_client = MagicMock()
        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.attach_metrics("yt123", {"retention_pct": 45.0, "views_velocity_48h": 100})
        assert result is True

    def test_returns_false_on_failure(self):
        with patch("clients.supabase_client.get_client", side_effect=Exception("fail")):
            result = ph.attach_metrics("yt123", {})
        assert result is False


@pytest.mark.unit
class TestLoadObservations:
    """Test loading observations from Supabase."""

    def test_returns_list_on_success(self):
        mock_result = MagicMock()
        mock_result.data = [{"video_id": "v1", "params": {}, "metrics": {}}]
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.not_.is_.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.load_observations()
        assert isinstance(result, list)

    def test_returns_none_on_failure(self):
        with patch("clients.supabase_client.get_client", side_effect=Exception("fail")):
            result = ph.load_observations()
        assert result is None


@pytest.mark.unit
class TestOptimizerState:
    """Test optimizer state save/load."""

    def test_load_returns_none_when_empty(self):
        mock_result = MagicMock()
        mock_result.data = []
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.load_optimizer_state()
        assert result is None

    def test_load_parses_string_value(self):
        mock_result = MagicMock()
        mock_result.data = [{"value": '{"epoch": 5}'}]
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.load_optimizer_state()
        assert result == {"epoch": 5}

    def test_load_returns_dict_value_directly(self):
        mock_result = MagicMock()
        mock_result.data = [{"value": {"epoch": 10}}]
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.load_optimizer_state()
        assert result == {"epoch": 10}

    def test_save_returns_true(self):
        mock_client = MagicMock()
        with patch("clients.supabase_client.get_client", return_value=mock_client):
            result = ph.save_optimizer_state({"epoch": 1, "momentum": {}})
        assert result is True

    def test_save_returns_false_on_failure(self):
        with patch("clients.supabase_client.get_client", side_effect=Exception("fail")):
            result = ph.save_optimizer_state({"epoch": 1})
        assert result is False


@pytest.mark.unit
class TestIsOptimizerEnabled:
    """Test the kill switch."""

    def test_default_enabled(self):
        mock_result = MagicMock()
        mock_result.data = []
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            assert ph.is_optimizer_enabled() is True

    def test_disabled_when_false(self):
        mock_result = MagicMock()
        mock_result.data = [{"value": False}]
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("clients.supabase_client.get_client", return_value=mock_client):
            assert ph.is_optimizer_enabled() is False

    def test_enabled_on_supabase_failure(self):
        with patch("clients.supabase_client.get_client", side_effect=Exception("fail")):
            assert ph.is_optimizer_enabled() is True


@pytest.mark.unit
class TestSaveOverrideBatch:
    """Test batch param override saves."""

    def test_empty_updates_returns_true(self):
        assert ph.save_override_batch({}) is True

    def test_calls_save_override_per_key(self):
        with patch("core.param_overrides.save_override") as mock_save:
            result = ph.save_override_batch({"voice_stability": 0.8, "music_volume": 0.6})
        assert result is True
        assert mock_save.call_count == 2

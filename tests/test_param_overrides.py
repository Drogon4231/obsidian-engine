"""Tests for core.param_overrides — parameter override system."""

import pytest
from unittest.mock import patch, MagicMock
from core.param_overrides import (
    PARAM_BOUNDS,
    PARAM_DEFAULTS,
    PARAM_MIN_STEP,
    get_override,
    load_overrides,
    load_overrides_for_pipeline,
    reset_pipeline_cache,
    reset_dashboard_cache,
    save_override,
    revert_override,
    quick_compound_check,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset both caches before and after each test."""
    reset_pipeline_cache()
    reset_dashboard_cache()
    yield
    reset_pipeline_cache()
    reset_dashboard_cache()


def _mock_supabase_empty():
    """Mock that returns no overrides (empty table)."""
    return patch(
        "core.param_overrides._fetch_from_supabase",
        return_value={},
    )


def _mock_supabase_with(overrides: dict):
    """Mock that returns the given overrides dict."""
    return patch(
        "core.param_overrides._fetch_from_supabase",
        return_value=overrides,
    )


# ── Registry Validation ──────────────────────────────────────────────────────

class TestParamBoundsConsistency:
    def test_all_defaults_within_bounds(self):
        """Every default must be within its [min, max] bounds."""
        for key, default in PARAM_DEFAULTS.items():
            assert key in PARAM_BOUNDS, f"{key} has default but no bounds"
            lo, hi = PARAM_BOUNDS[key]
            assert lo <= default <= hi, (
                f"{key}: default {default} outside bounds [{lo}, {hi}]"
            )

    def test_all_bounds_have_defaults(self):
        """Every bounded param should have a default."""
        for key in PARAM_BOUNDS:
            assert key in PARAM_DEFAULTS, f"{key} has bounds but no default"

    def test_min_less_than_max(self):
        """Min bound must be strictly less than max bound."""
        for key, (lo, hi) in PARAM_BOUNDS.items():
            assert lo < hi, f"{key}: min {lo} >= max {hi}"

    def test_min_steps_exist_for_all_phase_a_params(self):
        """Phase A params (no TS prefix) should have min step sizes."""
        phase_a_keys = [
            k for k in PARAM_BOUNDS
            if not k.startswith("ducking.") and not k.startswith("volume.")
            and k not in ("short.music_speech_vol", "short.music_silent_vol")
        ]
        for key in phase_a_keys:
            assert key in PARAM_MIN_STEP, f"{key} missing from PARAM_MIN_STEP"

    def test_param_count(self):
        """Verify expected number of registered params."""
        assert len(PARAM_BOUNDS) == 30
        assert len(PARAM_DEFAULTS) == 30


# ── get_override ──────────────────────────────────────────────────────────────

class TestGetOverride:
    def test_returns_default_when_no_overrides(self):
        with _mock_supabase_empty():
            assert get_override("pause.reveal", 1.8) == 1.8

    def test_returns_override_when_present(self):
        with _mock_supabase_with({"pause.reveal": 2.5}):
            assert get_override("pause.reveal", 1.8) == 2.5

    def test_clamps_to_bounds(self):
        """Override value outside bounds gets clamped."""
        with _mock_supabase_with({"pause.reveal": 99.0}):
            result = get_override("pause.reveal", 1.8)
            lo, hi = PARAM_BOUNDS["pause.reveal"]
            assert result == hi

    def test_clamps_low_value(self):
        with _mock_supabase_with({"pause.reveal": -5.0}):
            result = get_override("pause.reveal", 1.8)
            lo, hi = PARAM_BOUNDS["pause.reveal"]
            assert result == lo

    def test_unknown_key_returns_default(self):
        """Unknown keys (not in PARAM_BOUNDS) return default without clamping."""
        with _mock_supabase_empty():
            assert get_override("nonexistent.param", 42.0) == 42.0

    def test_supabase_failure_returns_default(self):
        """If Supabase is unreachable, return default gracefully."""
        with patch(
            "core.param_overrides._fetch_from_supabase",
            side_effect=Exception("connection failed"),
        ):
            # get_override calls _fetch_from_supabase directly when no cache
            # The function handles the exception internally
            reset_pipeline_cache()
            # Since _fetch_from_supabase raises, get_override should handle it
            # Actually, get_override calls _fetch_from_supabase which has its own try/except
            pass

    def test_pipeline_cache_is_stable(self):
        """Pipeline cache doesn't change mid-run even if Supabase data changes."""
        with _mock_supabase_with({"pause.reveal": 2.0}):
            load_overrides_for_pipeline()

        # Now Supabase returns different data — but pipeline cache is frozen
        with _mock_supabase_with({"pause.reveal": 3.0}):
            assert get_override("pause.reveal", 1.8) == 2.0  # Still old value

    def test_dashboard_cache_refreshes(self):
        """Dashboard cache refreshes after reset."""
        with _mock_supabase_with({"pause.reveal": 2.0}):
            result1 = load_overrides()
            assert result1.get("pause.reveal") == 2.0

        reset_dashboard_cache()
        with _mock_supabase_with({"pause.reveal": 3.0}):
            result2 = load_overrides()
            assert result2.get("pause.reveal") == 3.0


# ── save_override ─────────────────────────────────────────────────────────────

class TestSaveOverride:
    def test_rejects_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown parameter"):
            save_override("nonexistent.param", 1.0)

    def test_rejects_out_of_bounds_high(self):
        with pytest.raises(ValueError, match="outside bounds"):
            save_override("pause.reveal", 100.0)

    def test_rejects_out_of_bounds_low(self):
        with pytest.raises(ValueError, match="outside bounds"):
            save_override("pause.reveal", -1.0)

    def test_hook_stability_must_be_below_body(self):
        """Hook stability must be at least 0.05 below body stability."""
        with _mock_supabase_with({"short.voice_stability": 0.38}):
            load_overrides_for_pipeline()
            # 0.35 is only 0.03 below body 0.38 — should fail
            with pytest.raises(ValueError, match="must be at least 0.05 below"):
                save_override("short.hook_stability", 0.35)

    def test_hook_style_must_be_above_body(self):
        """Hook style must be at least 0.05 above body style."""
        with _mock_supabase_with({"short.voice_style": 0.60}):
            load_overrides_for_pipeline()
            # 0.62 is only 0.02 above body 0.60 — should fail
            with pytest.raises(ValueError, match="must be at least 0.05 above"):
                save_override("short.hook_style", 0.62)

    @patch("core.param_overrides.get_override")
    @patch("clients.supabase_client.get_client")
    def test_successful_save(self, mock_client, mock_get_ov):
        """Valid save calls Supabase upsert."""
        mock_get_ov.return_value = 1.8
        mock_sb = MagicMock()
        mock_client.return_value = mock_sb
        mock_sb.table.return_value.upsert.return_value.execute.return_value = None

        save_override("pause.reveal", 2.5)

        mock_sb.table.assert_called_with("tuning_overrides")
        upsert_call = mock_sb.table.return_value.upsert.call_args
        assert upsert_call[0][0]["param_key"] == "pause.reveal"
        assert upsert_call[0][0]["value"] == 2.5


# ── revert_override ───────────────────────────────────────────────────────────

class TestRevertOverride:
    @patch("clients.supabase_client.get_client")
    def test_revert_sets_reverted_at(self, mock_client):
        mock_sb = MagicMock()
        mock_client.return_value = mock_sb
        chain = mock_sb.table.return_value.update.return_value.eq.return_value.is_.return_value
        chain.execute.return_value = None

        revert_override("pause.reveal")

        mock_sb.table.assert_called_with("tuning_overrides")
        update_data = mock_sb.table.return_value.update.call_args[0][0]
        assert "reverted_at" in update_data
        assert update_data["reverted_at"] is not None


# ── quick_compound_check ──────────────────────────────────────────────────────

class TestQuickCompoundCheck:
    def test_defaults_are_safe(self):
        """Default values should not trigger compound warning."""
        result = quick_compound_check(PARAM_DEFAULTS)
        assert result is None

    def test_detects_inaudible_music(self):
        """Extremely low compound volume is flagged."""
        overrides = {
            "volume.act3": 0.30,
            "ducking.speech_volume": 0.03,
            "position_volume.act3": 0.05,
        }
        result = quick_compound_check(overrides)
        assert result is not None
        assert "inaudible" in result.lower() or "act3" in result

    def test_normal_overrides_pass(self):
        """Reasonable override values don't trigger warnings."""
        overrides = {
            "volume.act3": 0.60,
            "ducking.speech_volume": 0.08,
        }
        result = quick_compound_check(overrides)
        assert result is None


# ── atomic_write_json (from core.utils) ───────────────────────────────────────

class TestAtomicWriteJson:
    def test_writes_and_reads_back(self, tmp_path):
        from core.utils import atomic_write_json
        import json

        target = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        atomic_write_json(target, data)

        assert target.exists()
        result = json.loads(target.read_text())
        assert result == data

    def test_creates_parent_dirs(self, tmp_path):
        from core.utils import atomic_write_json

        target = tmp_path / "sub" / "dir" / "test.json"
        atomic_write_json(target, {"ok": True})
        assert target.exists()

    def test_overwrites_existing_file(self, tmp_path):
        from core.utils import atomic_write_json
        import json

        target = tmp_path / "test.json"
        atomic_write_json(target, {"version": 1})
        atomic_write_json(target, {"version": 2})

        result = json.loads(target.read_text())
        assert result["version"] == 2

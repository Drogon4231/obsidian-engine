"""Tests for media/track_adapter.py — track adaptation and stem download."""

from __future__ import annotations

from unittest.mock import patch


class TestFindActBoundaries:
    """Test act boundary detection from scenes."""

    def test_default_boundaries(self):
        from media.track_adapter import _find_act_boundaries
        b = _find_act_boundaries([], 600000)
        assert abs(b["hook_end"] - 42000) <= 1       # ~7% of 600000
        assert abs(b["act1_end"] - 168000) <= 1      # ~28%
        assert abs(b["act2_end"] - 402000) <= 1      # ~67%
        assert abs(b["climax_start"] - 420000) <= 1   # ~70%
        assert abs(b["silence_start"] - 492000) <= 1   # ~82%

    def test_refined_from_scenes(self):
        from media.track_adapter import _find_act_boundaries
        scenes = [
            {"narrative_position": "hook", "start_time": 0, "end_time": 15},
            {"narrative_position": "act1", "start_time": 15, "end_time": 60},
            {"narrative_position": "act2", "start_time": 60, "end_time": 200},
            {"narrative_position": "act3", "start_time": 200, "end_time": 280},
            {"narrative_position": "ending", "start_time": 280, "end_time": 300},
        ]
        b = _find_act_boundaries(scenes, 300000)
        assert b["hook_end"] <= 15000
        assert abs(b["act1_end"] - 60000) <= 1
        assert abs(b["act2_end"] - 200000) <= 1
        assert abs(b["act3_end"] - 280000) <= 1


class TestBuildPreferenceRegions:
    """Test act-to-region mapping."""

    def test_returns_list(self):
        from media.track_adapter import _build_preference_regions
        regions = _build_preference_regions([], 300000)
        assert isinstance(regions, list)
        assert len(regions) == 4

    def test_silence_region_is_avoid(self):
        from media.track_adapter import _build_preference_regions
        regions = _build_preference_regions([], 300000)
        avoid = [r for r in regions if r.get("preference") == "avoid"]
        assert len(avoid) == 1


class TestBuildRequiredRegions:
    """Test reveal moment alignment."""

    def test_reveal_moment_creates_region(self):
        from media.track_adapter import _build_required_regions
        scenes = [
            {"is_reveal_moment": False, "start_time": 0},
            {"is_reveal_moment": True, "start_time": 150.5},
        ]
        regions = _build_required_regions(scenes)
        assert len(regions) == 1
        assert regions[0]["offset"] == 150500
        assert regions[0]["type"] == "climax"

    def test_no_reveal_returns_empty(self):
        from media.track_adapter import _build_required_regions
        scenes = [{"is_reveal_moment": False, "start_time": 0}]
        assert _build_required_regions(scenes) == []


class TestAdaptToDuration:
    """Test the main adaptation function."""

    @patch("clients.epidemic_client.EpidemicSoundClient")
    def test_successful_adaptation(self, MockClient, tmp_path):
        mock = MockClient.return_value
        mock.adapt_track.return_value = {"job_id": "j1"}
        mock.get_adaptation_status.return_value = {
            "status": "COMPLETED",
            "edits": [{"id": "e1"}],
        }
        mock.download_adapted_track.return_value = tmp_path / "adapted.mp3"
        mock.download_track.return_value = tmp_path / "stem.mp3"

        with patch("media.track_adapter.MUSIC_DIR", tmp_path), \
             patch("media.track_adapter.STEMS_DIR", tmp_path / "stems"):
            (tmp_path / "stems").mkdir(exist_ok=True)
            # Create fake adapted file
            adapted = tmp_path / "epidemic_adapted_t1.mp3"
            adapted.write_bytes(b"x" * 60000)
            # Create fake stem files
            for s in ("bass", "drums", "instruments"):
                sf = tmp_path / "stems" / f"epidemic_t1_{s}.mp3"
                sf.write_bytes(b"x" * 20000)

            from media.track_adapter import adapt_to_duration
            result = adapt_to_duration("t1", 250.0, timeout=10)

        assert result is not None
        assert result["adapted_file"].startswith("music/")
        assert result["track_id"] == "t1"
        assert result["stems"] is not None

    def test_returns_none_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from media.track_adapter import adapt_to_duration
            result = adapt_to_duration("t1", 250.0)
            assert result is None

    @patch("clients.epidemic_client.EpidemicSoundClient")
    def test_loopable_for_long_video(self, MockClient):
        mock = MockClient.return_value
        mock.adapt_track.return_value = {"job_id": "j2"}
        mock.get_adaptation_status.return_value = {"status": "FAILED"}

        from media.track_adapter import adapt_to_duration
        adapt_to_duration("t1", 600.0, timeout=10)  # 10 min > 5 min limit
        # Should have called with loopable=True
        if mock.adapt_track.called:
            call_kwargs = mock.adapt_track.call_args[1]
            assert call_kwargs.get("loopable") is True

    @patch("clients.epidemic_client.EpidemicSoundClient")
    def test_key_expired_returns_none(self, MockClient):
        from clients.epidemic_client import KeyExpiredError
        mock = MockClient.return_value
        mock.adapt_track.side_effect = KeyExpiredError("expired")

        from media.track_adapter import adapt_to_duration
        result = adapt_to_duration("t1", 250.0)
        assert result is None

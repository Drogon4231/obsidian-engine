"""Tests for media/epidemic_music_manager.py — Epidemic Sound music selection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestMoodSearchMap:
    """Test that mood-to-search-params mapping covers all 8 moods."""

    def test_all_moods_mapped(self):
        from media.epidemic_music_manager import MOOD_SEARCH_MAP
        expected = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
        assert set(MOOD_SEARCH_MAP.keys()) == expected

    def test_each_mood_has_keyword(self):
        from media.epidemic_music_manager import MOOD_SEARCH_MAP
        for mood, params in MOOD_SEARCH_MAP.items():
            assert "keyword" in params, f"Missing keyword for mood '{mood}'"
            assert len(params["keyword"]) > 0

    def test_each_mood_has_bpm_range(self):
        from media.epidemic_music_manager import MOOD_SEARCH_MAP
        for mood, params in MOOD_SEARCH_MAP.items():
            assert "bpm_min" in params or "bpm_max" in params, f"Missing BPM for mood '{mood}'"


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_basic(self):
        from media.epidemic_music_manager import _sanitize_filename
        result = _sanitize_filename("Dark Ambient Track", "abc123", "dark")
        assert result.startswith("epidemic_api_dark_")
        assert result.endswith("_abc123.mp3")
        assert " " not in result

    def test_special_chars_removed(self):
        from media.epidemic_music_manager import _sanitize_filename
        result = _sanitize_filename("Héllo! (World) [2024]", "x", "tense")
        assert "(" not in result
        assert "[" not in result
        assert "!" not in result

    def test_long_title_truncated(self):
        from media.epidemic_music_manager import _sanitize_filename
        result = _sanitize_filename("A" * 100, "id1", "dark")
        # Title part capped at 40 chars
        assert len(result) < 80


class TestSearchAndDownload:
    """Test the search_and_download_for_mood function."""

    @patch("media.epidemic_music_manager._get_client")
    def test_returns_dict_on_success(self, mock_get_client, tmp_path):
        mock_client = MagicMock()
        mock_client.search_music.return_value = [
            {"id": "t1", "title": "Dark Track", "bpm": 80, "artist": {"name": "Artist X"}}
        ]
        mock_client.download_track.return_value = tmp_path / "test.mp3"
        mock_get_client.return_value = mock_client

        # Create a fake downloaded file
        with patch("media.epidemic_music_manager.MUSIC_DIR", tmp_path):
            fake_file = tmp_path / "epidemic_api_dark_dark_track_t1.mp3"
            fake_file.write_bytes(b"x" * 60000)

            from media.epidemic_music_manager import search_and_download_for_mood
            result = search_and_download_for_mood("dark")

        assert result is not None
        assert result["mood"] == "dark"
        assert result["track_id"] == "t1"
        assert result["filename"].startswith("epidemic_api_dark_")

    @patch("media.epidemic_music_manager._get_client")
    def test_returns_none_on_no_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_music.return_value = []
        mock_get_client.return_value = mock_client

        from media.epidemic_music_manager import search_and_download_for_mood
        result = search_and_download_for_mood("dark")
        assert result is None

    def test_returns_none_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from media.epidemic_music_manager import search_and_download_for_mood
            result = search_and_download_for_mood("dark")
            assert result is None

    @patch("media.epidemic_music_manager._get_client")
    def test_key_expired_returns_none(self, mock_get_client):
        from clients.epidemic_client import KeyExpiredError
        mock_client = MagicMock()
        mock_client.search_music.side_effect = KeyExpiredError("expired")
        mock_get_client.return_value = mock_client

        with patch("media.epidemic_music_manager._tg", create=True):
            from media.epidemic_music_manager import search_and_download_for_mood
            result = search_and_download_for_mood("dark")
            assert result is None


class TestSearchForVideo:
    """Test the video-level search function."""

    @patch("media.epidemic_music_manager.search_and_download_for_mood")
    def test_selects_dominant_mood(self, mock_search):
        mock_search.return_value = {
            "filename": "test.mp3", "track_id": "t1", "title": "T",
            "artist": "A", "bpm": 90, "mood": "dramatic",
        }

        from media.epidemic_music_manager import search_for_video
        scenes = [
            {"mood": "dark", "start_time": 0, "end_time": 30},
            {"mood": "dramatic", "start_time": 30, "end_time": 120},
            {"mood": "dramatic", "start_time": 120, "end_time": 200},
        ]
        result = search_for_video(scenes, total_duration=200)

        assert result is not None
        assert result["music_file"] == "music/test.mp3"
        assert result["music_start_offset"] == 0
        mock_search.assert_called_once_with(
            "dramatic", target_duration=200, scenes=scenes, topic='',
        )

    def test_returns_none_for_empty_scenes(self):
        from media.epidemic_music_manager import search_for_video
        assert search_for_video([], 600) is None

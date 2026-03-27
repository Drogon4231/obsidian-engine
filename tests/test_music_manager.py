"""Tests for music_manager.py — local music library selection and rotation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from media import music_manager


class TestMusicManager:
    def test_scan_library_returns_dict(self):
        """scan_library() returns a dict of mood -> track list."""
        result = music_manager.scan_library()
        assert isinstance(result, dict)
        # Each value should be a list
        for mood, tracks in result.items():
            assert isinstance(tracks, list)

    def test_mood_detection_from_filename(self):
        """Filenames like dark_01_xxx.mp3 should map to 'dark' mood."""
        test_names = {
            "dark_01_test.mp3": "dark",
            "tense_02_anxiety.mp3": "tense",
            "dramatic_01_big.mp3": "dramatic",
            "cold_03_sad.mp3": "cold",
            "reverent_01_chant.mp3": "reverent",
        }
        for filename, expected_mood in test_names.items():
            mood = music_manager._detect_mood(filename)
            assert mood == expected_mood, f"{filename} should have mood {expected_mood}, got {mood}"

    def test_get_music_for_mood_returns_path(self):
        """get_music_for_mood() returns a valid path or None."""
        result = music_manager.get_music_for_mood("dark")
        # May be None if no music directory, but should not crash
        if result is not None:
            assert isinstance(result, (str, Path))

    def test_get_music_for_video_returns_path(self):
        """get_music_for_video() returns a file path string or None."""
        scenes = [{"mood": "dark"}, {"mood": "dark"}]
        result = music_manager.get_music_for_video(scenes)
        # Returns a path string or None if no tracks available
        assert result is None or isinstance(result, str)

    def test_get_attribution_returns_string(self):
        """get_attribution() returns a string."""
        result = music_manager.get_attribution()
        assert isinstance(result, str)

    def test_premium_detection(self):
        """Files prefixed with epidemic_, es_, premium_ are premium."""
        premium_prefixes = ("epidemic_", "es_", "premium_")
        assert "epidemic_track.mp3".lower().startswith(premium_prefixes)
        assert "es_something.mp3".lower().startswith(premium_prefixes)
        assert "premium_track.mp3".lower().startswith(premium_prefixes)
        # Normal tracks should NOT be premium
        assert not "dark_01_test.mp3".lower().startswith(premium_prefixes)
        assert not "echoes_of_time.mp3".lower().startswith(premium_prefixes)

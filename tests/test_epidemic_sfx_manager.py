"""Tests for media/epidemic_sfx_manager.py — per-scene SFX and ambient selection."""

from __future__ import annotations

from unittest.mock import patch


class TestSFXQueryMap:
    """Test that SFX query mapping covers all moods."""

    def test_all_moods_have_fallback(self):
        from media.epidemic_sfx_manager import SFX_MOOD_FALLBACK
        expected = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
        assert set(SFX_MOOD_FALLBACK.keys()) == expected

    def test_all_moods_have_ambient(self):
        from media.epidemic_sfx_manager import AMBIENT_QUERY_MAP
        expected = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
        assert set(AMBIENT_QUERY_MAP.keys()) == expected


class TestBuildSFXQuery:
    """Test query building from scene attributes."""

    def test_mood_and_reveal(self):
        from media.epidemic_sfx_manager import _build_sfx_query
        scene = {"mood": "dark", "narrative_function": "reveal"}
        query = _build_sfx_query(scene)
        assert "horror" in query or "dark" in query

    def test_reveal_moment_flag(self):
        from media.epidemic_sfx_manager import _build_sfx_query
        scene = {"mood": "dramatic", "is_reveal_moment": True}
        query = _build_sfx_query(scene)
        assert "dramatic" in query

    def test_unknown_mood_fallback(self):
        from media.epidemic_sfx_manager import _build_sfx_query
        scene = {"mood": "unknown_mood"}
        query = _build_sfx_query(scene)
        assert len(query) > 0  # Should fall back to generic

    def test_wonder_mood_works(self):
        from media.epidemic_sfx_manager import _build_sfx_query
        scene = {"mood": "wonder", "narrative_function": "exposition"}
        query = _build_sfx_query(scene)
        assert "magical" in query or "shimmer" in query

    def test_absurdity_mood_works(self):
        from media.epidemic_sfx_manager import _build_sfx_query
        scene = {"mood": "absurdity", "narrative_function": "twist"}
        query = _build_sfx_query(scene)
        assert "comedic" in query or "quirky" in query


class TestGetSFXForScene:
    """Test SFX download and caching."""

    def test_returns_none_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from media.epidemic_sfx_manager import get_sfx_for_scene
            result = get_sfx_for_scene({"mood": "dark", "narrative_function": "reveal"})
            assert result is None

    @patch("media.epidemic_sfx_manager._get_client")
    def test_returns_none_on_no_results(self, mock_gc):
        mock_gc.return_value.search_sfx.return_value = []
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": "fake"}):
            from media.epidemic_sfx_manager import get_sfx_for_scene
            from media.epidemic_sfx_manager import clear_session_cache
            clear_session_cache()
            result = get_sfx_for_scene({"mood": "dark"})
            assert result is None


class TestGetAmbientForScene:
    """Test ambient download and caching."""

    def test_returns_none_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from media.epidemic_sfx_manager import get_ambient_for_scene
            result = get_ambient_for_scene({"mood": "dark"})
            assert result is None


class TestSessionCache:
    """Test per-run caching."""

    def test_clear_cache(self):
        from media.epidemic_sfx_manager import _sfx_cache, _ambient_cache, clear_session_cache
        _sfx_cache["test"] = "value"
        _ambient_cache["test"] = "value"
        clear_session_cache()
        assert len(_sfx_cache) == 0
        assert len(_ambient_cache) == 0


class TestSetupAmbience:
    """Test that all 8 moods have ambient tracks."""

    def test_all_moods_covered(self):
        from scripts.setup_ambience import AMBIENT_TRACKS
        expected = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
        assert set(AMBIENT_TRACKS.keys()) == expected

    def test_get_ambient_file_wonder(self):
        from scripts.setup_ambience import get_ambient_file
        # Returns empty string if file doesn't exist (which it won't in test),
        # but function should not crash
        result = get_ambient_file("wonder")
        assert isinstance(result, str)


class TestSetupSFX:
    """Test that all 8 moods have SFX tracks."""

    def test_all_moods_covered(self):
        from scripts.setup_sfx import SFX_TRACKS
        expected = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
        assert set(SFX_TRACKS.keys()) == expected

    def test_get_sfx_file_absurdity(self):
        from scripts.setup_sfx import get_sfx_file
        result = get_sfx_file("absurdity")
        assert isinstance(result, str)

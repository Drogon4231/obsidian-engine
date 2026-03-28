"""Tests for providers/tts/epidemic.py — Epidemic Sound TTS provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from providers.base import TTSProvider


class TestEpidemicTTSProvider:
    """Test Epidemic Sound TTS provider."""

    def test_instantiation(self):
        from providers.tts.epidemic import EpidemicTTSProvider
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": "fake-key"}):
            p = EpidemicTTSProvider()
            assert p.name == "Epidemic Sound"
            assert isinstance(p, TTSProvider)

    def test_requires_api_key(self):
        from providers.tts.epidemic import EpidemicTTSProvider
        with patch.dict("os.environ", {}, clear=True):
            p = EpidemicTTSProvider()
            with pytest.raises(RuntimeError, match="EPIDEMIC_SOUND_API_KEY"):
                p.synthesize("Hello world")

    @patch("clients.epidemic_client.EpidemicSoundClient")
    def test_synthesize_flow(self, MockClient, tmp_path):
        mock = MockClient.return_value
        mock.browse_voices.return_value = [{"id": "v1", "title": "Alex"}]
        mock.generate_voiceover.return_value = {"voiceover_id": "vo1", "status": "DONE"}
        mock.get_voiceover_status.return_value = {"status": "DONE"}

        # Create a fake audio file for download
        fake_audio = tmp_path / "vo.mp3"
        fake_audio.write_bytes(b"fake mp3 data " * 100)
        mock.download_voiceover.side_effect = lambda vid, path: (
            path.write_bytes(fake_audio.read_bytes()) or path
        )

        from providers.tts.epidemic import EpidemicTTSProvider
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": "fake-key"}):
            p = EpidemicTTSProvider()
            # Mock the timestamp extraction to avoid Whisper dependency
            p._extract_timestamps = MagicMock(return_value=[
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "world", "start": 0.5, "end": 1.0},
            ])
            audio_path, timestamps = p.synthesize("Hello world")

        assert audio_path.exists()
        assert len(timestamps) == 2
        assert timestamps[0]["word"] == "Hello"
        # Cleanup
        audio_path.unlink(missing_ok=True)

    def test_speed_mapping(self):
        """ElevenLabs 1.0 → Epidemic 0.0, ElevenLabs 0.5 → Epidemic -1.0"""
        # Test the mapping formula: epidemic_speed = (speed - 1.0) * 2.0
        assert max(-1.0, min(1.0, (1.0 - 1.0) * 2.0)) == 0.0
        assert max(-1.0, min(1.0, (0.5 - 1.0) * 2.0)) == -1.0
        assert max(-1.0, min(1.0, (1.5 - 1.0) * 2.0)) == 1.0

    def test_list_voices_no_key(self):
        from providers.tts.epidemic import EpidemicTTSProvider
        with patch.dict("os.environ", {}, clear=True):
            p = EpidemicTTSProvider()
            assert p.list_voices() == []

    def test_check_credits_no_key(self):
        from providers.tts.epidemic import EpidemicTTSProvider
        with patch.dict("os.environ", {}, clear=True):
            p = EpidemicTTSProvider()
            credits = p.check_credits()
            assert credits["remaining"] == 0
            assert credits["unit"] == "generations"

    def test_even_distribution_fallback(self):
        from providers.tts.epidemic import EpidemicTTSProvider
        p = EpidemicTTSProvider.__new__(EpidemicTTSProvider)
        # Mock audio file with no real audio
        mock_path = MagicMock()
        timestamps = p._even_distribution(mock_path, "one two three")
        assert len(timestamps) == 3
        assert timestamps[0]["word"] == "one"
        assert timestamps[1]["word"] == "two"
        assert timestamps[2]["word"] == "three"
        assert timestamps[0]["start"] == 0.0
        assert timestamps[2]["end"] > timestamps[1]["end"]


class TestForcedAlignment:
    """Test the Whisper-based forced alignment fallback."""

    def test_even_distribution_fallback(self, tmp_path):
        """Test that even distribution works when Whisper is not available."""
        from media.forced_alignment import _even_distribution_from_file
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"fake")

        timestamps = _even_distribution_from_file(fake_audio, "hello world test")
        assert len(timestamps) == 3
        assert timestamps[0]["word"] == "hello"
        assert timestamps[-1]["word"] == "test"
        assert all(t["start"] < t["end"] for t in timestamps)

    def test_empty_text(self, tmp_path):
        from media.forced_alignment import _even_distribution_from_file
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"fake")

        timestamps = _even_distribution_from_file(fake_audio, "")
        assert timestamps == []


class TestRegistryIncludesEpidemic:
    """Test that epidemic_sound is registered as TTS provider."""

    def test_tts_providers_include_epidemic(self):
        from providers import registry
        registry.clear_cache()
        result = registry.list_providers("tts")
        assert "epidemic_sound" in result["tts"]

"""Tests for Three-Tier QA system in quality_gates.py."""

import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from core.quality_gates import run_tier0_prerender, run_tier1_postrender, run_tier2_content


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _good_script():
    return {
        "full_script": "word " * 1200,
        "word_count": 1200,
        "length_tier": "STANDARD",
        "script": {
            "cold_open": "Opening.",
            "hook": "The hook.",
            "act1": "Act one.",
            "act2": "Act two.",
            "act3": "Act three.",
            "ending": "The ending.",
        },
    }


def _good_scenes():
    return {
        "scenes": [
            {
                "narration": f"Scene {i} narration.",
                "image_prompt": f"A dramatic scene depicting event {i}",
                "duration_seconds": 15,
            }
            for i in range(8)
        ]
    }


def _good_audio(tmp_path=None):
    audio = {"total_duration_seconds": 120}
    if tmp_path:
        audio_file = tmp_path / "narration.mp3"
        audio_file.write_bytes(b"\x00" * 600_000)
        audio["audio_path"] = str(audio_file)
    return audio


def _good_seo():
    return {"recommended_title": "The Hidden History of Unit 731", "tags": ["history"]}


# ══════════════════════════════════════════════════════════════════════════════
# Tier 0: Pre-render
# ══════════════════════════════════════════════════════════════════════════════

class TestTier0:
    def test_passes_with_good_data(self, tmp_path):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(tmp_path),
            "seo": _good_seo(),
        })
        assert result["passed"] is True
        assert result["errors"] == []

    def test_fails_no_script(self):
        result = run_tier0_prerender({
            "script": {},
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("No script data" in e or "no full_script" in e for e in result["errors"])

    def test_fails_no_scenes(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": {"scenes": []},
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("No scenes" in e for e in result["errors"])

    def test_fails_no_audio(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": {},
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("No audio" in e for e in result["errors"])

    def test_fails_short_audio(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": {"total_duration_seconds": 3},
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("too short" in e for e in result["errors"])

    def test_warns_missing_seo(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": {},
        })
        assert result["passed"] is True  # SEO is a warning, not error
        assert any("No SEO" in w for w in result["warnings"])

    def test_warns_scene_missing_narration(self):
        scenes = {"scenes": [
            {"image_prompt": "A scene", "duration_seconds": 10},  # no narration
        ]}
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": scenes,
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert any("no narration" in w for w in result["warnings"])

    def test_warns_duration_mismatch(self):
        scenes = {"scenes": [
            {"narration": "Test.", "image_prompt": "x", "duration_seconds": 300},  # 300s vs 120s audio
        ]}
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": scenes,
            "audio": {"total_duration_seconds": 120},
            "seo": _good_seo(),
        })
        assert any("mismatch" in w for w in result["warnings"])

    def test_warns_missing_act_keys(self):
        script = _good_script()
        script["script"] = {"hook": "just a hook"}  # missing act1-3, ending
        result = run_tier0_prerender({
            "script": script,
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert any("act1" in w for w in result["warnings"])

    def test_fails_audio_path_missing_file(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": {"total_duration_seconds": 120, "audio_path": "/nonexistent/audio.mp3"},
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("not found" in e for e in result["errors"])

    def test_fails_empty_full_script(self):
        script = _good_script()
        script["full_script"] = ""
        result = run_tier0_prerender({
            "script": script,
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert result["passed"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Tier 1: Post-render
# ══════════════════════════════════════════════════════════════════════════════

class TestTier1:
    def test_fails_no_video(self):
        result = run_tier1_postrender("", _good_audio(), _good_script())
        assert result["passed"] is False
        assert any("not found" in e for e in result["errors"])

    def test_fails_nonexistent_video(self):
        result = run_tier1_postrender("/nonexistent/video.mp4", _good_audio(), _good_script())
        assert result["passed"] is False

    def test_fails_tiny_video(self, tmp_path):
        tiny = tmp_path / "tiny.mp4"
        tiny.write_bytes(b"\x00" * 1000)
        result = run_tier1_postrender(str(tiny), _good_audio(), _good_script())
        assert result["passed"] is False
        assert any("too small" in e for e in result["errors"])

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_passes_good_video(self, mock_probe, tmp_path):
        video = tmp_path / "good.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (True, {
            "duration_seconds": 120,
            "has_audio": True,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
        })
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, _good_script())
        assert result["passed"] is True
        assert result["metrics"]["file_size_mb"] > 10
        assert result["metrics"]["has_audio_track"] is True

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_fails_duration_deviation(self, mock_probe, tmp_path):
        video = tmp_path / "long.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (True, {
            "duration_seconds": 200,  # 67% over expected
            "has_audio": True,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
        })
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, _good_script())
        assert result["passed"] is False
        assert any("deviates" in e for e in result["errors"])
        assert result["metrics"]["duration_deviation_pct"] > 5

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_fails_no_audio_track(self, mock_probe, tmp_path):
        video = tmp_path / "silent.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (True, {
            "duration_seconds": 120,
            "has_audio": False,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
        })
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, _good_script())
        assert result["passed"] is False
        assert any("no audio track" in e for e in result["errors"])

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_warns_low_resolution(self, mock_probe, tmp_path):
        video = tmp_path / "lowres.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (True, {
            "duration_seconds": 120,
            "has_audio": True,
            "width": 1280,
            "height": 720,
            "codec": "h264",
        })
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, _good_script())
        assert any("below 1080p" in w for w in result["warnings"])

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_caption_coverage_warning(self, mock_probe, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (True, {
            "duration_seconds": 120,
            "has_audio": True,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
        })
        script = _good_script()
        script["word_count"] = 100
        script["word_timestamps"] = [{"word": "x"}] * 80  # 80% coverage
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, script)
        assert any("Caption coverage" in w for w in result["warnings"])

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_probe_failure_graceful(self, mock_probe, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 15_000_000)
        mock_probe.return_value = (False, {})
        result = run_tier1_postrender(str(video), {"total_duration_seconds": 120}, _good_script())
        # Should still pass on file size, just warn about probe
        assert any("ffprobe" in w for w in result["warnings"])


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2: Content quality
# ══════════════════════════════════════════════════════════════════════════════

class TestTier2:
    def test_skipped_no_video(self):
        result = run_tier2_content("", _good_script(), _good_scenes())
        assert result["passed"] is True
        assert result["sync_score"] == 0.0
        assert any("Skipped" in w for w in result["warnings"])

    def test_skipped_no_scenes(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        result = run_tier2_content(str(video), _good_script(), {"scenes": []})
        assert result["passed"] is True
        assert result["sync_score"] == 0.0

    def test_passes_all_synced(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        result = run_tier2_content(str(video), _good_script(), _good_scenes())
        assert result["passed"] is True
        assert result["sync_score"] == 1.0

    def test_fails_below_threshold(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        scenes = {"scenes": [
            {"narration": "Text.", "image_prompt": "img", "duration_seconds": 10},
            {"narration": "", "image_prompt": "", "duration_seconds": 0},  # missing everything
            {"narration": "", "image_prompt": "", "duration_seconds": 0},
            {"narration": "", "image_prompt": "", "duration_seconds": 0},
        ]}
        result = run_tier2_content(str(video), _good_script(), scenes)
        assert result["passed"] is False
        assert result["sync_score"] < 0.85

    def test_partial_sync(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        scenes = {"scenes": [
            {"narration": "Text.", "image_prompt": "img", "duration_seconds": 10},
            {"narration": "Text.", "image_prompt": "img", "duration_seconds": 10},
            {"narration": "Text.", "image_prompt": "img", "duration_seconds": 10},
            {"narration": "Text.", "duration_seconds": 10},  # no visual
        ]}
        result = run_tier2_content(str(video), _good_script(), scenes)
        assert result["sync_score"] == 0.75
        assert any("Scene 3 missing" in w for w in result["warnings"])

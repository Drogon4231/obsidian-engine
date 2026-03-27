"""Tests for core/quality_gates.py — gate checks, quality checks, and run_all_quality_checks."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.quality_gates import (
    gate_script_length,
    gate_verification_passed,
    gate_audio_exists,
    gate_wpm_range,
    gate_short_script_length,
    run_tier0_prerender,
    run_tier1_postrender,
    run_tier2_content,
    run_all_quality_checks,
)


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


def _good_research():
    return {
        "core_facts": [f"Fact {i}" for i in range(6)],
        "primary_sources": [f"Source {i}" for i in range(4)],
        "key_figures": ["Figure 1", "Figure 2", "Figure 3"],
    }


def _good_angle():
    return {
        "unique_angle": "A completely new perspective on the Roman Empire that focuses on the daily lives of common citizens rather than emperors.",
        "gap_in_coverage": "No existing documentary covers this angle.",
    }


def _good_images():
    return {
        "images": [{"path": f"/tmp/img_{i}.png", "prompt": f"prompt {i}"} for i in range(8)],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Gate checks
# ══════════════════════════════════════════════════════════════════════════════

class TestGateScriptLength:
    def test_passes_standard_tier(self):
        passed, reason = gate_script_length({"full_script": "word " * 1200, "length_tier": "STANDARD"})
        assert passed is True
        assert reason == ""

    def test_fails_too_short(self):
        passed, reason = gate_script_length({"full_script": "word " * 500})
        assert passed is False
        assert "too short" in reason.lower()

    def test_fails_too_long_standard(self):
        passed, reason = gate_script_length({"full_script": "word " * 1600, "length_tier": "STANDARD"})
        assert passed is False
        assert "too long" in reason.lower()

    def test_passes_deep_dive_tier(self):
        passed, reason = gate_script_length({"full_script": "word " * 2500, "length_tier": "DEEP_DIVE"})
        assert passed is True

    def test_passes_epic_tier(self):
        passed, reason = gate_script_length({"full_script": "word " * 3400, "length_tier": "EPIC"})
        assert passed is True


class TestGateVerificationPassed:
    def test_passes_normal_verdict(self):
        passed, reason = gate_verification_passed({"overall_verdict": "APPROVED"})
        assert passed is True

    def test_fails_requires_rewrite(self):
        passed, reason = gate_verification_passed({"overall_verdict": "REQUIRES_REWRITE", "reason": "Too many errors."})
        assert passed is False
        assert "Too many errors" in reason

    def test_passes_empty_dict(self):
        passed, reason = gate_verification_passed({})
        assert passed is True


class TestGateAudioExists:
    def test_passes_good_audio(self, tmp_path):
        audio = tmp_path / "narration.mp3"
        audio.write_bytes(b"\x00" * 600_000)
        passed, reason = gate_audio_exists(str(audio))
        assert passed is True

    def test_fails_missing_file(self):
        passed, reason = gate_audio_exists("/nonexistent/audio.mp3")
        assert passed is False
        assert "not found" in reason

    def test_fails_tiny_file(self, tmp_path):
        audio = tmp_path / "tiny.mp3"
        audio.write_bytes(b"\x00" * 100)
        passed, reason = gate_audio_exists(str(audio))
        assert passed is False
        assert "too small" in reason.lower()


class TestGateWpmRange:
    def test_passes_within_range(self):
        # 1200 words / 600s = 120 WPM, within 110.5-149.5
        passed, reason = gate_wpm_range(1200, 600)
        assert passed is True

    def test_fails_too_fast(self):
        passed, reason = gate_wpm_range(1000, 300)
        assert passed is False
        assert "WPM" in reason

    def test_fails_zero_duration(self):
        passed, reason = gate_wpm_range(1000, 0)
        assert passed is False


class TestGateShortScriptLength:
    def test_passes_valid_short(self):
        passed, reason = gate_short_script_length({"full_script": "word " * 120})
        assert passed is True

    def test_fails_too_short(self):
        passed, reason = gate_short_script_length({"full_script": "word " * 50})
        assert passed is False

    def test_fails_too_long(self):
        passed, reason = gate_short_script_length({"full_script": "word " * 250})
        assert passed is False


# ══════════════════════════════════════════════════════════════════════════════
# run_tier0_prerender — additional coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestTier0Additional:
    def test_passes_with_valid_data(self, tmp_path):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(tmp_path),
            "seo": _good_seo(),
        })
        assert result["passed"] is True
        assert result["errors"] == []
        assert "warnings" in result

    def test_fails_when_script_missing(self):
        result = run_tier0_prerender({
            "script": {},
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert len(result["errors"]) > 0

    def test_fails_when_audio_missing_duration(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": {},
            "seo": _good_seo(),
        })
        assert result["passed"] is False
        assert any("audio" in e.lower() or "No audio" in e for e in result["errors"])

    def test_warns_on_short_script(self):
        """Short word count in full_script triggers a warning (not error if above min)."""
        script = _good_script()
        # 1050 words — just above gate minimum, but might trigger scene warnings
        script["full_script"] = "word " * 1050
        script["word_count"] = 1050
        result = run_tier0_prerender({
            "script": script,
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        # Should pass (above 1000 word minimum)
        assert result["passed"] is True

    def test_returns_correct_keys(self):
        result = run_tier0_prerender({
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "seo": _good_seo(),
        })
        assert "passed" in result
        assert "errors" in result
        assert "warnings" in result


# ══════════════════════════════════════════════════════════════════════════════
# run_tier1_postrender — additional coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestTier1Additional:
    def test_fails_when_video_does_not_exist(self):
        result = run_tier1_postrender("/nonexistent/video.mp4", _good_audio(), _good_script())
        assert result["passed"] is False
        assert any("not found" in e for e in result["errors"])

    @patch("core.quality_gates.validate_video_ffprobe")
    def test_passes_with_valid_video(self, mock_probe, tmp_path):
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
        assert "metrics" in result
        assert result["metrics"]["file_size_mb"] > 10

    def test_returns_metrics_dict(self):
        result = run_tier1_postrender("", _good_audio(), _good_script())
        assert "metrics" in result
        assert isinstance(result["metrics"], dict)


# ══════════════════════════════════════════════════════════════════════════════
# run_tier2_content
# ══════════════════════════════════════════════════════════════════════════════

class TestTier2Additional:
    def test_returns_sync_score_and_passed(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        result = run_tier2_content(str(video), _good_script(), _good_scenes())
        assert "sync_score" in result
        assert "passed" in result
        assert isinstance(result["sync_score"], float)

    def test_handles_empty_scenes(self, tmp_path):
        video = tmp_path / "vid.mp4"
        video.write_bytes(b"\x00" * 100)
        result = run_tier2_content(str(video), _good_script(), {"scenes": []})
        assert result["passed"] is True
        assert result["sync_score"] == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# run_all_quality_checks
# ══════════════════════════════════════════════════════════════════════════════

class TestRunAllQualityChecks:
    def test_aggregates_all_tier_results(self):
        outputs = {
            "research": _good_research(),
            "angle": _good_angle(),
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "images": _good_images(),
            "seo": _good_seo(),
        }
        result = run_all_quality_checks(outputs)
        assert "warnings" in result
        assert "metrics" in result
        assert "total_warnings" in result
        assert isinstance(result["warnings"], list)
        assert isinstance(result["metrics"], dict)

    def test_returns_total_warnings_count(self):
        outputs = {
            "research": _good_research(),
            "angle": _good_angle(),
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "images": _good_images(),
            "seo": _good_seo(),
        }
        result = run_all_quality_checks(outputs)
        assert result["total_warnings"] == len(result["warnings"])

    def test_returns_metrics_dict(self):
        outputs = {
            "research": _good_research(),
            "angle": _good_angle(),
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "images": _good_images(),
            "seo": _good_seo(),
        }
        result = run_all_quality_checks(outputs)
        assert isinstance(result["metrics"], dict)
        # metrics_script should contribute word_count
        assert "word_count" in result["metrics"]

    def test_empty_outputs_does_not_crash(self):
        result = run_all_quality_checks({})
        assert "warnings" in result
        assert "total_warnings" in result
        assert result["total_warnings"] >= 0

    def test_poor_research_produces_warnings(self):
        outputs = {
            "research": {"core_facts": [], "primary_sources": [], "key_figures": []},
            "angle": _good_angle(),
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "images": _good_images(),
            "seo": _good_seo(),
        }
        result = run_all_quality_checks(outputs)
        assert result["total_warnings"] > 0
        assert any("core facts" in w.lower() or "Research" in w for w in result["warnings"])

    def test_broll_scores_in_metrics(self):
        outputs = {
            "research": _good_research(),
            "angle": _good_angle(),
            "script": _good_script(),
            "scenes": _good_scenes(),
            "audio": _good_audio(),
            "images": _good_images(),
            "seo": _good_seo(),
        }
        result = run_all_quality_checks(outputs)
        # Scenes have image_prompts so broll scoring should produce metrics
        assert "avg_broll_score" in result["metrics"]
        assert "min_broll_score" in result["metrics"]

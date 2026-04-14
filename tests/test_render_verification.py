"""Tests for core/render_verification.py — post-render output verification."""

import json
from unittest.mock import patch

from core.render_verification import (
    measure_loudness,
    measure_actual_wpm,
    measure_volume_profile,
    measure_silence_structure,
    verify_visual_output,
    verify_render_output,
    _build_narration_mask,
    _run_cmd,
    _ffprobe_json,
    _get_video_duration,
    _get_resolution,
    RenderVerification,
    VisualVerification,
)


# ── _build_narration_mask tests ────────────────────────────────────────────


class TestNarrationMask:
    def test_empty_input(self):
        assert _build_narration_mask([]) == []

    def test_single_word(self):
        words = [{"start": 1.0, "end": 1.5}]
        mask = _build_narration_mask(words)
        assert len(mask) == 1
        assert mask[0] == {"start": 1.0, "end": 1.5}

    def test_words_merge_within_threshold(self):
        words = [
            {"start": 1.0, "end": 1.5},
            {"start": 1.6, "end": 2.0},  # 0.1s gap < 0.3s threshold
            {"start": 2.1, "end": 2.5},  # 0.1s gap < 0.3s threshold
        ]
        mask = _build_narration_mask(words)
        assert len(mask) == 1
        assert mask[0]["start"] == 1.0
        assert mask[0]["end"] == 2.5

    def test_words_split_on_gap(self):
        words = [
            {"start": 1.0, "end": 1.5},
            {"start": 3.0, "end": 3.5},  # 1.5s gap > 0.3s threshold
        ]
        mask = _build_narration_mask(words)
        assert len(mask) == 2
        assert mask[0]["end"] == 1.5
        assert mask[1]["start"] == 3.0

    def test_unsorted_input(self):
        words = [
            {"start": 3.0, "end": 3.5},
            {"start": 1.0, "end": 1.5},
        ]
        mask = _build_narration_mask(words)
        assert len(mask) == 2
        assert mask[0]["start"] == 1.0


# ── Loudness tests ─────────────────────────────────────────────────────────


class TestMeasureLoudness:
    def test_missing_file_returns_none(self, tmp_path):
        assert measure_loudness(str(tmp_path / "nonexistent.mp4")) is None

    @patch("core.render_verification._run_cmd")
    def test_ebur128_parsing(self, mock_cmd, tmp_path):
        # Create a dummy file
        video = tmp_path / "test.mp4"
        video.touch()

        # Mock ebur128 stderr output
        mock_cmd.return_value = ("", """
[Parsed_ebur128_0 @ 0x12345] Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.2 LUFS

  Loudness range:
    LRA:        10.8 LU
    Threshold: -34.2 LUFS
    LRA low:   -21.5 LUFS
    LRA high:  -10.7 LUFS

  True peak:
    Peak:       -1.3 dBFS
""")
        result = measure_loudness(str(video))
        assert result is not None
        assert result["integrated_lufs"] == -14.2
        assert result["method"] == "ebur128"

    @patch("core.render_verification._run_cmd")
    def test_volumedetect_fallback(self, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        # First call (ebur128) returns nothing useful, second call (volumedetect) works
        mock_cmd.side_effect = [
            ("", ""),  # ebur128 fails
            ("", "[Parsed_volumedetect_0 @ 0x5678] mean_volume: -18.5 dB\n"
                 "[Parsed_volumedetect_0 @ 0x5678] max_volume: -12.3 dB"),
        ]
        result = measure_loudness(str(video))
        assert result is not None
        assert result["integrated_lufs"] == -18.5
        assert result["method"] == "volumedetect"

    @patch("core.render_verification._run_cmd")
    def test_both_methods_fail(self, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_cmd.return_value = ("", "")
        assert measure_loudness(str(video)) is None


# ── WPM tests ──────────────────────────────────────────────────────────────


class TestMeasureWPM:
    @patch("core.render_verification._get_video_duration")
    def test_basic_wpm(self, mock_dur):
        mock_dur.return_value = 120.0  # 2 minutes
        result = measure_actual_wpm("/fake.mp4", total_words=260)
        assert result is not None
        assert result["overall_wpm"] == 130.0
        assert result["deviation_pct"] == 0.0

    @patch("core.render_verification._get_video_duration")
    def test_fast_speech(self, mock_dur):
        mock_dur.return_value = 60.0  # 1 minute
        result = measure_actual_wpm("/fake.mp4", total_words=180)
        assert result is not None
        assert result["overall_wpm"] == 180.0
        assert result["deviation_pct"] > 0  # faster than target

    @patch("core.render_verification._get_video_duration")
    def test_word_timestamps_count(self, mock_dur):
        mock_dur.return_value = 60.0
        timestamps = [{"start": i, "end": i + 0.3} for i in range(130)]
        result = measure_actual_wpm("/fake.mp4", word_timestamps=timestamps)
        assert result is not None
        assert result["total_words"] == 130

    @patch("core.render_verification._get_video_duration")
    def test_zero_words_returns_none(self, mock_dur):
        mock_dur.return_value = 120.0
        assert measure_actual_wpm("/fake.mp4", total_words=0) is None

    @patch("core.render_verification._get_video_duration")
    def test_zero_duration_returns_none(self, mock_dur):
        mock_dur.return_value = 0.0
        assert measure_actual_wpm("/fake.mp4", total_words=100) is None

    @patch("core.render_verification._get_video_duration")
    def test_no_duration_returns_none(self, mock_dur):
        mock_dur.return_value = None
        assert measure_actual_wpm("/fake.mp4", total_words=100) is None


# ── Volume profile tests ──────────────────────────────────────────────────


class TestVolumeProfile:
    def test_no_file_returns_none(self, tmp_path):
        assert measure_volume_profile(str(tmp_path / "no.mp4")) is None

    def test_no_mask_returns_none(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        assert measure_volume_profile(str(video), narration_mask=None) is None

    @patch("core.render_verification._get_video_duration")
    @patch("core.render_verification._run_cmd")
    def test_speech_vs_silence_detection(self, mock_cmd, mock_dur, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_dur.return_value = 30.0

        # Alternating: speech loud (-15), silence quieter (-25)
        call_count = [0]
        def side_effect(cmd, timeout=60):
            call_count[0] += 1
            if "-af" in cmd and "volumedetect" in cmd:
                # Odd calls = speech, even = silence
                if call_count[0] <= 2:
                    return ("", "mean_volume: -15.0 dB\nmax_volume: -10.0 dB")
                else:
                    return ("", "mean_volume: -25.0 dB\nmax_volume: -20.0 dB")
            return ("", "")

        mock_cmd.side_effect = side_effect
        mask = [
            {"start": 0.0, "end": 5.0},
            {"start": 10.0, "end": 15.0},
        ]
        result = measure_volume_profile(str(video), narration_mask=mask)
        assert result is not None
        assert "speech_segments_mean_db" in result
        assert "silence_segments_mean_db" in result
        assert "segments_sampled" in result


# ── Silence structure tests ────────────────────────────────────────────────


class TestSilenceStructure:
    @patch("core.render_verification._get_video_duration")
    def test_basic_gap_detection(self, mock_dur):
        mock_dur.return_value = 20.0
        words = [
            {"start": 0.0, "end": 1.0},
            {"start": 1.1, "end": 2.0},   # 0.1s gap (below threshold)
            {"start": 3.5, "end": 4.5},   # 1.5s gap (above threshold)
            {"start": 5.0, "end": 6.0},   # 0.5s gap (above threshold)
        ]
        result = measure_silence_structure("/fake.mp4", words)
        assert result is not None
        assert result["silence_gaps_count"] == 2

    @patch("core.render_verification._get_video_duration")
    def test_no_gaps(self, mock_dur):
        mock_dur.return_value = 10.0
        words = [
            {"start": 0.0, "end": 1.0},
            {"start": 1.1, "end": 2.0},
            {"start": 2.1, "end": 3.0},
        ]
        result = measure_silence_structure("/fake.mp4", words)
        assert result is not None
        assert result["silence_gaps_count"] == 0

    @patch("core.render_verification._get_video_duration")
    def test_insufficient_words(self, mock_dur):
        mock_dur.return_value = 10.0
        assert measure_silence_structure("/fake.mp4", [{"start": 0, "end": 1}]) is None
        assert measure_silence_structure("/fake.mp4", []) is None
        assert measure_silence_structure("/fake.mp4", None) is None

    @patch("core.render_verification._get_video_duration")
    def test_silence_percentage(self, mock_dur):
        mock_dur.return_value = 10.0
        # 2s speech + 5s gap + 2s speech = 9s content in 10s video
        words = [
            {"start": 0.0, "end": 2.0},
            {"start": 7.0, "end": 9.0},  # 5s gap
        ]
        result = measure_silence_structure("/fake.mp4", words)
        assert result is not None
        assert result["silence_gaps_count"] == 1
        assert result["max_gap_duration"] == 5.0
        assert result["total_silence_pct"] == 50.0  # 5/10 * 100


# ── Visual verification tests ─────────────────────────────────────────────


class TestBlackFrameParsing:
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_black_frame_detection(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)

        mock_cmd.return_value = ("", (
            "[blackdetect @ 0x1234] black_start:120.5 black_end:121.2 black_duration:0.7\n"
            "[blackdetect @ 0x1234] black_start:200.0 black_end:200.8 black_duration:0.8\n"
        ))

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1920, 1080))
        assert result.black_frame_report["total_black_segments"] == 2
        assert result.black_frame_report["unexpected_black_segments"] == 2

    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_black_frames_at_boundaries_expected(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)

        mock_cmd.return_value = ("", (
            "[blackdetect @ 0x1234] black_start:10.0 black_end:10.7 black_duration:0.7\n"
        ))

        scenes = [
            {"start_time": 0, "end_time": 10.0},
            {"start_time": 10.5, "end_time": 20.0},
        ]
        result = verify_visual_output(str(video), scenes=scenes, expected_resolution=(1920, 1080))
        # black_start:10.0 is at scene boundary → expected
        assert result.black_frame_report["unexpected_black_segments"] == 0


class TestResolution:
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_correct_resolution(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1920, 1080))
        assert result.aspect_ratio_ok is True

    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_wrong_resolution(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1280, 720)
        mock_cmd.return_value = ("", "")

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1920, 1080))
        assert result.aspect_ratio_ok is False
        assert any("Resolution" in d for d in result.deviations)

    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_shorts_aspect_ratio(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1080, 1920)
        mock_cmd.return_value = ("", "")

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1080, 1920))
        assert result.aspect_ratio_ok is True


class TestVisualMissing:
    def test_missing_video(self, tmp_path):
        result = verify_visual_output(str(tmp_path / "no.mp4"), scenes=[])
        assert result.overall_visual_compliance == 0.0
        assert "Video file not found" in result.deviations


# ── Sharpness tests ────────────────────────────────────────────────────────


class TestSharpness:
    @patch("core.render_verification._compute_sharpness")
    @patch("core.render_verification._extract_frame")
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_blurry_scene_flagged(self, mock_res, mock_cmd, mock_extract, mock_sharp, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")  # no black frames
        mock_extract.return_value = True
        mock_sharp.return_value = 30.0  # below 50 threshold (calibrated for AI art + H.264)

        scenes = [{"start_time": 0, "end_time": 5}]
        result = verify_visual_output(str(video), scenes=scenes, expected_resolution=(1920, 1080))
        assert any("sharpness" in d.lower() for d in result.deviations)

    @patch("core.render_verification._compute_sharpness")
    @patch("core.render_verification._extract_frame")
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_sharp_scene_ok(self, mock_res, mock_cmd, mock_extract, mock_sharp, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")
        mock_extract.return_value = True
        mock_sharp.return_value = 500.0  # well above threshold

        scenes = [{"start_time": 0, "end_time": 5}]
        result = verify_visual_output(str(video), scenes=scenes, expected_resolution=(1920, 1080))
        assert not any("sharpness" in d.lower() for d in result.deviations)


# ── Ken Burns motion tests ─────────────────────────────────────────────────


class TestKenBurnsMotion:
    @patch("core.render_verification._compute_frame_diff")
    @patch("core.render_verification._compute_sharpness")
    @patch("core.render_verification._extract_frame")
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_static_scene_flagged(self, mock_res, mock_cmd, mock_extract, mock_sharp, mock_diff, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")
        mock_extract.return_value = True
        mock_sharp.return_value = 500.0
        mock_diff.return_value = 0.5  # nearly zero diff → static

        scenes = [{"start_time": 0, "end_time": 5}]  # >1.5s so motion check runs
        result = verify_visual_output(str(video), scenes=scenes, expected_resolution=(1920, 1080))
        assert any("Ken Burns" in d for d in result.deviations)

    @patch("core.render_verification._compute_frame_diff")
    @patch("core.render_verification._compute_sharpness")
    @patch("core.render_verification._extract_frame")
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_good_motion_ok(self, mock_res, mock_cmd, mock_extract, mock_sharp, mock_diff, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")
        mock_extract.return_value = True
        mock_sharp.return_value = 500.0
        mock_diff.return_value = 10.0  # good motion

        scenes = [{"start_time": 0, "end_time": 5}]
        result = verify_visual_output(str(video), scenes=scenes, expected_resolution=(1920, 1080))
        assert not any("Ken Burns" in d for d in result.deviations)


# ── Orchestrator tests ─────────────────────────────────────────────────────


class TestVerifyRenderOutput:
    def test_missing_file_returns_none(self, tmp_path):
        assert verify_render_output(str(tmp_path / "no.mp4"), {}, {}) is None

    @patch("core.render_verification.verify_visual_output")
    @patch("core.render_verification.measure_silence_structure")
    @patch("core.render_verification.measure_volume_profile")
    @patch("core.render_verification.measure_actual_wpm")
    @patch("core.render_verification.measure_loudness")
    def test_full_compliance(self, mock_lufs, mock_wpm, mock_vol, mock_sil, mock_vis, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        mock_lufs.return_value = {"integrated_lufs": -14.0, "method": "ebur128"}
        mock_wpm.return_value = {"overall_wpm": 130.0, "deviation_pct": 0.0}
        mock_vol.return_value = {"ducking_detected": True, "segments_sampled": 6}
        mock_sil.return_value = {"silence_gaps_count": 3}
        mock_vis.return_value = VisualVerification(overall_visual_compliance=1.0)

        result = verify_render_output(str(video), {}, {})
        assert result is not None
        assert result.overall_compliance == 1.0
        assert len(result.deviations) == 0

    @patch("core.render_verification.verify_visual_output")
    @patch("core.render_verification.measure_silence_structure")
    @patch("core.render_verification.measure_volume_profile")
    @patch("core.render_verification.measure_actual_wpm")
    @patch("core.render_verification.measure_loudness")
    def test_loudness_deviation_flagged(self, mock_lufs, mock_wpm, mock_vol, mock_sil, mock_vis, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        mock_lufs.return_value = {"integrated_lufs": -20.0, "method": "ebur128"}  # 6 LUFS off
        mock_wpm.return_value = {"overall_wpm": 130.0, "deviation_pct": 0.0}
        mock_vol.return_value = {"ducking_detected": True}
        mock_sil.return_value = {}
        mock_vis.return_value = VisualVerification(overall_visual_compliance=1.0)

        result = verify_render_output(str(video), {}, {})
        assert result is not None
        assert any("Loudness" in d for d in result.deviations)
        assert result.overall_compliance < 1.0

    @patch("core.render_verification.verify_visual_output")
    @patch("core.render_verification.measure_silence_structure")
    @patch("core.render_verification.measure_volume_profile")
    @patch("core.render_verification.measure_actual_wpm")
    @patch("core.render_verification.measure_loudness")
    def test_wpm_deviation_flagged(self, mock_lufs, mock_wpm, mock_vol, mock_sil, mock_vis, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        mock_lufs.return_value = {"integrated_lufs": -14.0, "method": "ebur128"}
        mock_wpm.return_value = {"overall_wpm": 180.0, "deviation_pct": 38.5}  # way fast
        mock_vol.return_value = {"ducking_detected": True}
        mock_sil.return_value = {}
        mock_vis.return_value = VisualVerification(overall_visual_compliance=1.0)

        result = verify_render_output(str(video), {}, {})
        assert result is not None
        assert any("WPM" in d for d in result.deviations)

    @patch("core.render_verification._get_video_duration")
    @patch("core.render_verification.verify_visual_output")
    @patch("core.render_verification.measure_silence_structure")
    @patch("core.render_verification.measure_volume_profile")
    @patch("core.render_verification.measure_actual_wpm")
    @patch("core.render_verification.measure_loudness")
    def test_shorts_duration_out_of_range(self, mock_lufs, mock_wpm, mock_vol, mock_sil, mock_vis, mock_dur, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        mock_lufs.return_value = None
        mock_wpm.return_value = None
        mock_vol.return_value = None
        mock_sil.return_value = None
        mock_vis.return_value = VisualVerification()
        mock_dur.return_value = 180.0  # 3 min, too long for shorts

        result = verify_render_output(str(video), {}, {}, format="short")
        assert result is not None
        assert any("duration" in d.lower() for d in result.deviations)

    @patch("core.render_verification.verify_visual_output")
    @patch("core.render_verification.measure_silence_structure")
    @patch("core.render_verification.measure_volume_profile")
    @patch("core.render_verification.measure_actual_wpm")
    @patch("core.render_verification.measure_loudness")
    def test_ducking_not_detected(self, mock_lufs, mock_wpm, mock_vol, mock_sil, mock_vis, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()

        mock_lufs.return_value = {"integrated_lufs": -14.0, "method": "ebur128"}
        mock_wpm.return_value = {"overall_wpm": 130.0, "deviation_pct": 0.0}
        mock_vol.return_value = {"ducking_detected": False, "segments_sampled": 6}
        mock_sil.return_value = {}
        mock_vis.return_value = VisualVerification(overall_visual_compliance=1.0)

        # Provide word_timestamps so narration_mask is non-empty → volume profile runs
        state = {"word_timestamps": [{"start": 0, "end": 1}, {"start": 2, "end": 3}]}
        result = verify_render_output(str(video), {}, state)
        assert any("ducking" in d.lower() for d in result.deviations)


# ── RenderVerification dataclass tests ─────────────────────────────────────


class TestRenderVerificationDataclass:
    def test_to_dict(self):
        rv = RenderVerification(
            loudness={"integrated_lufs": -14.0},
            format="long",
            overall_compliance=0.85,
        )
        d = rv.to_dict()
        assert d["loudness"]["integrated_lufs"] == -14.0
        assert d["format"] == "long"
        assert d["overall_compliance"] == 0.85

    def test_default_values(self):
        rv = RenderVerification()
        assert rv.loudness is None
        assert rv.format == "long"
        assert rv.overall_compliance == 1.0
        assert rv.deviations == []


# ── Edge cases / error handling ────────────────────────────────────────────


class TestErrorHandling:
    @patch("core.render_verification._run_cmd")
    def test_ffprobe_failure_returns_none(self, mock_cmd):
        mock_cmd.return_value = ("", "")
        assert _ffprobe_json("/no/file.mp4") is None

    @patch("core.render_verification._run_cmd")
    def test_ffprobe_bad_json(self, mock_cmd):
        mock_cmd.return_value = ("not json", "")
        assert _ffprobe_json("/no/file.mp4") is None

    @patch("core.render_verification._run_cmd")
    def test_get_duration_no_format(self, mock_cmd):
        mock_cmd.return_value = (json.dumps({"streams": []}), "")
        assert _get_video_duration("/fake.mp4") == 0.0  # format.duration defaults to 0

    @patch("core.render_verification._run_cmd")
    def test_get_resolution_no_video_stream(self, mock_cmd):
        mock_cmd.return_value = (json.dumps({
            "streams": [{"codec_type": "audio"}],
            "format": {},
        }), "")
        assert _get_resolution("/fake.mp4") is None

    def test_run_cmd_file_not_found(self):
        # Non-existent binary
        stdout, stderr = _run_cmd(["__nonexistent_binary_xyz__"])
        assert stdout == ""
        assert stderr == ""


# ── Visual compliance scoring ──────────────────────────────────────────────


class TestVisualComplianceScoring:
    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_all_checks_pass(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1920, 1080)
        mock_cmd.return_value = ("", "")  # no black frames

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1920, 1080))
        # resolution ok + no black frames = 2/2
        assert result.overall_visual_compliance == 1.0

    @patch("core.render_verification._run_cmd")
    @patch("core.render_verification._get_resolution")
    def test_resolution_fail_lowers_score(self, mock_res, mock_cmd, tmp_path):
        video = tmp_path / "test.mp4"
        video.touch()
        mock_res.return_value = (1280, 720)  # wrong
        mock_cmd.return_value = ("", "")

        result = verify_visual_output(str(video), scenes=[], expected_resolution=(1920, 1080))
        assert result.overall_visual_compliance < 1.0

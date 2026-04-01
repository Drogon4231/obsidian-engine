"""
Post-render verification — measures actual audio/video output against intended params.

Closes the intent-vs-outcome gap: the optimizer knows what it asked for,
this module tells it what it got.

Uses ffmpeg/ffprobe (already available in the pipeline). Pure functions
except for subprocess calls to ffmpeg.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class VisualVerification:
    scene_transitions: dict = field(default_factory=dict)
    black_frame_report: dict = field(default_factory=dict)
    sharpness_report: list = field(default_factory=list)
    motion_report: list = field(default_factory=list)
    resolution: dict = field(default_factory=dict)
    aspect_ratio_ok: bool = True
    overall_visual_compliance: float = 1.0
    deviations: list[str] = field(default_factory=list)


@dataclass
class RenderVerification:
    loudness: dict | None = None
    wpm: dict | None = None
    volume_profile: dict | None = None
    silence_structure: dict | None = None
    visual: VisualVerification | None = None
    format: str = "long"
    overall_compliance: float = 1.0
    deviations: list[str] = field(default_factory=list)
    verified_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── ffmpeg/ffprobe helpers ──────────────────────────────────────────────────

def _run_cmd(cmd: list[str], timeout: int = 60) -> tuple[str, str]:
    """Run a command, return (stdout, stderr). Returns empty on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout, result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "", ""


def _ffprobe_json(video_path: str) -> dict | None:
    """Get ffprobe JSON output for a video file."""
    stdout, _ = _run_cmd([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path),
    ])
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def _get_video_duration(video_path: str) -> float | None:
    """Get video duration in seconds from ffprobe."""
    info = _ffprobe_json(video_path)
    if not info:
        return None
    try:
        return float(info.get("format", {}).get("duration", 0))
    except (ValueError, TypeError):
        return None


def _get_resolution(video_path: str) -> tuple[int, int] | None:
    """Get (width, height) from first video stream."""
    info = _ffprobe_json(video_path)
    if not info:
        return None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            try:
                return int(stream["width"]), int(stream["height"])
            except (KeyError, ValueError):
                pass
    return None


# ── Audio measurements ──────────────────────────────────────────────────────

def measure_loudness(video_path: str) -> dict | None:
    """Measure integrated loudness (LUFS) using ffmpeg ebur128 filter.

    Falls back to volumedetect if ebur128 is unavailable.
    Returns: {"integrated_lufs": float, "method": str} or None.
    """
    if not Path(video_path).exists():
        return None

    # Try ebur128 first (more accurate)
    _, stderr = _run_cmd([
        "ffmpeg", "-nostats", "-i", str(video_path),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-",
    ], timeout=120)

    if stderr:
        for line in stderr.split("\n"):
            line_stripped = line.strip()
            # Parse "I: -14.2 LUFS" from summary
            if line_stripped.startswith("I:") and "LUFS" in line_stripped:
                try:
                    lufs_str = line_stripped.split(":")[1].strip().split()[0]
                    return {
                        "integrated_lufs": float(lufs_str),
                        "method": "ebur128",
                    }
                except (ValueError, IndexError):
                    pass

    # Fallback: volumedetect (simpler, less accurate)
    _, stderr = _run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-af", "volumedetect", "-f", "null", "-",
    ], timeout=120)

    if stderr:
        mean_vol = None
        for line in stderr.split("\n"):
            if "mean_volume:" in line:
                try:
                    mean_vol = float(line.split("mean_volume:")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        if mean_vol is not None:
            return {
                "integrated_lufs": mean_vol,  # Approximate — dB not LUFS
                "method": "volumedetect",
            }

    return None


def measure_actual_wpm(
    video_path: str,
    word_timestamps: list[dict] | None = None,
    total_words: int = 0,
) -> dict | None:
    """Measure actual words-per-minute from video duration and word count.

    Returns: {"overall_wpm": float, "target_wpm": 130, "deviation_pct": float}.
    """
    duration = _get_video_duration(video_path)
    if not duration or duration <= 0:
        return None

    if word_timestamps:
        total_words = len(word_timestamps)

    if total_words <= 0:
        return None

    wpm = total_words / (duration / 60.0)
    target = 130.0
    deviation = ((wpm - target) / target) * 100

    return {
        "overall_wpm": round(wpm, 1),
        "target_wpm": target,
        "deviation_pct": round(deviation, 1),
        "duration_seconds": round(duration, 1),
        "total_words": total_words,
    }


def measure_volume_profile(
    video_path: str,
    narration_mask: list[dict] | None = None,
) -> dict | None:
    """Measure volume levels during speech vs silence segments.

    Uses volumedetect on extracted segments (same pattern as content_auditor.py).
    Samples up to 5 segments of each type to limit ffmpeg calls.
    """
    if not Path(video_path).exists() or not narration_mask:
        return None

    duration = _get_video_duration(video_path)
    if not duration:
        return None

    def _measure_segment_volume(start: float, end: float) -> float | None:
        """Get mean volume (dB) for a time segment."""
        if end <= start or end - start < 0.3:
            return None
        _, stderr = _run_cmd([
            "ffmpeg", "-ss", str(start), "-to", str(end),
            "-i", str(video_path), "-af", "volumedetect",
            "-f", "null", "-",
        ], timeout=30)
        if not stderr:
            return None
        for line in stderr.split("\n"):
            if "mean_volume:" in line:
                try:
                    return float(line.split("mean_volume:")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        return None

    # Collect speech and silence segments
    speech_vols: list[float] = []
    silence_vols: list[float] = []

    # Sample up to 5 speech segments
    speech_segments = narration_mask[:5]
    for seg in speech_segments:
        vol = _measure_segment_volume(seg["start"], seg["end"])
        if vol is not None:
            speech_vols.append(vol)

    # Build silence segments from gaps between speech
    silence_segments: list[dict] = []
    prev_end = 0.0
    for seg in narration_mask:
        if seg["start"] > prev_end + 0.5:
            silence_segments.append({"start": prev_end, "end": seg["start"]})
        prev_end = seg["end"]
    if duration > prev_end + 0.5:
        silence_segments.append({"start": prev_end, "end": duration})

    for seg in silence_segments[:5]:
        vol = _measure_segment_volume(seg["start"], seg["end"])
        if vol is not None:
            silence_vols.append(vol)

    if not speech_vols or not silence_vols:
        return None

    speech_mean = sum(speech_vols) / len(speech_vols)
    silence_mean = sum(silence_vols) / len(silence_vols)
    ratio_db = silence_mean - speech_mean  # Positive = silence is louder than speech (expected for music)

    return {
        "speech_segments_mean_db": round(speech_mean, 1),
        "silence_segments_mean_db": round(silence_mean, 1),
        "speech_to_silence_ratio_db": round(ratio_db, 1),
        "segments_sampled": len(speech_vols) + len(silence_vols),
        "ducking_detected": ratio_db > 2.0,  # Silence louder → music ducking is working
    }


def measure_silence_structure(
    video_path: str,
    word_timestamps: list[dict] | None = None,
) -> dict | None:
    """Analyze gaps between speech segments.

    Returns silence gap distribution and total silence percentage.
    """
    duration = _get_video_duration(video_path)
    if not duration or not word_timestamps or len(word_timestamps) < 2:
        return None

    # Find gaps > 0.3s between consecutive words
    gaps: list[dict] = []
    sorted_words = sorted(word_timestamps, key=lambda w: w.get("start", 0))

    for i in range(len(sorted_words) - 1):
        end_current = sorted_words[i].get("end", 0)
        start_next = sorted_words[i + 1].get("start", 0)
        gap_dur = start_next - end_current
        if gap_dur > 0.3:
            gaps.append({
                "start": round(end_current, 2),
                "end": round(start_next, 2),
                "duration": round(gap_dur, 2),
            })

    total_silence = sum(g["duration"] for g in gaps)
    total_speech = sum(
        w.get("end", 0) - w.get("start", 0)
        for w in sorted_words
        if w.get("end", 0) > w.get("start", 0)
    )

    return {
        "total_silence_pct": round((total_silence / duration) * 100, 1) if duration > 0 else 0,
        "total_speech_pct": round((total_speech / duration) * 100, 1) if duration > 0 else 0,
        "silence_gaps_count": len(gaps),
        "avg_gap_duration": round(total_silence / len(gaps), 2) if gaps else 0,
        "max_gap_duration": round(max(g["duration"] for g in gaps), 2) if gaps else 0,
        "gaps": gaps[:20],  # Limit output size
    }


# ── Visual measurements ─────────────────────────────────────────────────────

def _extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame at a timestamp. Returns True on success."""
    _, _ = _run_cmd([
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2", str(output_path),
    ], timeout=15)
    return Path(output_path).exists() and Path(output_path).stat().st_size > 0


def _compute_sharpness(frame_path: str) -> float | None:
    """Compute Laplacian variance as sharpness metric using PIL + basic math."""
    try:
        from PIL import Image
        img = Image.open(frame_path).convert("L")  # Grayscale
        pixels = list(img.getdata())
        width, height = img.size

        if width < 10 or height < 10:
            return None

        # Simple Laplacian approximation: sum of abs second derivatives
        variance_sum = 0.0
        count = 0
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                idx = y * width + x
                # Laplacian = 4*center - up - down - left - right
                lap = (
                    4 * pixels[idx]
                    - pixels[(y - 1) * width + x]
                    - pixels[(y + 1) * width + x]
                    - pixels[y * width + (x - 1)]
                    - pixels[y * width + (x + 1)]
                )
                variance_sum += lap * lap
                count += 1

        if count == 0:
            return None
        return variance_sum / count

    except Exception:
        return None


def _compute_frame_diff(frame1_path: str, frame2_path: str) -> float | None:
    """Compute mean absolute pixel difference between two frames (0-255 scale)."""
    try:
        from PIL import Image
        img1 = Image.open(frame1_path).convert("L").resize((320, 180))
        img2 = Image.open(frame2_path).convert("L").resize((320, 180))
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())
        if len(pixels1) != len(pixels2) or not pixels1:
            return None
        total_diff = sum(abs(a - b) for a, b in zip(pixels1, pixels2))
        return total_diff / len(pixels1)
    except Exception:
        return None


def verify_visual_output(
    video_path: str,
    scenes: list[dict],
    expected_resolution: tuple[int, int] = (1920, 1080),
    max_scenes_to_check: int = 15,
) -> VisualVerification:
    """Run visual quality checks on rendered video.

    Checks: resolution, black frames, per-scene sharpness, Ken Burns motion.
    """
    result = VisualVerification()

    if not Path(video_path).exists():
        result.deviations.append("Video file not found")
        result.overall_visual_compliance = 0.0
        return result

    # Resolution check
    res = _get_resolution(video_path)
    if res:
        result.resolution = {"actual": f"{res[0]}x{res[1]}", "expected": f"{expected_resolution[0]}x{expected_resolution[1]}"}
        if res != expected_resolution:
            result.deviations.append(
                f"Resolution {res[0]}x{res[1]} != expected {expected_resolution[0]}x{expected_resolution[1]}"
            )
            result.aspect_ratio_ok = False
    else:
        result.deviations.append("Could not determine resolution")

    # Black frame detection
    _, stderr = _run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-vf", "blackdetect=d=0.5:pix_th=0.10",
        "-f", "null", "-",
    ], timeout=120)

    black_segments: list[dict] = []
    if stderr:
        for line in stderr.split("\n"):
            if "black_start:" in line:
                try:
                    parts = line.split()
                    seg: dict = {}
                    for p in parts:
                        if p.startswith("black_start:"):
                            seg["start"] = float(p.split(":")[1])
                        elif p.startswith("black_end:"):
                            seg["end"] = float(p.split(":")[1])
                        elif p.startswith("black_duration:"):
                            seg["duration"] = float(p.split(":")[1])
                    if "start" in seg:
                        black_segments.append(seg)
                except (ValueError, IndexError):
                    pass

    # Filter: black segments at scene boundaries are expected
    scene_boundaries = set()
    for s in scenes:
        scene_boundaries.add(round(s.get("start_time", 0), 0))
        scene_boundaries.add(round(s.get("end_time", 0), 0))

    # Collect time ranges where black frames are expected (silence beats, text overlays, transitions)
    expected_dark_ranges = set()
    for s in scenes:
        if s.get("intent_silence_beat") or s.get("visual_treatment") == "text_overlay_dark" or s.get("is_breathing_room"):
            expected_dark_ranges.add(round(s.get("start_time", 0), 0))
            expected_dark_ranges.add(round(s.get("end_time", 0), 0))

    unexpected_black = []
    for seg in black_segments:
        start_rounded = round(seg.get("start", 0), 0)
        near_boundary = any(abs(start_rounded - b) < 2 for b in scene_boundaries)
        near_expected_dark = any(abs(start_rounded - d) < 3 for d in expected_dark_ranges)
        if not near_boundary and not near_expected_dark:
            unexpected_black.append(seg)

    result.black_frame_report = {
        "total_black_segments": len(black_segments),
        "unexpected_black_segments": len(unexpected_black),
        "segments": unexpected_black[:5],
    }
    if unexpected_black:
        result.deviations.append(f"{len(unexpected_black)} unexpected black frame segment(s)")

    # Per-scene sharpness + motion checks (sample up to max_scenes_to_check)
    scenes_to_check = scenes[:max_scenes_to_check]
    if len(scenes) > max_scenes_to_check:
        step = len(scenes) / max_scenes_to_check
        scenes_to_check = [scenes[int(i * step)] for i in range(max_scenes_to_check)]

    tmpdir = tempfile.mkdtemp(prefix="obsidian_verify_")
    try:
        for i, scene in enumerate(scenes_to_check):
            start = scene.get("start_time", 0)
            end = scene.get("end_time", start + 1)
            mid = (start + end) / 2

            # Sharpness at midpoint
            mid_frame = str(Path(tmpdir) / f"mid_{i}.jpg")
            if _extract_frame(video_path, mid, mid_frame):
                sharpness = _compute_sharpness(mid_frame)
                status = "ok"
                if sharpness is not None and sharpness < 100:
                    status = "blurry"
                    result.deviations.append(f"Scene {i}: low sharpness ({sharpness:.0f})")
                result.sharpness_report.append({
                    "scene": i, "laplacian_var": round(sharpness, 1) if sharpness else None,
                    "status": status,
                })

            # Ken Burns motion: compare start+0.5s vs end-0.5s
            if end - start > 1.5:
                start_frame = str(Path(tmpdir) / f"start_{i}.jpg")
                end_frame = str(Path(tmpdir) / f"end_{i}.jpg")
                if (_extract_frame(video_path, start + 0.5, start_frame) and
                        _extract_frame(video_path, end - 0.5, end_frame)):
                    diff = _compute_frame_diff(start_frame, end_frame)
                    if diff is not None:
                        diff_pct = (diff / 255.0) * 100
                        status = "ok"
                        if diff_pct < 0.5:
                            status = "static"
                            result.deviations.append(f"Scene {i}: no Ken Burns motion detected")
                        result.motion_report.append({
                            "scene": i, "pixel_diff_pct": round(diff_pct, 2),
                            "status": status,
                        })
    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    # Compute overall visual compliance
    checks_total = 0
    checks_passed = 0

    if result.resolution:
        checks_total += 1
        if result.aspect_ratio_ok:
            checks_passed += 1

    checks_total += 1  # black frames
    if not unexpected_black:
        checks_passed += 1

    if result.sharpness_report:
        checks_total += 1
        blurry = sum(1 for s in result.sharpness_report if s.get("status") == "blurry")
        if blurry == 0:
            checks_passed += 1
        elif blurry < len(result.sharpness_report) / 2:
            checks_passed += 0.5

    if result.motion_report:
        checks_total += 1
        static = sum(1 for m in result.motion_report if m.get("status") == "static")
        if static == 0:
            checks_passed += 1
        elif static < len(result.motion_report) / 2:
            checks_passed += 0.5

    result.overall_visual_compliance = round(checks_passed / max(1, checks_total), 2)
    return result


# ── Orchestrator ────────────────────────────────────────────────────────────

def verify_render_output(
    video_path: str,
    intended_params: dict,
    pipeline_state: dict,
    format: str = "long",
) -> RenderVerification | None:
    """Run all post-render verification checks.

    Args:
        video_path: Path to the rendered video file.
        intended_params: Production params snapshot (from param_registry).
        pipeline_state: Full pipeline state dict (contains scenes, word_timestamps, etc).
        format: "long" or "short".

    Returns:
        RenderVerification with compliance score and deviations, or None on failure.
    """
    if not Path(video_path).exists():
        return None

    result = RenderVerification(
        format=format,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )

    # Extract data from pipeline state
    word_timestamps = pipeline_state.get("word_timestamps", [])
    scenes = pipeline_state.get("scenes", [])
    audio_data = pipeline_state.get("audio_data", {})
    if not word_timestamps and audio_data:
        word_timestamps = audio_data.get("word_timestamps", [])
    # Fallback: scenes may be nested under stage keys, not top-level
    if not scenes:
        stage_11 = pipeline_state.get("stage_11", {})
        if isinstance(stage_11, dict):
            scenes = stage_11.get("scenes", [])
    if not scenes:
        stage_10 = pipeline_state.get("stage_10", {})
        if isinstance(stage_10, dict):
            scenes = stage_10.get("scenes", [])
    if not scenes:
        # Last resort: read from video-data.json
        try:
            import json as _json
            _vd = Path(video_path).parent.parent / "remotion" / "src" / "video-data.json"
            if _vd.exists():
                scenes = _json.loads(_vd.read_text()).get("scenes", [])
        except Exception:
            pass

    # Build narration mask from word timestamps
    narration_mask = _build_narration_mask(word_timestamps)

    # 1. Loudness
    try:
        result.loudness = measure_loudness(video_path)
        if result.loudness:
            lufs = result.loudness.get("integrated_lufs", -14)
            if abs(lufs - (-14)) > 3:
                result.deviations.append(
                    f"Loudness {lufs:.1f} LUFS (target: -14, deviation: {abs(lufs + 14):.1f})"
                )
    except Exception:
        pass

    # 2. WPM
    try:
        total_words = len(word_timestamps)
        if not total_words:
            total_words = pipeline_state.get("word_count", 0)
        result.wpm = measure_actual_wpm(video_path, word_timestamps, total_words)
        if result.wpm:
            dev = abs(result.wpm.get("deviation_pct", 0))
            if dev > 15:
                result.deviations.append(
                    f"WPM {result.wpm['overall_wpm']:.0f} (target: 130, deviation: {dev:.0f}%)"
                )
    except Exception:
        pass

    # 3. Volume profile (ducking)
    try:
        if narration_mask:
            result.volume_profile = measure_volume_profile(video_path, narration_mask)
            if result.volume_profile and not result.volume_profile.get("ducking_detected", True):
                result.deviations.append("Music ducking not detected in volume profile")
    except Exception:
        pass

    # 4. Silence structure
    try:
        result.silence_structure = measure_silence_structure(video_path, word_timestamps)
    except Exception:
        pass

    # 5. Visual checks
    try:
        expected_res = (1080, 1920) if format == "short" else (1920, 1080)
        result.visual = verify_visual_output(
            video_path, scenes, expected_resolution=expected_res
        )
        result.deviations.extend(result.visual.deviations)
    except Exception:
        pass

    # 6. Shorts-specific checks
    if format == "short":
        try:
            duration = _get_video_duration(video_path)
            if duration and (duration < 15 or duration > 120):
                result.deviations.append(f"Short duration {duration:.0f}s outside 15-120s range")
        except Exception:
            pass

    # Compute overall compliance
    checks = 0
    passed = 0.0

    if result.loudness:
        checks += 1
        lufs = result.loudness.get("integrated_lufs", -14)
        if abs(lufs - (-14)) <= 3:
            passed += 1

    if result.wpm:
        checks += 1
        if abs(result.wpm.get("deviation_pct", 0)) <= 15:
            passed += 1

    if result.volume_profile:
        checks += 1
        if result.volume_profile.get("ducking_detected", False):
            passed += 1

    if result.visual:
        checks += 1
        passed += result.visual.overall_visual_compliance

    result.overall_compliance = round(passed / max(1, checks), 2)
    return result


def _build_narration_mask(
    word_timestamps: list[dict],
    gap_threshold: float = 0.3,
) -> list[dict]:
    """Build merged speech intervals from word timestamps.

    Mirrors buildNarrationMask from audio-utils.ts.
    """
    if not word_timestamps:
        return []

    sorted_words = sorted(word_timestamps, key=lambda w: w.get("start", 0))
    intervals: list[dict] = []

    current = {"start": sorted_words[0].get("start", 0), "end": sorted_words[0].get("end", 0)}
    for w in sorted_words[1:]:
        w_start = w.get("start", 0)
        w_end = w.get("end", 0)
        if w_start <= current["end"] + gap_threshold:
            current["end"] = max(current["end"], w_end)
        else:
            intervals.append(dict(current))
            current = {"start": w_start, "end": w_end}
    intervals.append(dict(current))

    return intervals

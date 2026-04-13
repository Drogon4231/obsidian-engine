"""
Utilities for rendered output audit.

Extract frames and audio segments from rendered videos for perceptual analysis.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)


def extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame at timestamp. Returns True on success."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
                "-frames:v", "1", "-q:v", "2", str(output_path),
            ],
            capture_output=True, timeout=15,
        )
        return Path(output_path).exists() and Path(output_path).stat().st_size > 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def extract_frames_at_boundaries(
    video_path: str,
    scenes: list[dict],
    output_dir: str,
) -> list[dict]:
    """Extract frames at scene midpoints for visual quality check."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for i, scene in enumerate(scenes):
        mid = (scene.get("start_time", 0) + scene.get("end_time", 0)) / 2
        out = str(Path(output_dir) / f"scene_{i:02d}_mid.jpg")
        ok = extract_frame(video_path, mid, out)
        results.append({"scene": i, "timestamp": mid, "path": out, "extracted": ok})
    return results


def extract_audio_segment(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> bool:
    """Extract audio segment as WAV for analysis."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
                "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
                str(output_path),
            ],
            capture_output=True, timeout=30,
        )
        return Path(output_path).exists() and Path(output_path).stat().st_size > 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def extract_silence_beat_audio(
    video_path: str,
    scenes: list[dict],
    output_dir: str,
) -> list[dict]:
    """Extract audio around silence beat transitions for listening analysis."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for i, scene in enumerate(scenes):
        if not scene.get("intent_silence_beat"):
            continue
        start = scene.get("start_time", 0)
        end = scene.get("end_time", 0)
        seg_start = max(0, start - 2)
        seg_end = end + 2
        out = str(Path(output_dir) / f"silence_beat_{i:02d}.wav")
        ok = extract_audio_segment(video_path, seg_start, seg_end, out)
        results.append({
            "scene": i, "start": seg_start, "end": seg_end,
            "path": out, "extracted": ok,
        })
    return results


def run_rendered_audit(
    video_path: str,
    scenes: list[dict],
    output_dir: str,
) -> dict:
    """Full rendered output audit — extract frames + audio for review."""
    frames = extract_frames_at_boundaries(video_path, scenes, str(Path(output_dir) / "frames"))
    audio = extract_silence_beat_audio(video_path, scenes, str(Path(output_dir) / "audio"))
    return {
        "frames": frames,
        "silence_beat_audio": audio,
        "video_path": video_path,
    }

#!/usr/bin/env python3
"""
Agent 13 — Content Auditor (Post-Production QA)

12-pass audit system that downloads a published YouTube video and performs
deep quality analysis against the pipeline's actual quality contract:

  Pass  1: Technical specs (ffprobe baseline)
  Pass  2: Pipeline state loading (intent vs output comparison)
  Pass  3: Act structure & energy curve (hook→act1→act2→act3→ending)
  Pass  4: Scene duration variance & pacing rhythm
  Pass  5: Scene transition quality (type correctness at act boundaries)
  Pass  6: Visual continuity & art style consistency
  Pass  7: Caption sync, grouping & styling compliance
  Pass  8: Voice modulation by narrative position
  Pass  9: Audio mixing (music ducking, act envelope, SFX, room tone)
  Pass 10: Narrative quality (re-hooks, breathing room, reflection beat, POV)
  Pass 11: YouTube metadata & SEO compliance
  Pass 12: Master assessment (synthesizes all passes against quality contract)

Usage:
  python agents/13_content_auditor.py --video-id <YOUTUBE_ID>
  python agents/13_content_auditor.py --url <YOUTUBE_URL>
  python agents/13_content_auditor.py --latest
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.claude_client import client as anthropic_client, SONNET
from core.agent_wrapper import call_agent

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"


# ═══════════════════════════════════════════════════════════════════════════════
#  QUALITY CONTRACT — The pipeline's promises (from the 40-item plan)
# ═══════════════════════════════════════════════════════════════════════════════

# Act boundaries (fraction of total duration)
ACT_BOUNDARIES = {
    "hook":   (0.00, 0.07),
    "act1":   (0.07, 0.28),
    "act2":   (0.28, 0.67),
    "act3":   (0.67, 0.90),
    "ending": (0.90, 1.00),
}

# Target WPM by narrative position (documentary pacing: 130 wpm base)
TARGET_WPM = {
    "hook":   145,   # punchy, grabs attention
    "act1":   135,   # measured exposition
    "act2":   140,   # building tension
    "act3":   125,   # slower for revelations
    "ending": 120,   # reflective close
}

# Music ducking levels (from audio-utils.ts)
EXPECTED_DUCKING = {
    "speech_primary":  0.13,
    "silence_primary": 0.28,
    "speech_secondary": 0.10,
    "silence_secondary": 0.22,
}

# Music volume envelope by act (from ObsidianVideo.tsx)
ACT_VOLUME_ENVELOPE = {
    "act1":   0.90,  # subdued
    "act2":   1.10,  # tension rising
    "act3":   0.75,  # narration carries
    "ending": 1.15,  # swell for close
}

# Caption constraints (from Captions.tsx)
CAPTION_MAX_WORDS_PER_GROUP = 6
CAPTION_COMFORTABLE_WPS = (2.0, 3.5)
CAPTION_FAST_WPS = 4.0
CAPTION_UNREADABLE_WPS = 5.5

# Scene constraints (from pipeline_config.py)
MAX_SCENE_SECONDS = 12.0
MIN_SCENES = 5
SCENE_WORDS_PER_SCENE = 60  # target_scenes = word_count // 60

# Script quality thresholds (from 04b_script_doctor.py)
SCRIPT_APPROVAL_THRESHOLD = 7.0
SCRIPT_DIMENSIONS = [
    "hook_strength", "emotional_pacing", "personality",
    "pov_shifts", "voice_consistency", "factual_grounding", "emotional_arc",
]

# Retention danger zones (fraction of video)
RETENTION_DANGER_ZONES = [0.05, 0.25, 0.50, 0.75]

# Voice settings (from pipeline_config.py)
NARRATOR_BASE_SPEED = 0.88
NARRATOR_STABILITY = 0.38


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _check_tool(name: str) -> bool:
    try:
        subprocess.run([name, "--version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_youtube_client_safe():
    try:
        import importlib
        uploader = importlib.import_module("agents.11_youtube_uploader")
        creds = uploader.get_credentials()
        from googleapiclient.discovery import build
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"[Auditor] YouTube API unavailable: {e}")
        return None


def _ts_to_seconds(ts: str) -> float:
    """Convert SRT timestamp '00:01:23,456' to seconds."""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


def _encode_frame(path: Path) -> str:
    """Base64-encode an image file."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _extract_audio(video_path: Path, work_dir: Path, name: str = "audio") -> Path | None:
    """Extract mono 16kHz WAV from video."""
    audio_path = work_dir / f"{name}.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return audio_path if r.returncode == 0 and audio_path.exists() else None


def _get_volume_stats(audio_path: Path) -> dict:
    """Get volume stats for an audio file."""
    cmd = ["ffmpeg", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    stats = {}
    for line in r.stderr.splitlines():
        for key in ["mean_volume", "max_volume"]:
            m = re.search(rf"{key}:\s*(-?\d+\.?\d*)", line)
            if m:
                stats[key] = float(m.group(1))
    return stats


def _extract_frame(video_path: Path, work_dir: Path, ts: float, name: str) -> Path | None:
    """Extract a single frame at timestamp."""
    out = work_dir / f"{name}.jpg"
    cmd = ["ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
           "-frames:v", "1", "-q:v", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=15)
    return out if r.returncode == 0 and out.exists() else None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 0: DOWNLOAD VIDEO + CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def download_video(video_id: str, work_dir: Path) -> Path | None:
    if not _check_tool("yt-dlp"):
        print("[Auditor] yt-dlp not found — brew install yt-dlp")
        return None

    url = f"https://www.youtube.com/watch?v={video_id}"
    out_template = str(work_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", out_template,
        "--no-playlist",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--convert-subs", "srt",
        url,
    ]

    print(f"[Auditor] Downloading {video_id}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[Auditor] yt-dlp failed: {result.stderr[:500]}")
        return None

    for ext in ["mp4", "mkv", "webm"]:
        candidate = work_dir / f"{video_id}.{ext}"
        if candidate.exists():
            mb = candidate.stat().st_size / 1024 / 1024
            print(f"[Auditor] Downloaded: {candidate.name} ({mb:.1f} MB)")
            return candidate

    for f in work_dir.iterdir():
        if f.suffix in (".mp4", ".mkv", ".webm") and video_id in f.name:
            return f
    return None


def parse_srt_with_timestamps(video_id: str, work_dir: Path) -> list[dict]:
    """Parse SRT into list of {start_s, end_s, text} with rolling-window dedup."""
    srt_path = None
    for pattern in [f"{video_id}.en.srt", f"{video_id}.en.auto.srt"]:
        candidate = work_dir / pattern
        if candidate.exists():
            srt_path = candidate
            break
    if not srt_path:
        for f in work_dir.iterdir():
            if f.suffix == ".srt":
                srt_path = f
                break
    if not srt_path:
        return []

    raw = srt_path.read_text(encoding="utf-8", errors="replace")
    entries = []
    blocks = re.split(r"\n\s*\n", raw.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        ts_match = None
        ts_line_idx = -1
        for li, line in enumerate(lines):
            ts_match = re.match(
                r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})", line
            )
            if ts_match:
                ts_line_idx = li
                break
        if not ts_match:
            continue
        text_lines = lines[ts_line_idx + 1:]
        text = " ".join(re.sub(r"<[^>]+>", "", line) for line in text_lines).strip()
        if not text:
            continue
        entries.append({
            "start_s": _ts_to_seconds(ts_match.group(1)),
            "end_s": _ts_to_seconds(ts_match.group(2)),
            "text": text,
        })

    # YouTube auto-subs rolling window deduplication
    if len(entries) > 1:
        deduped = [entries[0]]
        for e in entries[1:]:
            prev = deduped[-1]
            prev_text = prev["text"].lower().strip()
            curr_text = e["text"].lower().strip()

            if curr_text.startswith(prev_text[:min(len(prev_text), 30)]):
                deduped[-1] = e
                continue

            prev_words = set(prev_text.split())
            curr_words = set(curr_text.split())
            if prev_words and curr_words:
                overlap = len(prev_words & curr_words) / max(len(prev_words), len(curr_words))
                if overlap > 0.6:
                    if len(e["text"]) >= len(prev["text"]):
                        deduped[-1] = e
                    continue

            if prev_text in curr_text or curr_text in prev_text:
                if len(e["text"]) >= len(prev["text"]):
                    deduped[-1] = e
                continue

            deduped.append(e)
        entries = deduped

    return entries


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 1: TECHNICAL SPECS
# ═══════════════════════════════════════════════════════════════════════════════

def pass_technical(video_path: Path) -> dict:
    if not _check_tool("ffprobe"):
        return {"error": "ffprobe not found"}

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return {}

    data = json.loads(result.stdout)
    info = {}
    fmt = data.get("format", {})
    info["duration_s"] = float(fmt.get("duration", 0))
    info["size_mb"] = round(int(fmt.get("size", 0)) / (1024 * 1024), 1)
    info["bitrate_kbps"] = round(int(fmt.get("bit_rate", 0)) / 1000, 1)
    info["format"] = fmt.get("format_long_name", "")

    for stream in data.get("streams", []):
        ct = stream.get("codec_type")
        if ct == "video":
            info["video_codec"] = stream.get("codec_name", "")
            info["width"] = stream.get("width", 0)
            info["height"] = stream.get("height", 0)
            fr = stream.get("r_frame_rate", "0/1")
            try:
                num, den = fr.split("/")
                info["fps"] = round(int(num) / max(int(den), 1), 2)
            except Exception:
                info["fps"] = 0
            br = stream.get("bit_rate")
            info["video_bitrate_kbps"] = round(int(br) / 1000, 1) if br else None
        elif ct == "audio":
            info["audio_codec"] = stream.get("codec_name", "")
            info["audio_sample_rate"] = stream.get("sample_rate", "")
            info["audio_channels"] = stream.get("channels", 0)
            br = stream.get("bit_rate")
            info["audio_bitrate_kbps"] = round(int(br) / 1000, 1) if br else None

    # Quality checks against pipeline contract
    issues = []
    if info.get("width", 0) < 1920 or info.get("height", 0) < 1080:
        issues.append(f"Resolution {info.get('width')}x{info.get('height')} below 1080p target")
    if info.get("fps", 0) > 0 and abs(info["fps"] - 30) > 2:
        issues.append(f"FPS {info['fps']} deviates from 30fps target")
    if info.get("duration_s", 0) < 300:
        issues.append(f"Duration {info['duration_s']:.0f}s below MIN_AUDIO_DURATION (300s)")
    if info.get("duration_s", 0) > 1200:
        issues.append(f"Duration {info['duration_s']:.0f}s above MAX_AUDIO_DURATION (1200s)")

    info["contract_issues"] = issues
    return info


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 2: PIPELINE STATE LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def pass_load_state(video_id: str) -> dict:
    """Find and load pipeline state file for this video."""
    state = {
        "found": False,
        "script_doctor_scores": None,
        "hook_scores": None,
        "compliance": None,
        "scene_intent_data": None,
        "visual_bible": None,
        "script_text": None,
        "scene_count": None,
        "fact_verification": None,
        "seo_data": None,
        "voice_settings": None,
        "qa_results": None,
    }

    # Search for state files — match by video_id in YouTube upload data
    state_files = sorted(OUTPUTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    best_match = None
    for sf in state_files:
        if sf.name.startswith("audit_") or sf.name.startswith("diagnostic"):
            continue
        try:
            data = json.loads(sf.read_text())
        except Exception:
            continue

        # Check if this state file's YouTube upload matches our video
        yt_upload = data.get("youtube_upload", {})
        if yt_upload.get("video_id") == video_id:
            best_match = data
            state["state_file"] = sf.name
            break

        # Also check if video_id appears anywhere in the data
        raw = sf.read_text()
        if video_id in raw:
            best_match = data
            state["state_file"] = sf.name
            break

    if not best_match:
        # Try the most recent non-audit state file as fallback
        for sf in state_files:
            if sf.name.startswith("audit_") or sf.name.startswith("diagnostic"):
                continue
            if sf.name.startswith("prompt_manifest") or sf.name.startswith("stage_"):
                continue
            try:
                data = json.loads(sf.read_text())
                if "script" in data or "scenes" in data:
                    best_match = data
                    state["state_file"] = sf.name
                    state["match_type"] = "latest_state_file"
                    break
            except Exception:
                continue

    if not best_match:
        print("[Auditor] No pipeline state file found — auditing without intent data")
        return state

    state["found"] = True
    print(f"[Auditor] Loaded state: {state.get('state_file', '?')}")

    # Extract quality data
    state["script_doctor_scores"] = best_match.get("script_doctor_scores")
    state["hook_scores"] = best_match.get("hook_scores")
    state["compliance"] = best_match.get("compliance")
    state["fact_verification"] = best_match.get("fact_verification", {}).get("verdict")
    state["qa_results"] = {
        "qa_tier1": best_match.get("qa_tier1"),
        "qa_tier2": best_match.get("qa_tier2"),
        "qa_tier2_sync_pct": best_match.get("qa_tier2_sync_pct"),
    }

    # Extract script
    script_data = best_match.get("script", {})
    if isinstance(script_data, dict):
        state["script_text"] = script_data.get("full_script") or script_data.get("narration")
        state["script_word_count"] = len(state["script_text"].split()) if state["script_text"] else None

    # Extract scenes
    scenes = best_match.get("scenes", best_match.get("scene_breakdown", []))
    if isinstance(scenes, list):
        state["scene_count"] = len(scenes)
        state["scene_intent_data"] = []
        for s in scenes:
            state["scene_intent_data"].append({
                "scene_id": s.get("scene_id"),
                "mood": s.get("mood"),
                "narrative_function": s.get("narrative_function"),
                "narrative_position": s.get("narrative_position"),
                "is_reveal_moment": s.get("is_reveal_moment", False),
                "is_breathing_room": s.get("is_breathing_room", False),
                "duration_seconds": s.get("duration_seconds"),
                "visual_type": s.get("visual_type"),
                "visual_treatment": s.get("visual_treatment"),
            })

    # Extract visual bible
    state["visual_bible"] = best_match.get("visual_bible", best_match.get("visual_continuity"))

    # Extract SEO
    state["seo_data"] = best_match.get("seo")

    # Extract voice settings
    state["voice_settings"] = best_match.get("voice_settings")

    # Summarize what we have
    available = [k for k, v in state.items() if v and k not in ("found", "state_file", "match_type")]
    print(f"  State data available: {', '.join(available)}")

    return state


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 3: ACT STRUCTURE & ENERGY CURVE
# ═══════════════════════════════════════════════════════════════════════════════

def pass_act_structure(video_path: Path, srt_entries: list[dict],
                       duration_s: float, work_dir: Path) -> dict:
    """Verify the video follows a proper act structure with energy progression."""
    if not srt_entries or duration_s <= 0:
        return {"error": "No caption data for act analysis"}

    acts = {}
    for act_name, (start_frac, end_frac) in ACT_BOUNDARIES.items():
        start_s = duration_s * start_frac
        end_s = duration_s * end_frac

        # Count words in this act
        words_in_act = 0
        entries_in_act = 0
        for e in srt_entries:
            if e["start_s"] >= start_s and e["start_s"] < end_s:
                words_in_act += len(e["text"].split())
                entries_in_act += 1

        act_duration = end_s - start_s
        wpm = (words_in_act / act_duration) * 60 if act_duration > 0 else 0

        acts[act_name] = {
            "start_s": round(start_s, 1),
            "end_s": round(end_s, 1),
            "duration_s": round(act_duration, 1),
            "word_count": words_in_act,
            "wpm": round(wpm),
            "target_wpm": TARGET_WPM.get(act_name, 130),
            "wpm_deviation": round(abs(wpm - TARGET_WPM.get(act_name, 130))),
            "caption_entries": entries_in_act,
        }

    # Analyze energy curve using audio volume across acts
    energy_curve = []
    if _check_tool("ffmpeg"):
        for act_name, act_data in acts.items():
            clip_path = work_dir / f"act_{act_name}.wav"
            mid = (act_data["start_s"] + act_data["end_s"]) / 2
            cmd = [
                "ffmpeg", "-y", "-ss", str(max(0, mid - 5)),
                "-i", str(video_path), "-t", "10",
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(clip_path),
            ]
            subprocess.run(cmd, capture_output=True, timeout=15)
            if clip_path.exists():
                stats = _get_volume_stats(clip_path)
                energy_curve.append({
                    "act": act_name,
                    "mean_volume_db": stats.get("mean_volume"),
                    "max_volume_db": stats.get("max_volume"),
                })
                clip_path.unlink()

    # Check for proper pacing progression
    issues = []
    wpm_values = {name: data["wpm"] for name, data in acts.items()}

    # Hook should be faster-paced
    if wpm_values.get("hook", 0) < wpm_values.get("act1", 0) * 0.9:
        issues.append("Hook pacing slower than Act 1 — should be punchier")

    # Act 3 should slow down for revelations
    if wpm_values.get("act3", 0) > wpm_values.get("act2", 0) * 1.1:
        issues.append("Act 3 faster than Act 2 — should slow for revelations")

    # Ending should be slowest
    if wpm_values.get("ending", 0) > 160:
        issues.append(f"Ending too fast ({wpm_values.get('ending', 0)} WPM) — should be reflective")

    # Overall WPM check (documentary standard: 130 WPM)
    total_words = sum(d["word_count"] for d in acts.values())
    overall_wpm = (total_words / duration_s) * 60
    if overall_wpm > 170:
        issues.append(f"Overall pacing {overall_wpm:.0f} WPM — too fast for documentary (target: 130)")
    elif overall_wpm < 100:
        issues.append(f"Overall pacing {overall_wpm:.0f} WPM — too slow, may lose audience")

    return {
        "acts": acts,
        "energy_curve": energy_curve,
        "overall_wpm": round(overall_wpm),
        "target_overall_wpm": 130,
        "issues": issues,
        "act_structure_score": max(1, 10 - len(issues) * 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 4: SCENE DURATION VARIANCE & PACING RHYTHM
# ═══════════════════════════════════════════════════════════════════════════════

def pass_scene_pacing(video_path: Path, duration_s: float, work_dir: Path) -> dict:
    """Check scene durations vary properly (not uniform) and match act pacing."""
    if not _check_tool("ffmpeg"):
        return {"error": "ffmpeg not found"}

    # Multi-threshold scene detection (Ken Burns needs low thresholds)
    scene_times = []
    used_threshold = None
    for threshold in [0.15, 0.08, 0.04, 0.02]:
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        timestamps = []
        for line in result.stderr.splitlines():
            match = re.search(r"pts_time:(\d+\.?\d*)", line)
            if match:
                timestamps.append(float(match.group(1)))

        if len(timestamps) >= 5:
            scene_times = timestamps
            used_threshold = threshold
            break

    # Fallback: estimate from crossfade intervals
    if len(scene_times) < 5 and duration_s > 0:
        est_count = max(5, int(duration_s // 20))
        scene_times = [i * (duration_s / est_count) for i in range(1, est_count)]
        used_threshold = "estimated"

    print(f"[Auditor] Detected {len(scene_times)} scene changes (threshold={used_threshold})")

    # Calculate scene durations
    boundaries = [0.0] + scene_times + [duration_s]
    scene_durations = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]

    # Variance analysis
    if scene_durations:
        avg_dur = sum(scene_durations) / len(scene_durations)
        std_dev = (sum((d - avg_dur) ** 2 for d in scene_durations) / len(scene_durations)) ** 0.5
        coeff_variation = std_dev / avg_dur if avg_dur > 0 else 0
    else:
        avg_dur = std_dev = coeff_variation = 0

    issues = []

    # Check for uniform scene durations (bad — should vary with content)
    if coeff_variation < 0.15 and len(scene_durations) > 5:
        issues.append(
            f"Scene durations too uniform (CV={coeff_variation:.2f}). "
            "Word-count-weighted scenes should vary. Feels robotic."
        )

    # Check for scenes exceeding max
    long_scenes = [d for d in scene_durations if d > MAX_SCENE_SECONDS]
    if long_scenes:
        issues.append(f"{len(long_scenes)} scenes exceed {MAX_SCENE_SECONDS}s cap (max: {max(long_scenes):.1f}s)")

    # Check pacing rhythm by act
    act_pacing = {}
    for act_name, (start_frac, end_frac) in ACT_BOUNDARIES.items():
        start_s = duration_s * start_frac
        end_s = duration_s * end_frac
        act_scenes = [d for i, d in enumerate(scene_durations)
                      if boundaries[i] >= start_s and boundaries[i] < end_s]
        if act_scenes:
            act_pacing[act_name] = {
                "scene_count": len(act_scenes),
                "avg_duration_s": round(sum(act_scenes) / len(act_scenes), 1),
                "min_duration_s": round(min(act_scenes), 1),
                "max_duration_s": round(max(act_scenes), 1),
            }

    # Act 2 should have more frequent cuts (tension building)
    act2_avg = act_pacing.get("act2", {}).get("avg_duration_s", 0)
    act1_avg = act_pacing.get("act1", {}).get("avg_duration_s", 0)
    if act2_avg > 0 and act1_avg > 0 and act2_avg > act1_avg * 1.3:
        issues.append("Act 2 scenes slower than Act 1 — should build tension with quicker cuts")

    return {
        "scene_count": len(scene_durations),
        "detection_threshold": used_threshold,
        "scene_times": [round(t, 2) for t in scene_times[:50]],
        "avg_scene_duration_s": round(avg_dur, 1),
        "std_dev_s": round(std_dev, 1),
        "coefficient_of_variation": round(coeff_variation, 2),
        "duration_range": {
            "min_s": round(min(scene_durations), 1) if scene_durations else 0,
            "max_s": round(max(scene_durations), 1) if scene_durations else 0,
        },
        "long_scenes_over_12s": len(long_scenes),
        "act_pacing": act_pacing,
        "issues": issues,
        "pacing_score": max(1, 10 - len(issues) * 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 5: SCENE TRANSITION QUALITY
# ═══════════════════════════════════════════════════════════════════════════════

def pass_transitions(video_path: Path, scene_times: list[float],
                     duration_s: float, work_dir: Path) -> dict:
    """Analyze transition quality — check type correctness at act boundaries."""
    if not _check_tool("ffmpeg") or not scene_times:
        return {"error": "No scene data for transition analysis"}

    # Identify which transitions should be act transitions vs normal
    act_boundary_times = {
        name: duration_s * frac
        for name, (frac, _) in ACT_BOUNDARIES.items()
        if frac > 0  # skip hook start
    }

    # Sample up to 12 transitions (mix of act boundaries + random)
    sampled_indices = []
    # Prioritize transitions near act boundaries
    for bt in act_boundary_times.values():
        closest_idx = min(range(len(scene_times)),
                         key=lambda i: abs(scene_times[i] - bt),
                         default=None)
        if closest_idx is not None and closest_idx not in sampled_indices:
            sampled_indices.append(closest_idx)

    # Fill remaining with evenly distributed transitions
    remaining = 10 - len(sampled_indices)
    if remaining > 0 and scene_times:
        step = max(1, len(scene_times) // remaining)
        for i in range(0, len(scene_times), step):
            if i not in sampled_indices and len(sampled_indices) < 12:
                sampled_indices.append(i)

    sampled_indices.sort()

    # Extract frame pairs
    pairs = []
    for idx in sampled_indices:
        ts = scene_times[idx]
        before_path = _extract_frame(video_path, work_dir, max(0, ts - 0.15), f"trans_{idx:02d}_before")
        after_path = _extract_frame(video_path, work_dir, ts + 0.15, f"trans_{idx:02d}_after")
        if before_path and after_path:
            # Determine expected transition type
            is_act_boundary = False
            nearest_act = ""
            for act_name, bt in act_boundary_times.items():
                if abs(ts - bt) < duration_s * 0.03:  # within 3% of act boundary
                    is_act_boundary = True
                    nearest_act = act_name
                    break

            pairs.append({
                "index": idx,
                "timestamp": round(ts, 2),
                "before": before_path,
                "after": after_path,
                "expected_type": "act" if is_act_boundary else "normal",
                "near_act": nearest_act,
                "video_position_pct": round(ts / duration_s * 100, 1),
            })

    print(f"[Auditor] Extracted {len(pairs)} transition pairs for analysis")

    if not pairs:
        return {"error": "No transition pairs extracted"}

    # Send to Claude vision — up to 6 pairs (12 images)
    selected = pairs[:6]
    content_blocks = []
    for pair in selected:
        for key in ["before", "after"]:
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg",
                           "data": _encode_frame(pair[key])},
            })

    pair_descriptions = "\n".join(
        f"Pair {i}: at {p['timestamp']:.1f}s ({p['video_position_pct']}% through video), "
        f"expected type: {p['expected_type']}"
        + (f" (near {p['near_act']} boundary)" if p['near_act'] else "")
        for i, p in enumerate(selected)
    )

    content_blocks.append({
        "type": "text",
        "text": f"""You are a senior video editor reviewing scene transitions in a dark history documentary.

I'm showing you {len(selected)} transition pairs. Each pair is two consecutive frames: BEFORE and AFTER a scene cut.

TRANSITION LOCATIONS:
{pair_descriptions}

The pipeline uses three transition types:
- NORMAL: Quick crossfade (0.4s, 35% opacity dip) — for standard scene changes
- ACT: Slow crossfade (0.8s, 70% opacity dip) — for major act boundaries
- REVEAL: Similar to act but marks dramatic reveal moments

Evaluate each transition for:
1. Smoothness — is it jarring or professional?
2. Color continuity — compatible palettes between scenes?
3. Transition type appropriateness — does the transition FEEL like the right type for its position?
4. Visual logic — is there a narrative connection between scenes?

Return ONLY valid JSON:
{{
    "transition_quality_score": <1-10>,
    "transitions": [
        {{
            "pair_index": <0-based>,
            "timestamp_s": <float>,
            "smoothness": "<smooth/acceptable/jarring/disorienting>",
            "color_continuity": "<matching/compatible/clashing>",
            "type_appropriate": "<yes/no — does it feel like the expected type?>",
            "visual_logic": "<connected/neutral/disconnected>",
            "note": "<specific observation>"
        }}
    ],
    "act_boundary_transitions_quality": "<specifically assess transitions at act boundaries>",
    "worst_transition": "<describe the worst transition and why>",
    "consistency_assessment": "<is transition style consistent throughout or erratic?>",
    "recommendations": ["<specific improvements>"]
}}""",
    })

    print(f"[Auditor] Analyzing {len(selected)} transitions with Claude vision...")
    try:
        response = anthropic_client.messages.create(
            model=SONNET, max_tokens=3000,
            messages=[{"role": "user", "content": content_blocks}],
        )
        try:
            from clients.claude_client import track_usage
            track_usage(SONNET, response.usage)
        except Exception:
            pass
        raw = response.content[0].text.strip()
        clean = re.sub(r"^```(?:json)?\s*", "", raw)
        clean = re.sub(r"\s*```$", "", clean).strip()
        result = json.loads(clean, strict=False)
        result["pairs_analyzed"] = len(selected)
        result["total_scenes"] = len(scene_times)
        return result
    except Exception as e:
        return {"error": str(e), "pairs_analyzed": len(selected)}


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 6: VISUAL CONTINUITY & ART STYLE
# ═══════════════════════════════════════════════════════════════════════════════

def pass_visual_continuity(video_path: Path, duration_s: float,
                           work_dir: Path, yt_title: str,
                           visual_bible: dict | None) -> dict:
    """Check visual consistency: art style, color palette, treatment variety."""
    if not _check_tool("ffmpeg"):
        return {"error": "ffmpeg not found"}

    # Sample 12 frames across the video (more than before, need continuity data)
    timestamps = []
    fixed = [2.0, 10.0, 30.0]  # Hook, early, intro
    step = duration_s / 10
    dynamic = [step * i for i in range(1, 10)]
    dynamic.append(max(0, duration_s - 8))
    timestamps = sorted(set(t for t in fixed + dynamic if 0 < t < duration_s))[:12]

    frames = []
    for i, ts in enumerate(timestamps):
        path = _extract_frame(video_path, work_dir, ts, f"vis_{i:02d}_{ts:.0f}s")
        if path:
            frames.append({"path": path, "timestamp": ts})

    if len(frames) < 4:
        return {"error": f"Only {len(frames)} frames extracted"}

    # Send to Claude vision for continuity analysis
    selected = frames[:10]
    content_blocks = []
    for f in selected:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": _encode_frame(f["path"])},
        })

    bible_context = ""
    if visual_bible:
        bible_context = f"""
INTENDED VISUAL BIBLE (from pipeline):
- Art style: {visual_bible.get('art_style', 'N/A')}
- Color palette: {visual_bible.get('color_palette', 'N/A')}
- Recurring motifs: {visual_bible.get('recurring_motifs', 'N/A')}

Compare the actual frames against this intended style."""

    content_blocks.append({
        "type": "text",
        "text": f"""You are a Visual Continuity Director reviewing {len(selected)} chronological frames from a dark history documentary titled "{yt_title}".
{bible_context}

Evaluate the VISUAL CONTINUITY — whether these frames look like they belong to the SAME video with a coherent visual identity:

Return ONLY valid JSON:
{{
    "continuity_score": <1-10>,
    "art_style": {{
        "consistency": "<consistent/mostly_consistent/inconsistent/chaotic>",
        "detected_style": "<describe the dominant art style across frames>",
        "style_breaks": ["<list any frames that break from the dominant style>"],
        "bible_adherence": "<if visual bible provided: how well do frames match?>",
    }},
    "color_palette": {{
        "consistency": "<unified/mostly_unified/fragmented>",
        "dominant_tones": ["<list 3-4 dominant color tones>"],
        "clashing_frames": ["<list frames with jarring color shifts>"],
    }},
    "visual_variety": {{
        "score": <1-10>,
        "treatment_types_observed": ["<list: close_portrait, wide_establishing, artifact_detail, etc.>"],
        "monotony_risk": "<high/medium/low — do scenes look too samey?>",
        "variety_notes": "<observation about visual diversity>",
    }},
    "composition_quality": {{
        "score": <1-10>,
        "framing": "<professional/adequate/poor>",
        "ai_artifacts": ["<visible AI generation issues: faces, text, anachronisms>"],
        "text_overlay_quality": "<if text overlays visible: readable, relevant, well-positioned?>",
    }},
    "narrative_visual_arc": {{
        "score": <1-10>,
        "hook_impact": "<does the opening frame grab attention?>",
        "emotional_progression": "<can you see mood shifting across the frames?>",
        "climax_visual": "<does the visual intensity peak in the right place (67-90% through)?>",
    }},
    "caption_visibility": {{
        "score": <1-10>,
        "readability": "<font size, contrast, positioning assessment>",
        "issues": ["<caption problems visible in frames>"],
    }},
    "critical_issues": ["<only genuinely serious visual problems>"],
    "overall_assessment": "<4-5 sentence honest assessment of visual quality>"
}}""",
    })

    print(f"[Auditor] Analyzing {len(selected)} frames for visual continuity...")
    try:
        response = anthropic_client.messages.create(
            model=SONNET, max_tokens=4000,
            messages=[{"role": "user", "content": content_blocks}],
        )
        try:
            from clients.claude_client import track_usage
            track_usage(SONNET, response.usage)
        except Exception:
            pass
        raw = response.content[0].text.strip()
        clean = re.sub(r"^```(?:json)?\s*", "", raw)
        clean = re.sub(r"\s*```$", "", clean).strip()
        result = json.loads(clean, strict=False)
        result["frames_analyzed"] = len(selected)
        return result
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 7: CAPTION SYNC, GROUPING & STYLING
# ═══════════════════════════════════════════════════════════════════════════════

def pass_captions(video_path: Path, srt_entries: list[dict], work_dir: Path) -> dict:
    """Check caption timing, word grouping, and styling against pipeline contract."""
    if not srt_entries:
        return {"error": "No caption data"}

    issues = []
    caption_speeds = []
    grouping_issues = []

    prev_end = 0.0
    for i, entry in enumerate(srt_entries):
        dur = entry["end_s"] - entry["start_s"]
        if dur <= 0:
            continue

        words = entry["text"].split()
        word_count = len(words)
        wps = word_count / dur

        caption_speeds.append({
            "index": i,
            "start_s": round(entry["start_s"], 2),
            "end_s": round(entry["end_s"], 2),
            "words": word_count,
            "duration_s": round(dur, 2),
            "wps": round(wps, 2),
        })

        # Contract: comfortable reading 2.0-3.5 wps
        if wps > CAPTION_UNREADABLE_WPS:
            issues.append({
                "type": "unreadable_speed",
                "severity": "critical",
                "at_s": round(entry["start_s"], 1),
                "wps": round(wps, 2),
                "text": entry["text"][:80],
                "detail": f"{word_count} words in {dur:.1f}s = {wps:.1f} wps (max readable: {CAPTION_UNREADABLE_WPS})",
            })
        elif wps > CAPTION_FAST_WPS:
            issues.append({
                "type": "fast_caption",
                "severity": "high",
                "at_s": round(entry["start_s"], 1),
                "wps": round(wps, 2),
                "text": entry["text"][:80],
            })

        # Contract: max 6 words per caption group
        if word_count > CAPTION_MAX_WORDS_PER_GROUP + 2:  # some tolerance for auto-subs
            grouping_issues.append({
                "at_s": round(entry["start_s"], 1),
                "words": word_count,
                "text": entry["text"][:80],
            })

        # Flash detection (< 0.8s with 3+ words)
        if dur < 0.8 and word_count > 2:
            issues.append({
                "type": "caption_flash",
                "severity": "critical",
                "at_s": round(entry["start_s"], 1),
                "duration_s": round(dur, 2),
                "text": entry["text"][:80],
            })

        # Overlap detection
        gap = entry["start_s"] - prev_end
        if gap < -0.5:
            issues.append({
                "type": "caption_overlap",
                "severity": "medium",
                "at_s": round(entry["start_s"], 1),
                "overlap_s": round(abs(gap), 2),
            })

        prev_end = entry["end_s"]

    # Stats
    wps_values = [cs["wps"] for cs in caption_speeds]
    avg_wps = sum(wps_values) / max(len(wps_values), 1)
    max_wps = max(wps_values) if wps_values else 0

    # Audio sync spot-checks at fast captions
    sync_checks = []
    fast_issues = [i for i in issues if i["type"] in ("unreadable_speed", "fast_caption")][:5]
    if _check_tool("ffmpeg") and fast_issues:
        audio_path = _extract_audio(video_path, work_dir, "sync_check")
        if audio_path:
            for fi in fast_issues:
                start = fi["at_s"]
                clip_path = work_dir / f"sync_{start:.0f}.wav"
                cmd = [
                    "ffmpeg", "-y", "-ss", str(max(0, start - 0.5)),
                    "-i", str(audio_path), "-t", "4",
                    "-acodec", "pcm_s16le", str(clip_path),
                ]
                subprocess.run(cmd, capture_output=True, timeout=15)
                if clip_path.exists():
                    stats = _get_volume_stats(clip_path)
                    sync_checks.append({
                        "at_s": start,
                        "wps": fi["wps"],
                        "mean_volume_db": stats.get("mean_volume"),
                        "speech_detected": stats.get("mean_volume", -99) > -35,
                    })
                    clip_path.unlink()
            audio_path.unlink()

    speed_dist = {
        "comfortable_under_3.5wps": sum(1 for w in wps_values if w <= 3.5),
        "fast_3.5_to_5wps": sum(1 for w in wps_values if 3.5 < w <= 5.0),
        "unreadable_over_5wps": sum(1 for w in wps_values if w > 5.0),
    }

    # Score: start at 10, deduct for issues
    critical_count = sum(1 for i in issues if i["severity"] == "critical")
    high_count = sum(1 for i in issues if i["severity"] == "high")
    score = max(1, 10 - critical_count * 2 - high_count)

    return {
        "total_captions": len(srt_entries),
        "avg_wps": round(avg_wps, 2),
        "max_wps": round(max_wps, 2),
        "contract_comfortable_range": f"{CAPTION_COMFORTABLE_WPS[0]}-{CAPTION_COMFORTABLE_WPS[1]} wps",
        "speed_distribution": speed_dist,
        "grouping_violations": len(grouping_issues),
        "sync_checks": sync_checks,
        "issues": issues[:20],
        "worst_offenders": sorted(caption_speeds, key=lambda x: -x["wps"])[:5],
        "caption_score": score,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 8: VOICE MODULATION BY NARRATIVE POSITION
# ═══════════════════════════════════════════════════════════════════════════════

def pass_voice_modulation(video_path: Path, srt_entries: list[dict],
                          duration_s: float, work_dir: Path,
                          voice_settings: dict | None) -> dict:
    """Check voice quality varies by act — not monotone throughout."""
    if not _check_tool("ffmpeg") or duration_s <= 0:
        return {"error": "Cannot analyze voice"}

    audio_path = _extract_audio(video_path, work_dir, "voice_mod")
    if not audio_path:
        return {"error": "Audio extraction failed"}

    # Get overall loudness
    loud_cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "loudnorm=print_format=json", "-f", "null", "-",
    ]
    loud_result = subprocess.run(loud_cmd, capture_output=True, text=True, timeout=60)
    loudness_info = {}
    json_match = re.search(r"\{[^{}]+\}", loud_result.stderr)
    if json_match:
        try:
            loudness_info = json.loads(json_match.group())
        except Exception:
            pass

    # Analyze voice at 8 points across the video (covers all acts)
    sample_positions = [
        ("hook_start", 0.03),
        ("hook_end", 0.06),
        ("act1_mid", 0.17),
        ("act2_early", 0.35),
        ("act2_mid", 0.48),
        ("act3_early", 0.72),
        ("act3_late", 0.85),
        ("ending", 0.95),
    ]

    voice_samples = []
    for label, frac in sample_positions:
        t = duration_s * frac
        clip_path = work_dir / f"voice_{label}.wav"
        cmd = [
            "ffmpeg", "-y", "-ss", str(max(0, t - 2)),
            "-i", str(audio_path), "-t", "4",
            "-acodec", "pcm_s16le", str(clip_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        if clip_path.exists():
            stats = _get_volume_stats(clip_path)
            # Also get WPM from captions in this window
            window_words = sum(
                len(e["text"].split()) for e in srt_entries
                if e["start_s"] >= t - 2 and e["start_s"] < t + 2
            )
            local_wpm = window_words * 15  # 4s window → multiply by 15 for WPM

            voice_samples.append({
                "position": label,
                "timestamp_s": round(t, 1),
                "mean_volume_db": stats.get("mean_volume"),
                "max_volume_db": stats.get("max_volume"),
                "local_wpm": local_wpm,
            })
            clip_path.unlink()

    # Detect silence gaps (potential breathing room or issues)
    silence_cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "silencedetect=noise=-35dB:d=1.0",
        "-f", "null", "-",
    ]
    silence_result = subprocess.run(silence_cmd, capture_output=True, text=True, timeout=60)

    silences = []
    current_start = None
    for line in silence_result.stderr.splitlines():
        start_match = re.search(r"silence_start:\s*(\d+\.?\d*)", line)
        end_match = re.search(r"silence_end:\s*(\d+\.?\d*)\s*\|\s*silence_duration:\s*(\d+\.?\d*)", line)
        if start_match:
            current_start = float(start_match.group(1))
        elif end_match and current_start is not None:
            silences.append({
                "start_s": round(current_start, 1),
                "end_s": round(float(end_match.group(1)), 1),
                "duration_s": round(float(end_match.group(2)), 1),
                "position_pct": round(current_start / duration_s * 100, 1),
            })
            current_start = None

    audio_path.unlink()

    # Analyze voice modulation issues
    issues = []
    volumes = [s["mean_volume_db"] for s in voice_samples if s["mean_volume_db"] is not None]
    vol_range = max(volumes) - min(volumes) if len(volumes) >= 2 else 0

    if vol_range < 3:
        issues.append("Voice volume is flat throughout — no dynamic range between acts")
    elif vol_range > 15:
        issues.append(f"Extreme volume inconsistency ({vol_range:.1f}dB range) — mastering issue")

    # Check WPM variation by position
    hook_samples = [s for s in voice_samples if "hook" in s["position"]]
    ending_samples = [s for s in voice_samples if "ending" in s["position"]]
    if hook_samples and ending_samples:
        hook_wpm = sum(s["local_wpm"] for s in hook_samples) / len(hook_samples)
        ending_wpm = sum(s["local_wpm"] for s in ending_samples) / len(ending_samples)
        if ending_wpm > hook_wpm * 1.1:
            issues.append(f"Ending faster ({ending_wpm:.0f} WPM) than hook ({hook_wpm:.0f} WPM) — should slow down")

    # Check for breathing room (silences in Act 3 after climax, 67-90%)
    act3_silences = [s for s in silences if 67 < s["position_pct"] < 90 and s["duration_s"] > 1.5]
    if not act3_silences:
        issues.append("No breathing room detected in Act 3 (67-90%) — needs contemplative pause after climax")

    # Check for reflection beat near ending
    reflection_silences = [s for s in silences if s["position_pct"] > 85 and s["duration_s"] > 2.0]
    if not reflection_silences:
        issues.append("No reflection beat near ending — needs moment of silence before conclusion")

    consistency = "consistent" if vol_range < 5 else "moderate_variation" if vol_range < 10 else "inconsistent"

    # Pacing by quarter (for backwards compatibility with reports)
    quarter_duration = duration_s / 4
    wpm_per_quarter = []
    for q in range(4):
        q_start = q * quarter_duration
        q_end = (q + 1) * quarter_duration
        words = sum(len(e["text"].split()) for e in srt_entries
                    if e["start_s"] >= q_start and e["start_s"] < q_end)
        wpm = (words / quarter_duration) * 60 if quarter_duration > 0 else 0
        wpm_per_quarter.append(round(wpm))

    return {
        "loudness": loudness_info,
        "voice_samples": voice_samples,
        "voice_consistency": consistency,
        "volume_range_db": round(vol_range, 1),
        "silence_count": len(silences),
        "silences_over_2s": [s for s in silences if s["duration_s"] > 2.0],
        "breathing_room_present": len(act3_silences) > 0,
        "reflection_beat_present": len(reflection_silences) > 0,
        "pacing_wpm_per_quarter": wpm_per_quarter,
        "issues": issues,
        "voice_score": max(1, 10 - len(issues) * 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 9: AUDIO MIXING (MUSIC DUCKING, ACT ENVELOPE, SFX)
# ═══════════════════════════════════════════════════════════════════════════════

def pass_audio_mixing(video_path: Path, srt_entries: list[dict],
                      duration_s: float, work_dir: Path) -> dict:
    """Check music ducking under narration, act volume envelope, room tone."""
    if not _check_tool("ffmpeg") or duration_s <= 0:
        return {"error": "Cannot analyze audio mixing"}

    # Extract stereo audio for mixing analysis
    stereo_path = work_dir / "stereo_mix.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
        str(stereo_path),
    ]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if not stereo_path.exists():
        return {"error": "Stereo extraction failed"}

    issues = []

    # Sample audio at points with speech vs points between captions
    speech_volumes = []
    gap_volumes = []

    # Find speech segments and gaps
    speech_points = []
    gap_points = []

    for i, e in enumerate(srt_entries):
        mid = (e["start_s"] + e["end_s"]) / 2
        speech_points.append(mid)
        if i + 1 < len(srt_entries):
            gap_start = e["end_s"]
            gap_end = srt_entries[i + 1]["start_s"]
            if gap_end - gap_start > 0.5:
                gap_points.append((gap_start + gap_end) / 2)

    # Sample up to 6 speech and 6 gap points
    import random
    random.seed(42)
    sampled_speech = random.sample(speech_points, min(6, len(speech_points))) if speech_points else []
    sampled_gaps = random.sample(gap_points, min(6, len(gap_points))) if gap_points else []

    for t in sampled_speech:
        clip_path = work_dir / f"speech_{t:.0f}.wav"
        cmd = [
            "ffmpeg", "-y", "-ss", str(max(0, t - 0.5)),
            "-i", str(stereo_path), "-t", "1",
            str(clip_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if clip_path.exists():
            stats = _get_volume_stats(clip_path)
            if stats.get("mean_volume") is not None:
                speech_volumes.append(stats["mean_volume"])
            clip_path.unlink()

    for t in sampled_gaps:
        clip_path = work_dir / f"gap_{t:.0f}.wav"
        cmd = [
            "ffmpeg", "-y", "-ss", str(max(0, t - 0.5)),
            "-i", str(stereo_path), "-t", "1",
            str(clip_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if clip_path.exists():
            stats = _get_volume_stats(clip_path)
            if stats.get("mean_volume") is not None:
                gap_volumes.append(stats["mean_volume"])
            clip_path.unlink()

    # Ducking analysis
    ducking_detected = False
    ducking_ratio = None
    if speech_volumes and gap_volumes:
        avg_speech_vol = sum(speech_volumes) / len(speech_volumes)
        avg_gap_vol = sum(gap_volumes) / len(gap_volumes)
        # During speech, music should be quieter (lower volume = more negative dB)
        # If gap volume is notably higher than speech volume, ducking is working
        vol_diff = avg_gap_vol - avg_speech_vol
        ducking_detected = vol_diff > 2  # at least 2dB difference
        ducking_ratio = round(vol_diff, 1)

        if not ducking_detected:
            issues.append(
                f"Music ducking not detected (speech avg: {avg_speech_vol:.1f}dB, "
                f"gap avg: {avg_gap_vol:.1f}dB, diff: {vol_diff:.1f}dB). "
                "Music should be 0.13× during speech, 0.28× during silence."
            )

    # Act volume envelope check
    act_volumes = {}
    for act_name, (start_frac, end_frac) in ACT_BOUNDARIES.items():
        mid = duration_s * (start_frac + end_frac) / 2
        clip_path = work_dir / f"act_vol_{act_name}.wav"
        cmd = [
            "ffmpeg", "-y", "-ss", str(max(0, mid - 3)),
            "-i", str(stereo_path), "-t", "6",
            str(clip_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if clip_path.exists():
            stats = _get_volume_stats(clip_path)
            act_volumes[act_name] = stats.get("mean_volume")
            clip_path.unlink()

    # Check envelope shape (Act3 should be quietest, ending should swell)
    if act_volumes.get("act3") and act_volumes.get("act2"):
        if act_volumes["act3"] > act_volumes["act2"]:
            issues.append("Act 3 louder than Act 2 — should be quieter for narration focus (0.75× envelope)")

    if act_volumes.get("ending") and act_volumes.get("act3"):
        if act_volumes["ending"] < act_volumes["act3"] - 2:
            issues.append("Ending quieter than Act 3 — should swell for emotional close (1.15× envelope)")

    # Room tone check: look for very brief silences between scenes (200ms)
    room_tone_cmd = [
        "ffmpeg", "-i", str(stereo_path),
        "-af", "silencedetect=noise=-45dB:d=0.15",
        "-f", "null", "-",
    ]
    rt_result = subprocess.run(room_tone_cmd, capture_output=True, text=True, timeout=60)
    micro_silences = sum(1 for line in rt_result.stderr.splitlines()
                        if "silence_start" in line)

    stereo_path.unlink()

    return {
        "ducking": {
            "detected": ducking_detected,
            "speech_to_gap_diff_db": ducking_ratio,
            "expected_ratio": "speech: 0.13×, silence: 0.28× (from audio-utils.ts)",
            "speech_sample_count": len(speech_volumes),
            "gap_sample_count": len(gap_volumes),
        },
        "act_volume_envelope": {
            act: round(vol, 1) if vol else None
            for act, vol in act_volumes.items()
        },
        "expected_envelope": ACT_VOLUME_ENVELOPE,
        "micro_silences_detected": micro_silences,
        "room_tone_assessment": (
            "present" if micro_silences > 5
            else "sparse" if micro_silences > 0
            else "absent"
        ),
        "issues": issues,
        "mixing_score": max(1, 10 - len(issues) * 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 10: NARRATIVE QUALITY (RE-HOOKS, POV, PERSONALITY)
# ═══════════════════════════════════════════════════════════════════════════════

def pass_narrative_quality(srt_entries: list[dict], duration_s: float,
                           yt_title: str, pipeline_state: dict) -> dict:
    """Check re-hooks at danger zones, POV shifts, personality, narrative arc."""
    if not srt_entries:
        return {"error": "No captions for narrative analysis"}

    # Get full caption text
    full_text = " ".join(e["text"] for e in srt_entries)

    # Build caption text at each retention danger zone
    danger_zone_samples = {}
    for dz_frac in RETENTION_DANGER_ZONES:
        dz_time = duration_s * dz_frac
        # Get ~15s of caption text around the danger zone
        window_text = " ".join(
            e["text"] for e in srt_entries
            if abs(e["start_s"] - dz_time) < 7.5
        )
        danger_zone_samples[f"{int(dz_frac*100)}%"] = {
            "timestamp_s": round(dz_time, 1),
            "text_sample": window_text[:300],
        }

    # Pipeline state quality data (if available)
    state_quality = {}
    if pipeline_state.get("found"):
        state_quality = {
            "script_doctor_scores": pipeline_state.get("script_doctor_scores"),
            "hook_scores": pipeline_state.get("hook_scores"),
            "fact_verification": pipeline_state.get("fact_verification"),
            "compliance": pipeline_state.get("compliance"),
        }

    # Send to Claude for narrative analysis
    state_context = ""
    if state_quality:
        state_context = f"""
PIPELINE QUALITY DATA (what was measured during production):
{json.dumps(state_quality, indent=2, default=str)[:2000]}

Compare the final narration against these pre-production quality scores."""

    try:
        result = call_agent(
            "content_auditor_master",
            system_prompt="""You are a narrative quality analyst for dark history documentaries.
You understand retention psychology, narrative structure, and audience engagement.
Output ONLY valid JSON, nothing else.""",
            user_prompt=f"""VIDEO: "{yt_title}"

FULL NARRATION TEXT (from captions):
{full_text[:5000]}

RETENTION DANGER ZONES (where viewers typically drop off):
{json.dumps(danger_zone_samples, indent=2)}
{state_context}

RE-HOOK PATTERNS to look for (words/phrases that recapture attention):
"but what", "here's what", "that wasn't", "stay with me", "this is where",
"forget everything", "it gets", "worse than", "nobody talks about",
"changes everything", "the worst part", "and then", "not the end",
"just the beginning", "here's the thing", "but here's", "wait —", "hold on"

Analyze this narration for:

Return ONLY valid JSON:
{{
    "narrative_score": <1-10>,
    "hook_analysis": {{
        "hook_present": <true/false>,
        "hook_type": "<curiosity_gap/shock/question/mystery/contrast>",
        "hook_strength": <1-10>,
        "hook_text": "<the actual hook text from captions>",
        "grabs_in_5_seconds": <true/false>
    }},
    "re_hooks": {{
        "danger_zone_5pct": {{
            "re_hook_present": <true/false>,
            "pattern_found": "<the re-hook pattern or 'none'>",
            "text": "<the re-hook text>"
        }},
        "danger_zone_25pct": {{ ... }},
        "danger_zone_50pct": {{ ... }},
        "danger_zone_75pct": {{ ... }},
        "total_re_hooks_found": <int>,
        "coverage": "<all zones covered / gaps at X% / no re-hooks>"
    }},
    "pov_shifts": {{
        "count": <int>,
        "shifts_detected": ["<describe each POV shift: from whose perspective to whose>"],
        "assessment": "<rich multi-perspective / some shifts / flat single POV>"
    }},
    "personality": {{
        "score": <1-10>,
        "human_markers": ["<quirky observations, unexpected analogies, dark humor examples>"],
        "ai_generic_markers": ["<phrases that feel AI-generated or generic>"],
        "assessment": "<unmistakably authored / shows personality / generic / robotic>"
    }},
    "emotional_arc": {{
        "score": <1-10>,
        "arc_shape": "<rising_tension / flat / frontloaded / proper_narrative_arc>",
        "climax_location_pct": <where the emotional peak is, as percentage>,
        "breathing_room_after_climax": <true/false>,
        "resolution_feels_complete": <true/false>
    }},
    "factual_density": {{
        "specific_dates": <count of specific dates/years mentioned>,
        "named_figures": <count of named people>,
        "concrete_details": "<high/medium/low — are claims anchored in specifics?>"
    }},
    "retention_prediction": {{
        "estimated_retention_30s": "<high/medium/low>",
        "estimated_retention_50pct": "<high/medium/low>",
        "biggest_drop_risk": "<where and why viewers would leave>",
        "strongest_moment": "<the most compelling part of the narration>"
    }}
}}""",
            max_tokens=4000,
            expect_json=True,
            effort_offset=0,
            stage_num=13,
            topic=yt_title[:50],
        )
        return result if isinstance(result, dict) else {"error": "Parse failed"}
    except Exception as e:
        print(f"[Auditor] Narrative analysis failed: {e}")
        return {"error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 11: YOUTUBE METADATA & SEO
# ═══════════════════════════════════════════════════════════════════════════════

def pass_youtube_metadata(video_id: str, seo_data: dict | None) -> dict:
    """Fetch YouTube metadata and compare against SEO plan if available."""
    yt = _get_youtube_client_safe()
    if not yt:
        return {"error": "YouTube API unavailable"}

    try:
        response = yt.videos().list(
            part="snippet,contentDetails,statistics", id=video_id,
        ).execute()
        items = response.get("items", [])
        if not items:
            return {"error": "Video not found"}

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})

        metadata = {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "published_at": snippet.get("publishedAt", ""),
            "duration_iso": content.get("duration", ""),
            "definition": content.get("definition", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "thumbnail_url": (
                snippet.get("thumbnails", {}).get("maxres", {}).get("url")
                or snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            ),
        }

        # SEO compliance check
        issues = []
        if len(metadata["tags"]) < 5:
            issues.append(f"Only {len(metadata['tags'])} tags — minimum is 5")
        if len(metadata["title"]) > 70:
            issues.append(f"Title {len(metadata['title'])} chars — over 70 char recommendation")
        if len(metadata["description"]) < 200:
            issues.append("Description too short — needs 200+ chars for SEO")

        # Check for chapter markers in description
        has_chapters = bool(re.search(r"\d{1,2}:\d{2}", metadata["description"]))
        if not has_chapters:
            issues.append("No chapter timestamps in description")

        # Compare against pipeline SEO data if available
        if seo_data:
            planned_title = seo_data.get("recommended_title", "")
            if planned_title and planned_title != metadata["title"]:
                issues.append(f"Title differs from SEO plan: planned '{planned_title[:50]}'")

            planned_tags = seo_data.get("tags", [])
            if planned_tags:
                actual_tags_lower = {t.lower() for t in metadata["tags"]}
                missing_tags = [t for t in planned_tags[:10]
                               if t.lower() not in actual_tags_lower]
                if len(missing_tags) > 3:
                    issues.append(f"Missing {len(missing_tags)} planned tags: {missing_tags[:3]}")

        metadata["seo_issues"] = issues
        metadata["seo_score"] = max(1, 10 - len(issues) * 2)
        return metadata

    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  PASS 12: MASTER ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════

def pass_master_assessment(report: dict) -> dict:
    """Synthesize all passes into a final verdict against the quality contract."""
    # Gather all section data (excluding master itself)
    sections = {k: v for k, v in report.get("sections", {}).items()
                if k != "master_assessment"}
    sections_json = json.dumps(sections, indent=2, default=str)[:12000]

    topic = report.get("topic", "Unknown")

    # Build quality contract summary for the LLM
    contract = """
QUALITY CONTRACT — What this pipeline promises:

SCRIPT: 7+ avg across 7 dimensions (hook_strength, emotional_pacing, personality,
pov_shifts, voice_consistency, factual_grounding, emotional_arc). Reflection beat
present after climax. Re-hooks at 5%, 25%, 50%, 75% retention danger zones.

SCENE INTENT: Scenes vary in energy (0-1 scale based on mood + narrative_function).
Transitions: normal (0.4s/35%), act (0.8s/70%), reveal. Act boundaries at 7%, 28%, 67%, 90%.
Ken Burns motion varies by intent (16 patterns, no 3 repeats).

CAPTIONS: 4-7 words per group, 2.0-3.5 wps comfortable speed, emphasis on numbers/all-caps.
3-frame color transitions. Spring animations. Max 6 words per group.

VOICE: Pacing varies by narrative position (hook: 145 WPM, act3: 125 WPM, ending: 120 WPM).
Base speed 0.88. Breathing room in Act 3. Reflection beat before conclusion.

AUDIO: Music ducks to 0.13× during speech, 0.28× during silence. Act envelope:
Act1 0.9×, Act2 1.1×, Act3 0.75×, Ending 1.15×. Room tone between scenes.

VISUAL: Consistent art style per visual bible. 3-4 hex color palette. Character consistency.
Treatment variety (close_portrait, wide_establishing, artifact_detail, etc.).
No same treatment 3× in a row. Images scored 7+/10.

VIDEO: 1920×1080, 30fps, CRF 15. Scene overlap: L-cut 0.3s, J-cut 0.2s.
Scene fade 0.5s. End screen 20s. Duration 5-20 min.
"""

    result = call_agent(
        "content_auditor_master",
        system_prompt=f"""You are the Chief Quality Officer for The Obsidian Archive, a dark history documentary YouTube channel.

You have access to a 12-pass post-production audit AND the pipeline's quality contract.
Your job is to grade the video against what the pipeline PROMISED to deliver.

Be brutally honest. Score against the contract, not against "good enough."
If the pipeline failed to deliver its own promises, say so explicitly.

{contract}""",
        user_prompt=f"""TOPIC: {topic}

FULL 12-PASS AUDIT DATA:
{sections_json}

Synthesize into a master assessment. Return ONLY valid JSON:

{{
    "overall_score": <1-10>,
    "grade": "<A+/A/A-/B+/B/B-/C+/C/D/F>",
    "verdict": "<PUBLISH_CONFIDENT / PUBLISH_WITH_NOTES / NEEDS_REVISION / PULL_AND_REDO>",

    "contract_compliance": {{
        "script_quality": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<how does it compare to the 7-dimension contract?>"
        }},
        "scene_intent": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<does energy/pacing vary as scene intent promises?>"
        }},
        "caption_quality": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<grouping, speed, sync compliance>"
        }},
        "voice_modulation": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<does voice vary by act as promised?>"
        }},
        "audio_mixing": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<ducking, envelope, room tone compliance>"
        }},
        "visual_continuity": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<art style consistency, treatment variety>"
        }},
        "transition_quality": {{
            "score": <1-10>,
            "meets_contract": <true/false>,
            "detail": "<correct transition types at act boundaries?>"
        }}
    }},

    "root_cause_analysis": "<what is the FUNDAMENTAL issue? not symptoms, the root cause>",

    "strengths": ["<top 3-5 genuine strengths>"],
    "critical_issues": ["<issues that MUST be fixed — ranked by severity>"],
    "retention_killers": ["<specific moments/patterns that cause viewers to click away>"],

    "intent_vs_output": {{
        "alignment_score": <1-10>,
        "assessment": "<does the final video deliver what was planned?>"
    }},

    "audience_impression": "<what would a viewer think in the first 30 seconds?>",

    "pipeline_fixes": [
        {{
            "component": "<which pipeline stage/agent>",
            "issue": "<what's wrong>",
            "fix": "<specific code/config change>"
        }}
    ],

    "comparison_to_competitors": "<honest comparison to Lemmino, Nexpo, Thoughty2, etc.>"
}}""",
        max_tokens=5000,
        expect_json=True,
        effort_offset=1,  # bump to premium for final assessment
        stage_num=13,
        topic=topic,
    )
    return result if isinstance(result, dict) else {"error": "Assessment failed"}


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run(video_id: str) -> dict:
    print(f"\n{'='*70}")
    print(f"  CONTENT AUDITOR v3 — Video: {video_id}")
    print("  12-Pass Quality Contract Audit")
    print(f"{'='*70}\n")

    report = {
        "video_id": video_id,
        "audit_version": "v3",
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "sections": {},
    }

    work_dir = Path(tempfile.mkdtemp(prefix="obsidian_audit_"))
    print(f"[Auditor] Work dir: {work_dir}")

    # ── Pass 0: Download ──────────────────────────────────────────────────
    print("\n[Pass 0/12] Downloading video + captions...")
    video_path = download_video(video_id, work_dir)
    if not video_path:
        print("[FATAL] Cannot download video. Aborting.")
        return report

    srt_entries = parse_srt_with_timestamps(video_id, work_dir)
    captions_text = " ".join(e["text"] for e in srt_entries)
    print(f"  Captions: {len(srt_entries)} entries, {len(captions_text)} chars")

    # ── Pass 1: Technical specs ───────────────────────────────────────────
    print("\n[Pass 1/12] Technical analysis...")
    tech = pass_technical(video_path)
    report["sections"]["technical"] = tech
    duration_s = tech.get("duration_s", 0)
    print(f"  {tech.get('width')}x{tech.get('height')} | {tech.get('fps')}fps | "
          f"{duration_s:.0f}s | {tech.get('size_mb', 0):.1f}MB")
    if tech.get("contract_issues"):
        for ci in tech["contract_issues"]:
            print(f"  ! {ci}")

    # ── Pass 2: Pipeline state ────────────────────────────────────────────
    print("\n[Pass 2/12] Loading pipeline state...")
    state = pass_load_state(video_id)
    report["sections"]["pipeline_state"] = {
        "found": state["found"],
        "state_file": state.get("state_file"),
        "script_doctor_scores": state.get("script_doctor_scores"),
        "hook_scores": state.get("hook_scores"),
        "compliance": state.get("compliance"),
        "fact_verification": state.get("fact_verification"),
        "scene_count": state.get("scene_count"),
        "qa_results": state.get("qa_results"),
    }

    # ── Pass 3: Act structure ─────────────────────────────────────────────
    print("\n[Pass 3/12] Act structure & energy curve...")
    act_data = pass_act_structure(video_path, srt_entries, duration_s, work_dir)
    report["sections"]["act_structure"] = act_data
    print(f"  Overall WPM: {act_data.get('overall_wpm', '?')} (target: 130)")
    for issue in act_data.get("issues", []):
        print(f"  ! {issue}")

    # ── Pass 4: Scene pacing ──────────────────────────────────────────────
    print("\n[Pass 4/12] Scene duration variance & pacing...")
    scene_data = pass_scene_pacing(video_path, duration_s, work_dir)
    report["sections"]["scene_pacing"] = scene_data
    scene_times = scene_data.get("scene_times", [])
    print(f"  {scene_data.get('scene_count', '?')} scenes | "
          f"avg: {scene_data.get('avg_scene_duration_s', '?')}s | "
          f"CV: {scene_data.get('coefficient_of_variation', '?')}")

    # ── Pass 5: Transitions ───────────────────────────────────────────────
    print("\n[Pass 5/12] Scene transition quality...")
    trans_data = pass_transitions(video_path, scene_times, duration_s, work_dir)
    report["sections"]["transitions"] = trans_data
    print(f"  Score: {trans_data.get('transition_quality_score', '?')}/10 | "
          f"Analyzed: {trans_data.get('pairs_analyzed', 0)} pairs")

    # ── Pass 6: Visual continuity ─────────────────────────────────────────
    print("\n[Pass 6/12] Visual continuity & art style...")
    yt_meta = pass_youtube_metadata(video_id, state.get("seo_data"))
    report["sections"]["youtube_metadata"] = yt_meta
    report["topic"] = yt_meta.get("title", "Unknown")

    visual_data = pass_visual_continuity(
        video_path, duration_s, work_dir,
        yt_meta.get("title", ""), state.get("visual_bible")
    )
    report["sections"]["visual_continuity"] = visual_data
    print(f"  Continuity: {visual_data.get('continuity_score', '?')}/10 | "
          f"Variety: {visual_data.get('visual_variety', {}).get('score', '?')}/10")

    # ── Pass 7: Captions ──────────────────────────────────────────────────
    print("\n[Pass 7/12] Caption sync, grouping & styling...")
    caption_data = pass_captions(video_path, srt_entries, work_dir)
    report["sections"]["captions"] = caption_data
    print(f"  Avg: {caption_data.get('avg_wps', '?')} wps | "
          f"Score: {caption_data.get('caption_score', '?')}/10 | "
          f"Issues: {len(caption_data.get('issues', []))}")

    # ── Pass 8: Voice modulation ──────────────────────────────────────────
    print("\n[Pass 8/12] Voice modulation by act...")
    voice_data = pass_voice_modulation(
        video_path, srt_entries, duration_s, work_dir,
        state.get("voice_settings")
    )
    report["sections"]["voice_modulation"] = voice_data
    print(f"  Consistency: {voice_data.get('voice_consistency', '?')} | "
          f"Breathing room: {'Yes' if voice_data.get('breathing_room_present') else 'No'} | "
          f"Reflection beat: {'Yes' if voice_data.get('reflection_beat_present') else 'No'}")

    # ── Pass 9: Audio mixing ─────────────────────────────────────────────
    print("\n[Pass 9/12] Audio mixing analysis...")
    audio_data = pass_audio_mixing(video_path, srt_entries, duration_s, work_dir)
    report["sections"]["audio_mixing"] = audio_data
    ducking = audio_data.get("ducking", {})
    print(f"  Ducking: {'Detected' if ducking.get('detected') else 'NOT DETECTED'} | "
          f"Room tone: {audio_data.get('room_tone_assessment', '?')} | "
          f"Score: {audio_data.get('mixing_score', '?')}/10")

    # ── Pass 10: Narrative quality ────────────────────────────────────────
    print("\n[Pass 10/12] Narrative quality (re-hooks, POV, personality)...")
    narrative_data = pass_narrative_quality(
        srt_entries, duration_s, yt_meta.get("title", ""), state
    )
    report["sections"]["narrative_quality"] = narrative_data
    print(f"  Narrative: {narrative_data.get('narrative_score', '?')}/10 | "
          f"Hook: {narrative_data.get('hook_analysis', {}).get('hook_strength', '?')}/10 | "
          f"Re-hooks: {narrative_data.get('re_hooks', {}).get('total_re_hooks_found', '?')}")

    # ── Pass 11: YouTube metadata ─────────────────────────────────────────
    print("\n[Pass 11/12] YouTube metadata & SEO...")
    # Already fetched in pass 6
    yt = report["sections"]["youtube_metadata"]
    if "error" not in yt:
        print(f"  Title: {yt.get('title', '?')[:60]}")
        print(f"  Tags: {len(yt.get('tags', []))} | Views: {yt.get('view_count', 0):,} | "
              f"SEO: {yt.get('seo_score', '?')}/10")

    # ── Pass 12: Master assessment ────────────────────────────────────────
    print("\n[Pass 12/12] Master assessment against quality contract...")
    report["sections"]["master_assessment"] = pass_master_assessment(report)

    # ── Save & cleanup ────────────────────────────────────────────────────
    report_path = OUTPUTS_DIR / f"audit_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[Auditor] Report saved: {report_path.name}")

    if video_path.exists():
        video_path.unlink()
        print("[Auditor] Cleaned up video")

    _print_summary(report)
    return report


# ═══════════════════════════════════════════════════════════════════════════════
#  SUMMARY PRINTER
# ═══════════════════════════════════════════════════════════════════════════════

def _print_summary(report: dict):
    sections = report.get("sections", {})

    print(f"\n{'='*70}")
    print("  CONTENT AUDITOR v3 — REPORT SUMMARY")
    print(f"{'='*70}")
    print(f"\n  Video: https://youtube.com/watch?v={report['video_id']}")
    print(f"  Topic: {report.get('topic', '?')}")

    # Technical
    tech = sections.get("technical", {})
    if "error" not in tech:
        print(f"\n  TECHNICAL: {tech.get('width')}x{tech.get('height')} | "
              f"{tech.get('duration_s', 0):.0f}s | {tech.get('fps')}fps | "
              f"{tech.get('size_mb', 0):.1f}MB")

    # Pipeline state
    state = sections.get("pipeline_state", {})
    if state.get("found"):
        print(f"  PIPELINE STATE: Loaded from {state.get('state_file', '?')}")
        if state.get("script_doctor_scores"):
            scores = state["script_doctor_scores"]
            if isinstance(scores, dict):
                avg = sum(v for v in scores.values() if isinstance(v, (int, float))) / max(len(scores), 1)
                print(f"    Script Doctor avg: {avg:.1f}/10")

    # Act structure
    act = sections.get("act_structure", {})
    if "error" not in act:
        print(f"\n  ACT STRUCTURE: Overall {act.get('overall_wpm', '?')} WPM (target: 130)")
        print(f"    Score: {act.get('act_structure_score', '?')}/10")

    # Scene pacing
    sp = sections.get("scene_pacing", {})
    if "error" not in sp:
        print(f"\n  SCENE PACING: {sp.get('scene_count', '?')} scenes | "
              f"avg {sp.get('avg_scene_duration_s', '?')}s | "
              f"CV: {sp.get('coefficient_of_variation', '?')}")
        print(f"    Score: {sp.get('pacing_score', '?')}/10")

    # Transitions
    trans = sections.get("transitions", {})
    if "error" not in trans:
        print(f"\n  TRANSITIONS: {trans.get('transition_quality_score', '?')}/10")

    # Visual
    vis = sections.get("visual_continuity", {})
    if "error" not in vis:
        print(f"\n  VISUAL: Continuity {vis.get('continuity_score', '?')}/10 | "
              f"Variety {vis.get('visual_variety', {}).get('score', '?')}/10 | "
              f"Composition {vis.get('composition_quality', {}).get('score', '?')}/10")

    # Captions
    cap = sections.get("captions", {})
    if "error" not in cap:
        dist = cap.get("speed_distribution", {})
        print(f"\n  CAPTIONS: {cap.get('avg_wps', '?')} avg wps | "
              f"Score: {cap.get('caption_score', '?')}/10")
        print(f"    Comfortable: {dist.get('comfortable_under_3.5wps', 0)} | "
              f"Fast: {dist.get('fast_3.5_to_5wps', 0)} | "
              f"Unreadable: {dist.get('unreadable_over_5wps', 0)}")

    # Voice
    voice = sections.get("voice_modulation", {})
    if "error" not in voice:
        print(f"\n  VOICE: {voice.get('voice_consistency', '?')} | "
              f"Score: {voice.get('voice_score', '?')}/10")
        print(f"    Breathing room: {'YES' if voice.get('breathing_room_present') else 'NO'} | "
              f"Reflection beat: {'YES' if voice.get('reflection_beat_present') else 'NO'}")
        print(f"    WPM by quarter: {voice.get('pacing_wpm_per_quarter', [])}")

    # Audio mixing
    audio = sections.get("audio_mixing", {})
    if "error" not in audio:
        duck = audio.get("ducking", {})
        print(f"\n  AUDIO MIXING: Score {audio.get('mixing_score', '?')}/10")
        print(f"    Ducking: {'YES' if duck.get('detected') else 'NO'} "
              f"(diff: {duck.get('speech_to_gap_diff_db', '?')}dB)")
        print(f"    Room tone: {audio.get('room_tone_assessment', '?')}")

    # Narrative
    narr = sections.get("narrative_quality", {})
    if "error" not in narr:
        hook = narr.get("hook_analysis", {})
        rehooks = narr.get("re_hooks", {})
        print(f"\n  NARRATIVE: Score {narr.get('narrative_score', '?')}/10")
        print(f"    Hook: {hook.get('hook_strength', '?')}/10 ({hook.get('hook_type', '?')})")
        print(f"    Re-hooks: {rehooks.get('total_re_hooks_found', '?')} at danger zones")
        pov = narr.get("pov_shifts", {})
        print(f"    POV shifts: {pov.get('count', '?')} | "
              f"Personality: {narr.get('personality', {}).get('score', '?')}/10")

    # YouTube
    yt = sections.get("youtube_metadata", {})
    if "error" not in yt and yt.get("view_count") is not None:
        print(f"\n  YOUTUBE: {yt.get('view_count', 0):,} views | "
              f"{yt.get('like_count', 0):,} likes | "
              f"SEO: {yt.get('seo_score', '?')}/10")

    # Master assessment
    master = sections.get("master_assessment", {})
    if "error" not in master:
        print(f"\n  {'─'*60}")
        print(f"  VERDICT: {master.get('grade', '?')} ({master.get('overall_score', '?')}/10) — "
              f"{master.get('verdict', '?')}")

        # Contract compliance
        cc = master.get("contract_compliance", {})
        if cc:
            print("\n  CONTRACT COMPLIANCE:")
            for area, data in cc.items():
                if isinstance(data, dict):
                    check = "PASS" if data.get("meets_contract") else "FAIL"
                    print(f"    [{check}] {area}: {data.get('score', '?')}/10")

        print(f"\n  Root cause: {master.get('root_cause_analysis', '?')}")

        print("\n  Strengths:")
        for s in master.get("strengths", [])[:5]:
            print(f"    + {s}")

        print("\n  Critical issues:")
        for w in master.get("critical_issues", [])[:5]:
            print(f"    ! {w}")

        print("\n  Retention killers:")
        for r in master.get("retention_killers", [])[:3]:
            print(f"    X {r}")

        fixes = master.get("pipeline_fixes", [])
        if fixes:
            print("\n  Pipeline fixes needed:")
            for fix in fixes[:5]:
                if isinstance(fix, dict):
                    print(f"    [{fix.get('component', '?')}] {fix.get('issue', '?')}")
                    print(f"      Fix: {fix.get('fix', '?')}")
                else:
                    print(f"    - {fix}")

        print(f"\n  Audience impression: {master.get('audience_impression', '?')}")
        print(f"  Competitor comparison: {master.get('comparison_to_competitors', '?')}")

    print(f"\n{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _find_latest_video_id() -> str | None:
    yt = _get_youtube_client_safe()
    if not yt:
        return None
    try:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads_id, maxResults=1
        ).execute()
        items = pl.get("items", [])
        if items:
            vid = items[0]["contentDetails"]["videoId"]
            print(f"[Auditor] Latest upload: {vid}")
            return vid
    except Exception as e:
        print(f"[Auditor] Could not find latest video: {e}")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Obsidian Archive — Content Auditor v3")
    parser.add_argument("--video-id", help="YouTube video ID")
    parser.add_argument("--url", help="YouTube URL")
    parser.add_argument("--latest", action="store_true", help="Audit most recent upload")
    args = parser.parse_args()

    video_id = args.video_id

    if args.url:
        match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", args.url)
        if match:
            video_id = match.group(1)
        else:
            print("Could not extract video ID from URL")
            sys.exit(1)

    if not video_id and args.latest:
        video_id = _find_latest_video_id()

    if not video_id:
        video_id = _find_latest_video_id()

    if not video_id:
        print("No video ID. Use --video-id, --url, or --latest")
        sys.exit(1)

    result = run(video_id)

    verdict = result.get("sections", {}).get("master_assessment", {}).get("verdict", "")
    sys.exit(1 if verdict in ("NEEDS_REVISION", "PULL_AND_REDO") else 0)

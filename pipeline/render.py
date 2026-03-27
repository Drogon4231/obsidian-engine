import json
import re
import subprocess
from datetime import datetime

from core.paths import BASE_DIR, OUTPUT_DIR, REMOTION_SRC, REMOTION_PUBLIC
from core.log import get_logger

logger = get_logger(__name__)


def validate_video_ffprobe(video_path, expected_duration=0, min_bitrate=3000):
    """Run ffprobe on rendered video. Falls back gracefully if not installed."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            audio_codec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None)
            def _safe_float(v, default=0):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return default
            duration  = next((_safe_float(s.get("duration", 0)) for s in streams if s.get("codec_type") == "video"), 0)
            if not has_video:
                return False, "No video stream found"
            if not has_audio:
                return False, "No audio stream found"
            if not audio_codec:
                return False, "Audio codec not detected"
            if duration < 10:
                return False, f"Video too short: {duration:.1f}s"

            # Check video bitrate (from format-level bit_rate or video stream)
            bitrate_kbps = 0
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            if video_stream.get("bit_rate"):
                bitrate_kbps = int(video_stream["bit_rate"]) / 1000
            elif fmt.get("bit_rate"):
                bitrate_kbps = int(fmt["bit_rate"]) / 1000
            if bitrate_kbps > 0 and bitrate_kbps < min_bitrate:
                return False, f"Video bitrate too low: {bitrate_kbps:.0f}kbps (minimum {min_bitrate}kbps)"

            # Check frame count vs expected duration at 30fps
            nb_frames = video_stream.get("nb_frames")
            if nb_frames and nb_frames != "N/A":
                frame_count = int(nb_frames)
                expected_frames = int(duration * 30)
                if expected_frames > 0 and abs(frame_count - expected_frames) / expected_frames > 0.1:
                    return False, (f"Frame count mismatch: {frame_count} frames vs "
                                   f"{expected_frames} expected at 30fps for {duration:.1f}s")

            # Check duration matches expected within 10% tolerance
            if expected_duration > 0:
                tolerance = expected_duration * 0.1
                if abs(duration - expected_duration) > tolerance:
                    return False, (f"Duration mismatch: {duration:.1f}s actual vs "
                                   f"{expected_duration:.1f}s expected (>{tolerance:.1f}s tolerance)")

            logger.info(f"[Validate] ✓ ffprobe OK — {duration:.0f}s, video+audio streams present, "
                  f"bitrate={bitrate_kbps:.0f}kbps, audio_codec={audio_codec}")
            return True, {"duration": duration, "has_video": has_video, "has_audio": has_audio,
                          "audio_codec": audio_codec, "bitrate_kbps": bitrate_kbps}
        else:
            stderr_snippet = (result.stderr or "")[:200]
            return False, f"ffprobe exited with code {result.returncode}: {stderr_snippet}"
    except FileNotFoundError:
        logger.warning("[Validate] ffprobe not installed — skipping video validation")
    except Exception as e:
        logger.error(f"[Validate] ffprobe error: {e}")
    return True, {"skipped": "ffprobe not available"}


# ── Stage 12: Render ───────────────────────────────────────────────────────────
def run_render(topic):
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug  = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:40]
    output = OUTPUT_DIR / f"{ts}_{slug}_FINAL_VIDEO.mp4"

    # Clean up any stale partial renders to free disk space
    for stale in OUTPUT_DIR.glob("*_FINAL_VIDEO.mp4"):
        try:
            if stale != output:
                stale.unlink()
                logger.info(f"[Render] Removed stale file: {stale.name}")
        except Exception:
            pass

    # Ensure short-video-data.json exists for Webpack compilation
    svd_path = REMOTION_SRC / "short-video-data.json"
    if not svd_path.exists():
        svd_path.write_text(json.dumps({
            "total_duration_seconds": 0,
            "scenes": [],
            "word_timestamps": [],
        }))
        logger.info("[Render] Created stub short-video-data.json for Webpack compilation")

    # Validate required assets exist before rendering
    narration_mp3 = REMOTION_PUBLIC / "narration.mp3"
    if not narration_mp3.exists():
        raise FileNotFoundError(f"[Render] Missing {narration_mp3} — audio stage must complete first")
    vd_check = REMOTION_SRC / "video-data.json"
    if not vd_check.exists():
        raise FileNotFoundError(f"[Render] Missing {vd_check} — convert stage must complete first")

    logger.info(f"[Render] Rendering to {output.name}...")
    logger.info("[Render] Rendering with concurrency=4...")

    proc = subprocess.Popen(
        ["npx", "remotion", "render", "ObsidianArchive", str(output),
         "--concurrency=4", "--gl=swangle", "--codec=h264", "--crf=15",
         "--enable-multiprocess-on-linux"],
        cwd=BASE_DIR / "remotion",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    last_progress = ""
    error_lines = []
    for line in proc.stdout:
        line = line.rstrip()
        m = re.search(r'(?:Frame|Rendered)[\s:]*(\d+)/(\d+)', line)
        if m:
            cur, total = int(m.group(1)), int(m.group(2))
            pct = int(cur / total * 100) if total > 0 else 0
            progress = f"[Render] Frame {cur}/{total} ({pct}%)"
            if progress != last_progress:
                logger.info(progress)
                last_progress = progress
        elif line.strip():
            logger.info(f"[Render] {line}")
            if any(w in line.lower() for w in ('error', 'failed', 'fatal', 'exception', 'cannot', 'unable', 'chromium', 'chrome', 'browser')):
                error_lines.append(line)
    proc.wait()
    if proc.returncode != 0:
        detail = "\n".join(error_lines[-10:]) if error_lines else "no error detail captured"
        raise Exception(f"Remotion render failed:\n{detail}")

    size_mb = output.stat().st_size / 1024 / 1024
    logger.info(f"[Render] ✓ {output.name} ({size_mb:.1f}MB)")

    # Read expected duration from video-data.json for validation
    vd_check = REMOTION_SRC / "video-data.json"
    expected_dur = 0
    if vd_check.exists():
        try:
            expected_dur = json.loads(vd_check.read_text()).get("total_duration_seconds", 0)
        except Exception:
            pass
    ok, info = validate_video_ffprobe(str(output), expected_duration=expected_dur)
    if not ok:
        raise Exception(f"[Render] Video validation FAILED: {info} — not uploading corrupted video")

    return str(output)

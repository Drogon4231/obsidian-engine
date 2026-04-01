"""
Track Adapter — adapts Epidemic Sound tracks to exact video duration.

Uses the edit_recording API (beta) to:
1. Trim/extend a track to match total_duration exactly
2. Download stems (bass, drums, instruments) for smarter ducking
3. Map act structure to preferenceRegions so music climax aligns with narrative

API constraint: max target_duration is 300,000ms (5 min).
For videos >5 min, uses loopable=true to get seamless loop points.
"""

from __future__ import annotations

import time
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MUSIC_DIR = BASE_DIR / "remotion" / "public" / "music"
STEMS_DIR = MUSIC_DIR / "stems"
STEMS_DIR.mkdir(parents=True, exist_ok=True)

MAX_ADAPTATION_DURATION_MS = 300_000  # 5 minutes — API hard limit


def _find_act_boundaries(scenes: list[dict], total_duration_ms: int) -> dict:
    """Find act boundary timestamps from scene narrative_positions."""
    boundaries = {
        "hook_end": int(total_duration_ms * 0.07),
        "act1_end": int(total_duration_ms * 0.28),
        "act2_end": int(total_duration_ms * 0.67),
        "act3_end": int(total_duration_ms * 0.90),
        "climax_start": int(total_duration_ms * 0.70),
        "climax_end": int(total_duration_ms * 0.82),
        "silence_start": int(total_duration_ms * 0.82),
        "silence_end": int(total_duration_ms * 0.88),
    }

    # Refine from actual scene data if available
    for s in scenes:
        pos = s.get("narrative_position", "")
        start_ms = int(s.get("start_time", 0) * 1000)

        if pos == "act1" and start_ms > 0:
            boundaries["hook_end"] = min(boundaries["hook_end"], start_ms)
        if pos == "act2" and start_ms > 0:
            boundaries["act1_end"] = start_ms
        if pos == "act3" and start_ms > 0:
            boundaries["act2_end"] = start_ms
        if pos == "ending" and start_ms > 0:
            boundaries["act3_end"] = start_ms

    return boundaries


def _build_preference_regions(scenes: list[dict], total_duration_ms: int) -> list[dict]:
    """Map act structure to Epidemic Sound preferenceRegions."""
    act = _find_act_boundaries(scenes, total_duration_ms)

    regions = [
        # Prefer atmospheric intro during hook
        {"start": 0, "end": act["hook_end"], "preference": "prefer"},
        # Prefer energy build during Act 2
        {"start": act["act1_end"], "end": act["act2_end"], "preference": "prefer"},
        # Prefer climax alignment with narrative climax
        {"start": act["climax_start"], "end": act["climax_end"], "preference": "prefer"},
        # Avoid energy during silence beat
        {"start": act["silence_start"], "end": act["silence_end"], "preference": "avoid"},
    ]

    return regions


def _build_required_regions(scenes: list[dict]) -> list[dict]:
    """Force music climax at reveal moment timestamps."""
    regions = []
    for s in scenes:
        if s.get("is_reveal_moment"):
            offset_ms = int(s.get("start_time", 0) * 1000)
            if offset_ms > 0:
                regions.append({"offset": offset_ms, "type": "climax"})
                break  # One required region is enough
    return regions


def adapt_to_duration(track_id: str, total_duration: float,
                      scenes: list[dict] | None = None,
                      download_stems: bool = True,
                      timeout: float = 120) -> dict | None:
    """Adapt a track to exact video duration with optional stems.

    Returns:
        {
            "adapted_file": "music/epidemic_adapted_<id>.mp3",
            "stems": {"bass": "...", "drums": "...", "instruments": "..."},
            "duration": float,
            "track_id": str,
        }
        or None if adaptation fails.
    """
    try:
        from clients.epidemic_client import EpidemicSoundClient
        from clients.epidemic_client import KeyExpiredError
    except ImportError:
        logger.warning("[Adapter] epidemic_client not available")
        return None

    client = EpidemicSoundClient()
    target_ms = int(total_duration * 1000)

    # API limit: 300,000ms (5 min). For longer videos, use loopable mode.
    loopable = target_ms > MAX_ADAPTATION_DURATION_MS
    effective_target = min(target_ms, MAX_ADAPTATION_DURATION_MS)

    if loopable:
        logger.info(f"[Adapter] Video {total_duration:.0f}s > 300s limit — using loopable adaptation at {effective_target / 1000:.0f}s")

    # Build preference regions from act structure
    preference_regions = None
    required_regions = None
    if scenes and not loopable:
        preference_regions = _build_preference_regions(scenes, effective_target)
        required_regions = _build_required_regions(scenes) or None

    try:
        # Submit adaptation job
        job = client.adapt_track(
            track_id,
            target_duration_ms=effective_target,
            force_duration=True,
            loopable=loopable,
            max_results=1,
            preference_regions=preference_regions,
            required_regions=required_regions,
            skip_stems=not download_stems,
        )

        job_id = job.get("job_id", "")
        if not job_id:
            logger.warning(f"[Adapter] No job_id returned: {job}")
            return None

        logger.info(f"[Adapter] Adaptation job submitted: {job_id} (target={effective_target / 1000:.0f}s, loopable={loopable})")

        # Poll for completion
        deadline = time.time() + timeout
        status = "PENDING"
        result_data = {}

        while time.time() < deadline and status in ("PENDING", "IN_PROGRESS"):
            time.sleep(5)
            result_data = client.get_adaptation_status(job_id)
            status = result_data.get("status", "UNKNOWN")
            logger.info(f"[Adapter] Job {job_id}: {status}")

        if status != "COMPLETED":
            logger.warning(f"[Adapter] Adaptation did not complete: {status}")
            return None

        # Download adapted track
        edits = result_data.get("edits", [])
        edit_id = edits[0].get("id", "") if edits else ""
        if not edit_id:
            # Try alternative response format
            edit_id = result_data.get("edit_id", job_id)

        adapted_filename = f"epidemic_adapted_{track_id}.mp3"
        adapted_path = MUSIC_DIR / adapted_filename
        client.download_adapted_track(job_id, edit_id, adapted_path)

        if not adapted_path.exists() or adapted_path.stat().st_size < 50000:
            logger.warning(f"[Adapter] Adapted file too small or missing: {adapted_filename}")
            return None

        logger.info(f"[Adapter] Adapted track saved: {adapted_filename} ({adapted_path.stat().st_size // 1024}KB)")

        # Download stems if requested
        stems = {}
        if download_stems:
            for stem_type in ("BASS", "DRUMS", "INSTRUMENTS"):
                stem_filename = f"epidemic_{track_id}_{stem_type.lower()}.mp3"
                stem_path = STEMS_DIR / stem_filename
                try:
                    client.download_track(track_id, stem_path, stem=stem_type)
                    if stem_path.exists() and stem_path.stat().st_size > 10000:
                        stems[stem_type.lower()] = f"music/stems/{stem_filename}"
                        logger.info(f"[Adapter] Stem downloaded: {stem_filename}")
                    elif stem_path.exists() and stem_path.stat().st_size == 0:
                        logger.warning(f"[Adapter] Stem {stem_type.lower()} expected but download produced empty file: {stem_filename} (0 bytes)")
                    else:
                        size = stem_path.stat().st_size if stem_path.exists() else 0
                        logger.warning(f"[Adapter] Stem {stem_type.lower()} expected but file too small or missing: {stem_filename} ({size} bytes)")
                except Exception as stem_err:
                    logger.warning(f"[Adapter] Stem {stem_type.lower()} expected but download failed: {stem_err}")

        return {
            "adapted_file": f"music/{adapted_filename}",
            "stems": stems if stems else None,
            "duration": effective_target / 1000,
            "track_id": track_id,
            "loopable": loopable,
        }

    except KeyExpiredError:
        logger.warning("[Adapter] API key expired — skipping adaptation")
        return None
    except Exception as e:
        logger.warning(f"[Adapter] Adaptation failed: {e}")
        return None

"""
Epidemic Sound music manager — API-powered track selection and download.

Searches the Epidemic Sound catalog by mood/BPM/energy, downloads tracks
to the local music cache, and integrates with music_manager.py's rotation system.

Falls back gracefully if API unavailable (key expired, network error, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MUSIC_DIR = BASE_DIR / "remotion" / "public" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Obsidian mood → Epidemic Sound search params ──────────────────────────────

MOOD_SEARCH_MAP = {
    "dark": {
        "keyword": "dark ambient cinematic",
        "mood": "dark",
        "bpm_min": 40,
        "bpm_max": 100,
    },
    "tense": {
        "keyword": "tension suspense thriller",
        "mood": "tense",
        "bpm_min": 80,
        "bpm_max": 130,
    },
    "dramatic": {
        "keyword": "epic cinematic orchestral",
        "mood": "epic",
        "bpm_min": 100,
        "bpm_max": 140,
    },
    "cold": {
        "keyword": "atmospheric minimal desolate",
        "mood": "melancholic",
        "bpm_min": 40,
        "bpm_max": 90,
    },
    "reverent": {
        "keyword": "sacred solemn meditation",
        "mood": "peaceful",
        "bpm_min": 40,
        "bpm_max": 80,
    },
    "wonder": {
        "keyword": "awe discovery vast cinematic",
        "mood": "uplifting",
        "bpm_min": 60,
        "bpm_max": 120,
    },
    "warmth": {
        "keyword": "tender intimate gentle",
        "mood": "romantic",
        "bpm_min": 50,
        "bpm_max": 100,
    },
    "absurdity": {
        "keyword": "quirky playful bizarre",
        "mood": "funny",
        "bpm_min": 80,
        "bpm_max": 140,
    },
}


def _get_client():
    """Lazy import to avoid import errors when key not configured."""
    from clients.epidemic_client import EpidemicSoundClient
    return EpidemicSoundClient()


def _sanitize_filename(title: str, track_id: str, mood: str) -> str:
    """Build a safe filename for a downloaded track."""
    safe_title = re.sub(r'[^a-z0-9]+', '_', title.lower())[:40]
    return f"epidemic_api_{mood}_{safe_title}_{track_id}.mp3"


def search_and_download_for_mood(mood: str, target_duration: float = 600,
                                  prefer_no_vocals: bool = True) -> dict | None:
    """Search Epidemic Sound for a track matching the mood, download to cache.

    Returns dict with keys: filename, track_id, title, artist, bpm, mood.
    Returns None if API unavailable or no results.
    """
    params = MOOD_SEARCH_MAP.get(mood, MOOD_SEARCH_MAP["dark"])

    try:
        client = _get_client()

        search_kwargs = {
            "keyword": params["keyword"],
            "bpm_min": params.get("bpm_min"),
            "bpm_max": params.get("bpm_max"),
            "mood": params.get("mood"),
            "limit": 5,
            "sort": "relevance",
        }
        if prefer_no_vocals:
            search_kwargs["vocals"] = False

        # Optional duration filter (±30% of target, in milliseconds)
        # Multipliers combine ±30% range with seconds→ms: 0.7×1000=700, 1.3×1000=1300
        if target_duration > 0:
            search_kwargs["duration_min"] = int(target_duration * 700)
            search_kwargs["duration_max"] = int(target_duration * 1300)

        results = client.search_music(**search_kwargs)
        if not results:
            logger.info(f"[Epidemic] No results for mood '{mood}', trying without duration filter")
            search_kwargs.pop("duration_min", None)
            search_kwargs.pop("duration_max", None)
            results = client.search_music(**search_kwargs)

        if not results:
            logger.info(f"[Epidemic] No results for mood '{mood}'")
            return None

        # Avoid reusing recently-used tracks across videos (War Room v7 fix)
        _recent_file = MUSIC_DIR / ".recent_tracks.json"
        _recent_ids = set()
        try:
            if _recent_file.exists():
                import json as _json
                _recent_ids = set(_json.loads(_recent_file.read_text()))
        except Exception:
            pass
        # Pick the first result not in recent history
        track = None
        for candidate in results:
            if str(candidate.get("id", "")) not in _recent_ids:
                track = candidate
                break
        if track is None:
            track = results[0]  # fallback if all results are recent
            logger.info(f"[Epidemic] All results for '{mood}' are recent — reusing least-recent")
        track_id = str(track.get("id", ""))
        title = track.get("title", "unknown")
        artist = ""
        if isinstance(track.get("artist"), dict):
            artist = track["artist"].get("name", "")
        elif isinstance(track.get("artist"), str):
            artist = track["artist"]
        bpm = track.get("bpm", 0)

        filename = _sanitize_filename(title, track_id, mood)
        output_path = MUSIC_DIR / filename

        # Check cache — don't re-download
        if output_path.exists() and output_path.stat().st_size > 50000:
            logger.info(f"[Epidemic] Cache hit: {filename}")
            # Still record to recent history even on cache hit (War Room v7 fix)
            try:
                import json as _json
                _recent_ids.add(track_id)
                _recent_list = list(_recent_ids)[-20:]
                _recent_file.write_text(_json.dumps(_recent_list))
            except Exception:
                pass
            return {
                "filename": filename,
                "track_id": track_id,
                "title": title,
                "artist": artist,
                "bpm": bpm,
                "mood": mood,
            }

        # Download
        client.download_track(track_id, output_path)

        if output_path.exists() and output_path.stat().st_size > 50000:
            logger.info(f"[Epidemic] Downloaded: {filename} ({bpm} BPM)")
            # Record track to recent history to avoid reuse across videos
            try:
                import json as _json
                _recent_ids.add(track_id)
                # Keep last 20 tracks to allow cycling
                _recent_list = list(_recent_ids)[-20:]
                _recent_file.write_text(_json.dumps(_recent_list))
            except Exception:
                pass
            return {
                "filename": filename,
                "track_id": track_id,
                "title": title,
                "artist": artist,
                "bpm": bpm,
                "mood": mood,
            }
        else:
            logger.warning(f"[Epidemic] Download too small or failed: {filename}")
            return None

    except Exception as e:
        from clients.epidemic_client import KeyExpiredError
        if isinstance(e, KeyExpiredError):
            logger.warning(f"[Epidemic] API key expired: {e}")
            try:
                from server.notify import _tg
                _tg("⚠️ *Epidemic Sound API key expired*\nRegenerate at epidemicsound.com/account/api-keys")
            except Exception:
                pass
        else:
            logger.warning(f"[Epidemic] Music search failed (falling back to local): {e}")
        return None


def search_for_video(scenes: list[dict], total_duration: float = 600) -> dict | None:
    """Full video-aware search: analyzes dominant mood, selects and downloads best track.

    Returns dict with keys: music_file, music_start_offset, track_id, title, artist, bpm, mood.
    Compatible with music_manager.py return format.
    """
    if not scenes:
        return None

    # Calculate dominant mood weighted by scene duration
    mood_weights: dict[str, float] = {}
    for s in scenes:
        mood = s.get("mood", "dark").lower()
        duration = s.get("end_time", 0) - s.get("start_time", 0)
        mood_weights[mood] = mood_weights.get(mood, 0) + max(duration, 0)

    if not mood_weights:
        return None

    dominant = max(mood_weights, key=mood_weights.get)
    result = search_and_download_for_mood(dominant, target_duration=total_duration)

    if result:
        return {
            "music_file": f"music/{result['filename']}",
            "music_start_offset": 0,
            "track_id": result["track_id"],
            "title": result["title"],
            "artist": result["artist"],
            "bpm": result["bpm"],
            "mood": result["mood"],
        }

    return None

"""
Music Manager — Smart local library selector for The Obsidian Archive.

Scans remotion/public/music/ for available tracks, categorizes by mood,
prioritizes premium (manually-added Epidemic Sound) tracks over free CC tracks,
and rotates selections to avoid repetition across videos.

No external API calls — works entirely from the local library.
"""

from __future__ import annotations
import os
import sys
import json
import random
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR   = Path(__file__).resolve().parent.parent
MUSIC_DIR  = BASE_DIR / "remotion" / "public" / "music"
USAGE_FILE = BASE_DIR / "outputs" / "music_usage.json"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Recognized moods (must match setup_music.py and scene breakdown agent)
MOODS = ["dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"]
DEFAULT_MOOD = "dark"

# Filename prefix → mood mapping for auto-detection
MOOD_PREFIXES = {
    "dark_": "dark",
    "tense_": "tense",
    "dramatic_": "dramatic",
    "cold_": "cold",
    "reverent_": "reverent",
    "wonder_": "wonder",
    "warmth_": "warmth",
    "absurdity_": "absurdity",
}

# Premium track prefixes — files STARTING with these are prioritized
# (Epidemic Sound tracks manually downloaded by user)
PREMIUM_PREFIXES = ["epidemic_", "es_", "premium_", "suno_"]

ANALYSIS_FILE = BASE_DIR / "outputs" / "music_analysis.json"

# Mood → target energy level (0-1) for smart matching
MOOD_ENERGY = {
    "dark": 0.4, "tense": 0.7, "dramatic": 0.9, "cold": 0.3,
    "reverent": 0.5, "wonder": 0.6, "warmth": 0.5, "absurdity": 0.5,
}


# ── Library scanning ─────────────────────────────────────────────────────────

def scan_library() -> dict[str, list[dict]]:
    """
    Scan MUSIC_DIR for all valid MP3 files.
    Returns {mood: [track_info, ...]} where each track_info has:
      filename, path, mood, is_premium, size_kb
    """
    library: dict[str, list[dict]] = {m: [] for m in MOODS}

    for f in sorted(MUSIC_DIR.glob("*.mp3")):
        if f.stat().st_size < 50_000:
            continue  # Skip corrupt/tiny files

        filename = f.name
        mood = _detect_mood(filename)
        is_premium = any(filename.lower().startswith(pfx) for pfx in PREMIUM_PREFIXES)

        library[mood].append({
            "filename": filename,
            "path": str(f),
            "mood": mood,
            "is_premium": is_premium,
            "size_kb": f.stat().st_size // 1024,
        })

    return library


def _detect_mood(filename: str) -> str:
    """Detect mood from filename prefix."""
    lower = filename.lower()
    for prefix, mood in MOOD_PREFIXES.items():
        if lower.startswith(prefix):
            return mood
    # Check if mood name appears anywhere in filename
    for mood in MOODS:
        if mood in lower:
            return mood
    return DEFAULT_MOOD


# ── Usage tracking (rotation) ────────────────────────────────────────────────

def _load_usage() -> dict:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_usage(usage: dict):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def _record_usage(filename: str, mood: str):
    """Record that a track was used, for rotation purposes."""
    usage = _load_usage()
    usage[filename] = {
        "mood": mood,
        "last_used": datetime.now(timezone.utc).isoformat(),
        "use_count": usage.get(filename, {}).get("use_count", 0) + 1,
    }
    _save_usage(usage)


def _get_usage_count(filename: str) -> int:
    usage = _load_usage()
    return usage.get(filename, {}).get("use_count", 0)


# ── Track selection ──────────────────────────────────────────────────────────

def _select_track(tracks: list[dict]) -> dict | None:
    """
    Pick the best track from a mood's available list.
    Priority: premium tracks first, then least-recently-used among free tracks.
    """
    if not tracks:
        return None

    # Split into premium and free
    premium = [t for t in tracks if t["is_premium"]]
    free = [t for t in tracks if not t["is_premium"]]

    # Try premium first (least used)
    pool = premium if premium else free
    if not pool:
        return None

    # Load usage once to avoid repeated disk reads
    usage = _load_usage()

    def _usage_count(filename: str) -> int:
        return usage.get(filename, {}).get("use_count", 0)

    # Sort by usage count (ascending) so least-used tracks come first
    pool_sorted = sorted(pool, key=lambda t: _usage_count(t["filename"]))

    # Among tracks with the same lowest usage count, pick randomly
    min_usage = _usage_count(pool_sorted[0]["filename"])
    least_used = [t for t in pool_sorted if _usage_count(t["filename"]) == min_usage]

    return random.choice(least_used)


def get_music_for_mood(mood: str, target_duration: float = 600) -> str | None:
    """
    Get a background music file for a given mood.
    Returns the filename relative to remotion/public/ (e.g., "music/dark_01_scp_x1x.mp3")
    or None if no tracks available for that mood.

    Priority: Epidemic Sound API → local premium → local free → fallback mood.
    """
    mood = mood.lower() if mood else DEFAULT_MOOD
    if mood not in MOODS:
        mood = DEFAULT_MOOD

    # Try Epidemic Sound API first (if key configured)
    if os.getenv("EPIDEMIC_SOUND_API_KEY"):
        try:
            from media.epidemic_music_manager import search_and_download_for_mood
            result = search_and_download_for_mood(mood, target_duration)
            if result:
                _record_usage(result["filename"], mood)
                print(f"[Music] Selected (EPIDEMIC API): {result['filename']} for mood '{mood}'")
                return f"music/{result['filename']}"
        except Exception as e:
            print(f"[Music] Epidemic Sound API unavailable: {e}")

    library = scan_library()
    tracks = library.get(mood, [])

    if not tracks:
        # Fallback: try default mood
        if mood != DEFAULT_MOOD:
            print(f"[Music] No tracks for '{mood}', falling back to '{DEFAULT_MOOD}'")
            tracks = library.get(DEFAULT_MOOD, [])
        if not tracks:
            print("[Music] No tracks available at all")
            return None

    track = _select_track(tracks)
    if not track:
        return None

    _record_usage(track["filename"], mood)
    prefix = "PREMIUM" if track["is_premium"] else "free"
    print(f"[Music] Selected ({prefix}): {track['filename']} for mood '{mood}' ({track['size_kb']} KB)")
    return f"music/{track['filename']}"


def get_secondary_music(primary_mood: str, scenes: list[dict], primary_track: str | None = None) -> str | None:
    """
    Select a secondary music track for Act 3 crossfade.
    Picks a contrasting mood — if primary is tense, secondary is reverent/cold.
    Avoids selecting the same file as the primary track.
    Returns filename relative to remotion/public/ or None.
    """
    # Mood contrast pairs for dramatic crossfade
    contrast_map = {
        "dark": ["reverent", "cold"],
        "tense": ["reverent", "dramatic"],
        "dramatic": ["cold", "reverent"],
        "cold": ["warmth", "reverent"],
        "reverent": ["dark", "cold"],
        "wonder": ["dark", "reverent"],
        "warmth": ["cold", "dark"],
        "absurdity": ["dark", "tense"],
    }
    candidates = contrast_map.get(primary_mood, ["reverent"])
    for mood in candidates:
        track = get_music_for_mood(mood)
        if track and track != primary_track:
            print(f"[Music] Secondary track (Act 3 crossfade): {track} (mood: {mood})")
            return track
    return None


def get_music_for_video(scenes: list[dict], total_duration: float = 600) -> str | None:
    """
    Select a single background music track for the entire video.
    Picks the dominant mood from scenes and finds a matching track.

    Returns filename relative to remotion/public/ or None.
    """
    if not scenes:
        return get_music_for_mood(DEFAULT_MOOD, total_duration)

    # Count mood frequency across scenes (weighted by duration)
    mood_counts: dict[str, float] = {}
    for scene in scenes:
        mood = (scene.get("mood", "") or DEFAULT_MOOD).lower()
        dur = (scene.get("end_time", 0) or 0) - (scene.get("start_time", 0) or 0)
        mood_counts[mood] = mood_counts.get(mood, 0) + max(dur, 1)

    dominant_mood = max(mood_counts, key=mood_counts.get) if mood_counts else DEFAULT_MOOD
    print(f"[Music] Dominant mood: {dominant_mood} ({mood_counts.get(dominant_mood, 0):.0f}s of {total_duration:.0f}s)")

    return get_music_for_mood(dominant_mood, total_duration)


# ── Smart selection (energy-curve matched) ──────────────────────────────────

def _load_analysis() -> dict:
    """Load pre-computed track analysis data."""
    if ANALYSIS_FILE.exists():
        try:
            data = json.loads(ANALYSIS_FILE.read_text())
            return data.get("tracks", {})
        except Exception:
            return {}
    return {}


def _build_video_energy_arc(scenes: list[dict], total_duration: float) -> list[float]:
    """Build target energy curve from scene moods (one value per 10-second window)."""
    window_sec = 10.0
    n_windows = max(1, int(total_duration / window_sec) + 1)
    arc = [0.0] * n_windows

    for scene in scenes:
        mood = (scene.get("mood", "") or "dark").lower()
        energy = MOOD_ENERGY.get(mood, 0.5)
        start = scene.get("start_time", 0) or 0
        end = scene.get("end_time", 0) or 0

        # Boost energy for reveal moments
        if scene.get("is_reveal_moment"):
            energy = min(1.0, energy + 0.2)
        # Lower energy for breathing room
        if scene.get("is_breathing_room"):
            energy = max(0.1, energy - 0.2)

        start_win = int(start / window_sec)
        end_win = int(end / window_sec) + 1
        for w in range(max(0, start_win), min(n_windows, end_win)):
            arc[w] = energy

    return arc


def _pearson_correlation(a: list[float], b: list[float]) -> float:
    """Compute Pearson correlation between two lists. Returns -1 to 1."""
    n = min(len(a), len(b))
    if n < 3:
        return 0.0

    a, b = a[:n], b[:n]
    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    std_a = (sum((x - mean_a) ** 2 for x in a)) ** 0.5
    std_b = (sum((x - mean_b) ** 2 for x in b)) ** 0.5

    if std_a < 1e-9 or std_b < 1e-9:
        return 0.0

    return cov / (std_a * std_b)


def _score_track(track_curve: list[float], video_arc: list[float],
                 track_duration: float, video_duration: float) -> tuple[float, float]:
    """
    Score a track against the video's energy arc.
    Returns (best_correlation, best_start_offset_seconds).
    Tries different start offsets to find optimal alignment.
    """
    window_sec = 10.0
    arc_len = len(video_arc)

    # If track is shorter than video, tile the energy curve
    if len(track_curve) < arc_len:
        reps = (arc_len // len(track_curve)) + 2
        extended = (track_curve * reps)[:arc_len * 2]
    else:
        extended = track_curve

    best_corr = -2.0
    best_offset = 0.0

    # Try offsets in 10-second steps
    max_offset_windows = max(0, len(extended) - arc_len)
    step = 1  # 10-second steps

    for offset_win in range(0, max_offset_windows + 1, step):
        segment = extended[offset_win:offset_win + arc_len]
        if len(segment) < arc_len:
            break
        corr = _pearson_correlation(video_arc, segment)
        if corr > best_corr:
            best_corr = corr
            best_offset = offset_win * window_sec

    return best_corr, best_offset


def get_smart_music_for_video(scenes: list[dict], total_duration: float = 600) -> dict | None:
    """
    Select the best-matching track using energy curve correlation.
    Returns dict with music_file, music_start_offset, correlation_score,
    or None if no analysis data available (caller should fall back to get_music_for_video).
    """
    analysis = _load_analysis()
    if not analysis:
        print("[Music] No analysis data — run 'python analyze_music.py' first")
        return None

    # Build target energy arc from scenes
    if not scenes:
        return None
    video_arc = _build_video_energy_arc(scenes, total_duration)

    # Get dominant mood for filtering candidates
    mood_counts: dict[str, float] = {}
    for scene in scenes:
        mood = (scene.get("mood", "") or "dark").lower()
        dur = (scene.get("end_time", 0) or 0) - (scene.get("start_time", 0) or 0)
        mood_counts[mood] = mood_counts.get(mood, 0) + max(dur, 1)
    dominant_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "dark"
    if dominant_mood not in MOODS:
        dominant_mood = "dark"

    # Scan library
    library = scan_library()

    # Collect candidate tracks: dominant mood + neighboring moods
    candidate_moods = [dominant_mood]
    # Add related moods for broader selection
    related = {
        "dark": ["tense", "cold"], "tense": ["dark", "dramatic"],
        "dramatic": ["tense", "dark"], "cold": ["dark", "reverent"],
        "reverent": ["cold", "warmth"], "wonder": ["reverent", "dramatic"],
        "warmth": ["reverent", "wonder"], "absurdity": ["warmth", "wonder"],
    }
    candidate_moods.extend(related.get(dominant_mood, []))

    candidates = []
    for mood in candidate_moods:
        candidates.extend(library.get(mood, []))

    if not candidates:
        return None

    # Split premium / free
    premium = [t for t in candidates if t["is_premium"]]
    free = [t for t in candidates if not t["is_premium"]]
    pool = premium if premium else free

    # Read optimizer-tuned music params (self-tunes from YouTube retention)
    try:
        from core.param_overrides import get_override
        _corr_weight = get_override("music.energy_correlation_weight", 0.7)
        _usage_penalty = get_override("music.usage_penalty", 0.02)
    except Exception:
        _corr_weight = 0.7
        _usage_penalty = 0.02

    # Score each track
    usage = _load_usage()
    scored = []
    for track in pool:
        fname = track["filename"]
        if fname not in analysis:
            continue
        info = analysis[fname]
        curve = info.get("energy_curve", [])
        dur = info.get("duration_seconds", 0)
        if not curve or dur < 30:
            continue

        corr, offset = _score_track(curve, video_arc, dur, total_duration)

        # Weight correlation by optimizer-tuned importance
        corr *= _corr_weight

        # Penalty for heavily used tracks (optimizer-tuned per-use penalty, max -0.1)
        use_count = usage.get(fname, {}).get("use_count", 0)
        corr -= min(use_count * _usage_penalty, 0.1)

        scored.append({
            "track": track,
            "correlation": corr,
            "start_offset": offset,
            "duration": dur,
        })

    if not scored:
        print("[Music] No tracks with analysis data — falling back to random")
        return None

    # Pick the best
    scored.sort(key=lambda x: x["correlation"], reverse=True)
    winner = scored[0]
    track = winner["track"]

    _record_usage(track["filename"], dominant_mood)

    prefix = "PREMIUM" if track["is_premium"] else "free"
    music_file = f"music/{track['filename']}"
    print(f"[Music] Smart select ({prefix}): {track['filename']}")
    print(f"[Music]   Correlation: {winner['correlation']:.3f}, "
          f"Start offset: {winner['start_offset']:.0f}s, "
          f"Track duration: {winner['duration']:.0f}s")

    if len(scored) > 1:
        runner_up = scored[1]
        print(f"[Music]   Runner-up: {runner_up['track']['filename']} "
              f"(corr: {runner_up['correlation']:.3f})")

    return {
        "music_file": music_file,
        "music_start_offset": winner["start_offset"],
        "correlation_score": winner["correlation"],
    }


def get_smart_secondary_music(primary_mood: str, scenes: list[dict],
                               primary_track: str | None = None,
                               total_duration: float = 600) -> dict | None:
    """
    Select a secondary track for Act 3 crossfade using energy matching.
    Only considers the last 35% of the video for arc matching.
    Returns dict with music_file, music_start_offset, correlation_score, or None.
    """
    analysis = _load_analysis()
    if not analysis:
        return None

    # Build energy arc for Act 3 only (last 35%)
    act3_start = total_duration * 0.65
    act3_scenes = [s for s in scenes if (s.get("end_time", 0) or 0) > act3_start]
    if not act3_scenes:
        return None

    act3_duration = total_duration - act3_start
    video_arc = _build_video_energy_arc(act3_scenes, act3_duration)

    # Use contrasting moods
    contrast_map = {
        "dark": ["reverent", "cold"], "tense": ["reverent", "dramatic"],
        "dramatic": ["cold", "reverent"], "cold": ["warmth", "reverent"],
        "reverent": ["dark", "cold"], "wonder": ["dark", "reverent"],
        "warmth": ["cold", "dark"], "absurdity": ["dark", "tense"],
    }
    target_moods = contrast_map.get(primary_mood, ["reverent"])

    library = scan_library()
    candidates = []
    for mood in target_moods:
        candidates.extend(library.get(mood, []))

    # Exclude primary track
    if primary_track:
        primary_fname = primary_track.replace("music/", "")
        candidates = [t for t in candidates if t["filename"] != primary_fname]

    premium = [t for t in candidates if t["is_premium"]]
    free = [t for t in candidates if not t["is_premium"]]
    pool = premium if premium else free

    scored = []
    for track in pool:
        fname = track["filename"]
        if fname not in analysis:
            continue
        info = analysis[fname]
        curve = info.get("energy_curve", [])
        dur = info.get("duration_seconds", 0)
        if not curve or dur < 20:
            continue

        corr, offset = _score_track(curve, video_arc, dur, act3_duration)
        scored.append({
            "track": track,
            "correlation": corr,
            "start_offset": offset,
        })

    if not scored:
        return None

    scored.sort(key=lambda x: x["correlation"], reverse=True)
    winner = scored[0]
    track = winner["track"]

    _record_usage(track["filename"], track["mood"])
    music_file = f"music/{track['filename']}"
    print(f"[Music] Smart secondary: {track['filename']} (corr: {winner['correlation']:.3f}, "
          f"offset: {winner['start_offset']:.0f}s)")

    return {
        "music_file": music_file,
        "music_start_offset": winner["start_offset"],
        "correlation_score": winner["correlation"],
    }


# ── Prefetch (ensures setup_music.py has run) ────────────────────────────────

def prefetch_all_moods():
    """Ensure tracks exist for all moods. Runs setup_music if library is sparse."""
    library = scan_library()
    total = sum(len(v) for v in library.values())

    if total < len(MOODS):
        print("[Music] Library sparse — running setup_music.py...")
        try:
            from scripts import setup_music
            setup_music.run()
        except Exception as e:
            print(f"[Music] setup_music failed: {e}")

    # Re-scan
    library = scan_library()
    for mood in MOODS:
        count = len(library.get(mood, []))
        premium = sum(1 for t in library.get(mood, []) if t["is_premium"])
        print(f"[Music]   {mood}: {count} tracks ({premium} premium)")

    total = sum(len(v) for v in library.values())
    print(f"[Music] Library ready: {total} tracks across {len(MOODS)} moods")
    return total


# ── Attribution ──────────────────────────────────────────────────────────────

def get_attribution() -> str:
    """Return attribution text for video description."""
    library = scan_library()
    has_premium = any(t["is_premium"] for tracks in library.values() for t in tracks)
    has_free = any(not t["is_premium"] for tracks in library.values() for t in tracks)

    lines = []
    if has_premium:
        lines.append("Music licensed from Epidemic Sound (epidemicsound.com)")
    if has_free:
        lines.append(
            "Music by Kevin MacLeod (incompetech.com) — "
            "Licensed under Creative Commons: By Attribution 4.0"
        )
    return "\n".join(lines)


def get_track_info(mood: str) -> dict | None:
    """Return info about available tracks for a mood."""
    library = scan_library()
    tracks = library.get(mood.lower(), [])
    if not tracks:
        return None
    return {
        "mood": mood,
        "available": len(tracks),
        "premium": sum(1 for t in tracks if t["is_premium"]),
        "tracks": [t["filename"] for t in tracks],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Music library manager")
    parser.add_argument("--scan", action="store_true", help="Scan and show library")
    parser.add_argument("--select", metavar="MOOD", help="Select a track for a mood")
    parser.add_argument("--prefetch", action="store_true", help="Ensure all moods have tracks")
    parser.add_argument("--attribution", action="store_true", help="Show attribution text")
    parser.add_argument("--usage", action="store_true", help="Show usage stats")
    args = parser.parse_args()

    if args.scan:
        lib = scan_library()
        for mood, tracks in lib.items():
            print(f"\n  {mood.upper()} ({len(tracks)} tracks):")
            for t in tracks:
                tag = " [PREMIUM]" if t["is_premium"] else ""
                uses = _get_usage_count(t["filename"])
                print(f"    {t['filename']}{tag} — {t['size_kb']} KB, used {uses}x")
    elif args.select:
        result = get_music_for_mood(args.select)
        print(f"  -> {result}" if result else "  -> No tracks available")
    elif args.prefetch:
        prefetch_all_moods()
    elif args.attribution:
        print(get_attribution())
    elif args.usage:
        usage = _load_usage()
        if not usage:
            print("  No usage history yet")
        for fn, info in sorted(usage.items(), key=lambda x: x[1].get("use_count", 0), reverse=True):
            print(f"  {fn}: {info['use_count']}x (last: {info['last_used'][:10]})")
    else:
        parser.print_help()

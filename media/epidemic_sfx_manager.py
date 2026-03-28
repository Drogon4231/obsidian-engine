"""
Epidemic Sound SFX manager — per-scene sound effect and ambient selection.

Searches the Epidemic Sound SFX catalog based on scene mood + narrative function,
downloads to local cache, and falls back gracefully to local Pixabay files.

Caches by mood per pipeline run to avoid redundant API calls.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SFX_DIR = BASE_DIR / "remotion" / "public" / "sfx"
AMBIENCE_DIR = BASE_DIR / "remotion" / "public" / "ambience"
SFX_DIR.mkdir(parents=True, exist_ok=True)
AMBIENCE_DIR.mkdir(parents=True, exist_ok=True)

# ── Scene → SFX search query mapping ─────────────────────────────────────────

SFX_QUERY_MAP = {
    ("dark", "reveal"):       "horror reveal sting dark",
    ("dark", "climax"):       "dark suspense hit impact",
    ("dark", "twist"):        "dark whoosh transition eerie",
    ("tense", "reveal"):      "tension riser suspense reveal",
    ("tense", "climax"):      "intense impact hit thriller",
    ("tense", "act"):         "tension riser suspense build",
    ("dramatic", "reveal"):   "dramatic boom impact epic",
    ("dramatic", "climax"):   "dramatic orchestral hit cinematic",
    ("dramatic", "twist"):    "dramatic reveal sting epic",
    ("cold", "reveal"):       "cold wind gust eerie reveal",
    ("cold", "climax"):       "frozen impact icy hit",
    ("reverent", "reveal"):   "church bell sacred solemn",
    ("reverent", "climax"):   "sacred choir hit ethereal",
    ("wonder", "reveal"):     "magical shimmer discovery awe",
    ("wonder", "climax"):     "wonder awe cosmic reveal",
    ("wonder", "exposition"): "gentle shimmer magical discovery",
    ("warmth", "reveal"):     "gentle chime warm reveal",
    ("warmth", "climax"):     "emotional swell heartfelt",
    ("warmth", "breathing_room"): "gentle wind chimes peaceful",
    ("absurdity", "reveal"):  "comedic twist quirky reveal",
    ("absurdity", "climax"):  "funny impact cartoon hit",
    ("absurdity", "twist"):   "comedic whoosh quirky surprise",
}

# Fallback: mood-only queries when narrative function doesn't match
SFX_MOOD_FALLBACK = {
    "dark":      "dark suspense hit",
    "tense":     "tension impact hit",
    "dramatic":  "dramatic boom impact",
    "cold":      "cold icy whoosh",
    "reverent":  "sacred bell chime",
    "wonder":    "magical shimmer awe",
    "warmth":    "gentle chime warm",
    "absurdity": "quirky comedic hit",
}

# ── Ambient search queries per mood ──────────────────────────────────────────

AMBIENT_QUERY_MAP = {
    "dark":      "dark cave wind ambience atmospheric",
    "tense":     "heartbeat tension drone suspense",
    "dramatic":  "low rumble cinematic atmospheric",
    "cold":      "cold wind howling arctic desolate",
    "reverent":  "cathedral reverb atmosphere sacred",
    "wonder":    "vast space cosmic awe atmospheric",
    "warmth":    "gentle fire crackling hearth warm",
    "absurdity": "carnival fairground quirky ambient",
}

# ── Session cache (avoid re-downloading same mood per pipeline run) ───────────

_sfx_cache: dict[str, str] = {}
_ambient_cache: dict[str, str] = {}


def clear_session_cache():
    """Reset per-run caches. Called at pipeline start."""
    _sfx_cache.clear()
    _ambient_cache.clear()


def _get_client():
    """Lazy import."""
    from clients.epidemic_client import EpidemicSoundClient
    return EpidemicSoundClient()


def _build_sfx_query(scene: dict) -> str:
    """Build a search query from scene attributes."""
    mood = scene.get("mood", "dark").lower()
    narrative_fn = scene.get("narrative_function", "")
    transition = scene.get("intent_transition_type", "")

    # Try specific (mood, function) combo first
    for fn_key in (narrative_fn, transition):
        query = SFX_QUERY_MAP.get((mood, fn_key))
        if query:
            return query

    # If reveal moment, use reveal combo
    if scene.get("is_reveal_moment"):
        query = SFX_QUERY_MAP.get((mood, "reveal"))
        if query:
            return query

    # Fallback: mood-only
    return SFX_MOOD_FALLBACK.get(mood, "cinematic hit impact")


def get_sfx_for_scene(scene: dict) -> str | None:
    """Search Epidemic Sound for an SFX matching the scene context.

    Returns path relative to remotion/public/ (e.g., "sfx/epidemic_sfx_abc.mp3") or None.
    """
    if not os.getenv("EPIDEMIC_SOUND_API_KEY"):
        return None

    query = _build_sfx_query(scene)
    cache_key = query  # Each unique query gets cached

    if cache_key in _sfx_cache:
        return _sfx_cache[cache_key]

    try:
        client = _get_client()
        results = client.search_sfx(keyword=query, duration_max=5.0, limit=3)
        if not results:
            return None

        sfx = results[0]
        sfx_id = str(sfx.get("id", ""))
        title = sfx.get("title", "unknown")

        import re
        safe_title = re.sub(r'[^a-z0-9]+', '_', title.lower())[:30]
        filename = f"epidemic_sfx_{safe_title}_{sfx_id}.mp3"
        output_path = SFX_DIR / filename

        if not output_path.exists() or output_path.stat().st_size < 5000:
            client.download_sfx(sfx_id, output_path)

        if output_path.exists() and output_path.stat().st_size >= 5000:
            result_path = f"sfx/{filename}"
            _sfx_cache[cache_key] = result_path
            logger.info(f"[SFX] Downloaded: {filename} for '{query}'")
            return result_path

    except Exception as e:
        from clients.epidemic_client import KeyExpiredError
        if isinstance(e, KeyExpiredError):
            logger.warning(f"[SFX] API key expired: {e}")
        else:
            logger.warning(f"[SFX] Search failed: {e}")

    return None


def get_ambient_for_scene(scene: dict) -> str | None:
    """Search Epidemic Sound for ambient audio matching the scene mood.

    Returns path relative to remotion/public/ (e.g., "ambience/epidemic_amb_abc.mp3") or None.
    Caches by mood — reuses same ambient across scenes with same mood.
    """
    if not os.getenv("EPIDEMIC_SOUND_API_KEY"):
        return None

    mood = scene.get("mood", "dark").lower()

    if mood in _ambient_cache:
        return _ambient_cache[mood]

    query = AMBIENT_QUERY_MAP.get(mood, "atmospheric ambient background")

    try:
        client = _get_client()
        results = client.search_sfx(keyword=query, duration_max=30.0, limit=3)
        if not results:
            return None

        amb = results[0]
        amb_id = str(amb.get("id", ""))
        filename = f"epidemic_amb_{mood}_{amb_id}.mp3"
        output_path = AMBIENCE_DIR / filename

        if not output_path.exists() or output_path.stat().st_size < 5000:
            client.download_sfx(amb_id, output_path)

        if output_path.exists() and output_path.stat().st_size >= 5000:
            result_path = f"ambience/{filename}"
            _ambient_cache[mood] = result_path
            logger.info(f"[Ambient] Downloaded: {filename} for mood '{mood}'")
            return result_path

    except Exception as e:
        from clients.epidemic_client import KeyExpiredError
        if isinstance(e, KeyExpiredError):
            logger.warning(f"[Ambient] API key expired: {e}")
        else:
            logger.warning(f"[Ambient] Search failed: {e}")

    return None

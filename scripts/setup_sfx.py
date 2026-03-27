"""
SFX setup — downloads CC0 one-shot sound effects for scene punctuation.
Called automatically on first run by scheduler.py.
Safe to re-run: skips files that already exist.

All sounds are CC0 / Pixabay License (free for commercial use).
"""

import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

SFX_DIR = Path(__file__).resolve().parent.parent / "remotion" / "public" / "sfx"
SFX_DIR.mkdir(parents=True, exist_ok=True)

# Mood-keyed SFX — one-shot sound effects that punctuate key moments.
# Each mood maps to a short (1-5s) sound effect played once at scene start.
SFX_TRACKS = {
    "tense": {
        "file": "sfx_tense.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/03/24/audio_4adb0e1edb.mp3",
        "desc": "Low tension hit / impact",
    },
    "dramatic": {
        "file": "sfx_dramatic.mp3",
        "url": "https://cdn.pixabay.com/audio/2021/08/04/audio_c0409498cf.mp3",
        "desc": "Dramatic boom / reveal sting",
    },
    "dark": {
        "file": "sfx_dark.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/10/30/audio_42cb0a9b09.mp3",
        "desc": "Dark whoosh / transition",
    },
    "cold": {
        "file": "sfx_cold.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/01/20/audio_7a67e06ced.mp3",
        "desc": "Cold wind gust",
    },
    "reverent": {
        "file": "sfx_reverent.mp3",
        "url": "https://cdn.pixabay.com/audio/2024/09/20/audio_926db0de3e.mp3",
        "desc": "Soft bell / chime tone",
    },
}


def download(mood: str, info: dict) -> bool:
    dest = SFX_DIR / info["file"]
    if dest.exists() and dest.stat().st_size > 5_000:
        print(f"[SFX] Already have: {info['file']}")
        return True
    print(f"[SFX] Downloading: {info['desc']} -> {info['file']}")
    try:
        r = requests.get(info["url"], timeout=30, stream=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 5_000:
            dest.write_bytes(r.content)
            size_kb = dest.stat().st_size // 1024
            print(f"[SFX] Downloaded {info['file']} ({size_kb} KB)")
            return True
        print(f"[SFX] Failed: HTTP {r.status_code} or too small")
        return False
    except Exception as e:
        print(f"[SFX] Failed: {e}")
        return False


def run():
    print("[SFX] Checking sound effect files...")
    ok = 0
    for mood, info in SFX_TRACKS.items():
        if download(mood, info):
            ok += 1
        time.sleep(0.5)

    attr_path = SFX_DIR / "ATTRIBUTION.txt"
    if not attr_path.exists():
        attr_path.write_text(
            "Sound effects sourced from Pixabay (pixabay.com)\n"
            "Licensed under Pixabay Content License (free for commercial use)\n\n"
            "Tracks:\n" +
            "\n".join(f"  {info['file']} — {info['desc']}" for info in SFX_TRACKS.values())
        )

    print(f"[SFX] Setup complete: {ok}/{len(SFX_TRACKS)} tracks available")
    return ok > 0


def get_sfx_file(mood: str) -> str:
    """Return the SFX filename for a mood, or empty string if not available."""
    info = SFX_TRACKS.get(mood)
    if info:
        path = SFX_DIR / info["file"]
        if path.exists():
            return f"sfx/{info['file']}"
    return ""


def should_play_sfx(scene: dict) -> bool:
    """Decide if a scene warrants an SFX hit.

    Plays SFX on:
    - Reveal moments
    - Act transitions (narrative_position starts with 'act')
    - Scenes tagged as dramatic/tense mood
    - Scenes with is_breathing_room (subtle SFX to fill silence)
    """
    if scene.get("is_reveal_moment"):
        return True
    narrative_fn = scene.get("narrative_function", "")
    if narrative_fn in ("climax", "twist", "reveal"):
        return True
    intent = scene.get("intent_transition_type", "")
    if intent in ("act", "reveal"):
        return True
    return False


if __name__ == "__main__":
    run()

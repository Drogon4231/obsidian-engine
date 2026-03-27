"""
Ambient sound setup — downloads CC0 ambient loops for scene atmosphere.
Called automatically on first run by scheduler.py.
Safe to re-run: skips files that already exist.

All sounds are CC0 (public domain) from Freesound.org or similar.
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

AMBIENCE_DIR = Path(__file__).resolve().parent.parent / "remotion" / "public" / "ambience"
AMBIENCE_DIR.mkdir(parents=True, exist_ok=True)

# Mood-keyed ambient loops — CC0 sources
# These are short (10-30s) seamless loops that Remotion will loop per scene
AMBIENT_TRACKS = {
    "dark": {
        "file": "amb_dark.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/10/30/audio_42cb0a9b09.mp3",
        "desc": "Dark cave wind ambience",
    },
    "tense": {
        "file": "amb_tense.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/03/15/audio_dce8bb4b68.mp3",
        "desc": "Tense heartbeat drone",
    },
    "dramatic": {
        "file": "amb_dramatic.mp3",
        "url": "https://cdn.pixabay.com/audio/2024/11/10/audio_84a5e7a1f9.mp3",
        "desc": "Dramatic low rumble",
    },
    "cold": {
        "file": "amb_cold.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/01/20/audio_7a67e06ced.mp3",
        "desc": "Cold wind howling",
    },
    "reverent": {
        "file": "amb_reverent.mp3",
        "url": "https://cdn.pixabay.com/audio/2024/09/20/audio_926db0de3e.mp3",
        "desc": "Cathedral reverb atmosphere",
    },
}


def download(mood: str, info: dict) -> bool:
    dest = AMBIENCE_DIR / info["file"]
    if dest.exists() and dest.stat().st_size > 10_000:
        print(f"[Ambience] Already have: {info['file']}")
        return True
    print(f"[Ambience] Downloading: {info['desc']} -> {info['file']}")
    try:
        r = requests.get(info["url"], timeout=30, stream=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 10_000:
            dest.write_bytes(r.content)
            size_kb = dest.stat().st_size // 1024
            print(f"[Ambience] Downloaded {info['file']} ({size_kb} KB)")
            return True
        print(f"[Ambience] Failed: HTTP {r.status_code} or too small")
        return False
    except Exception as e:
        print(f"[Ambience] Failed: {e}")
        return False


def run():
    print("[Ambience] Checking ambient sound loops...")
    ok = 0
    for mood, info in AMBIENT_TRACKS.items():
        if download(mood, info):
            ok += 1
        time.sleep(0.5)

    # Write attribution
    attr_path = AMBIENCE_DIR / "ATTRIBUTION.txt"
    if not attr_path.exists():
        attr_path.write_text(
            "Ambient sounds sourced from Pixabay (pixabay.com)\n"
            "Licensed under Pixabay Content License (free for commercial use)\n\n"
            "Tracks:\n" +
            "\n".join(f"  {info['file']} — {info['desc']}" for info in AMBIENT_TRACKS.values())
        )

    print(f"[Ambience] Setup complete: {ok}/{len(AMBIENT_TRACKS)} tracks available")
    return ok > 0


# Mood -> filename mapping for use by run_pipeline.py
def get_ambient_file(mood: str) -> str:
    """Return the ambient filename for a mood, or empty string if not available."""
    info = AMBIENT_TRACKS.get(mood, AMBIENT_TRACKS.get("dark"))
    if info:
        path = AMBIENCE_DIR / info["file"]
        if path.exists():
            return f"ambience/{info['file']}"
    return ""


if __name__ == "__main__":
    run()

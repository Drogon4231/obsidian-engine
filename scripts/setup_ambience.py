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
    "wonder": {
        "file": "amb_wonder.mp3",
        "url": "https://cdn.pixabay.com/audio/2024/02/14/audio_8f2e2d12f7.mp3",
        "desc": "Ethereal cosmic atmosphere",
    },
    "warmth": {
        "file": "amb_warmth.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/08/02/audio_884fe92c21.mp3",
        "desc": "Gentle fireplace crackling",
    },
    "absurdity": {
        "file": "amb_absurdity.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/10/12/audio_be9768d39e.mp3",
        "desc": "Quirky carnival atmosphere",
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
    # Download architectural ambient tracks
    for arch_key, info in ARCHITECTURE_TRACKS.items():
        if download(arch_key, info):
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


# ── Architectural / Location Ambient Tracks ──────────────────────────────────
# Override mood-based ambient when the scene has specific location context.
# These create period-accurate spatial atmosphere.

ARCHITECTURE_TRACKS = {
    "stone_interior": {
        "file": "amb_stone_chamber.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/12/22/audio_0eede79f2e.mp3",
        "desc": "Stone chamber reverb with distant echoes",
        "keywords": ["palace", "chamber", "throne", "temple", "court", "hall", "dungeon", "crypt",
                      "monastery", "cathedral", "fortress", "castle", "citadel", "tower"],
    },
    "outdoor_marketplace": {
        "file": "amb_marketplace.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/10/21/audio_be4f3f54f0.mp3",
        "desc": "Outdoor marketplace crowd murmur",
        "keywords": ["market", "bazaar", "agora", "forum", "square", "street", "village", "town"],
    },
    "nature_wind": {
        "file": "amb_open_wind.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/05/31/audio_06cc5b5c3e.mp3",
        "desc": "Open field wind with distant birds",
        "keywords": ["field", "plain", "desert", "mountain", "river", "coast", "sea", "ocean",
                      "forest", "jungle", "garden", "valley", "steppe", "savanna"],
    },
    "military_camp": {
        "file": "amb_military.mp3",
        "url": "https://cdn.pixabay.com/audio/2022/01/18/audio_98ccf14d31.mp3",
        "desc": "Distant military camp — horses, metal, murmur",
        "keywords": ["army", "military", "camp", "siege", "battle", "war", "legion",
                      "troops", "soldiers", "barracks", "march"],
    },
}


# Mood -> filename mapping for use by run_pipeline.py
def get_ambient_file(mood: str, location: str = "", visual_desc: str = "") -> str:
    """Return the ambient filename for a scene, preferring location-based over mood-based.

    Priority: architectural match (from location/visual_desc keywords) → mood fallback.
    """
    # Try architectural match first
    if location or visual_desc:
        search_text = (location + " " + visual_desc).lower()
        for arch_key, info in ARCHITECTURE_TRACKS.items():
            if any(kw in search_text for kw in info["keywords"]):
                path = AMBIENCE_DIR / info["file"]
                if path.exists():
                    return f"ambience/{info['file']}"

    # Fallback to mood-based
    info = AMBIENT_TRACKS.get(mood, AMBIENT_TRACKS.get("dark"))
    if info:
        path = AMBIENCE_DIR / info["file"]
        if path.exists():
            return f"ambience/{info['file']}"
    return ""


if __name__ == "__main__":
    run()

"""
Music setup — downloads CC-licensed background tracks for The Obsidian Archive.

Sources:
  - Kevin MacLeod (incompetech.com) — CC BY 4.0
  - Internet Archive mirrors as fallbacks

Called automatically on first run by scheduler.py.
Safe to re-run: skips files that already exist.

Attribution (required by CC BY 4.0):
  Music by Kevin MacLeod (incompetech.com)
  Licensed under Creative Commons: By Attribution 4.0 License
  http://creativecommons.org/licenses/by/4.0/
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

MUSIC_DIR = Path(__file__).resolve().parent.parent / "remotion" / "public" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Track library: 3-5 tracks per mood ──────────────────────────────────────
# Format: filename → (primary_url, title, artist, mood)
# Filenames follow pattern: {mood}_{index}_{slug}.mp3

INCOMPETECH = "https://incompetech.com/music/royalty-free/mp3-royaltyfree"
ARCHIVE = "https://archive.org/download"

TRACKS = {
    # ── DARK (ominous, foreboding, horror-adjacent) ──────────────────────────
    "dark_01_scp_x1x.mp3": (
        f"{INCOMPETECH}/SCP-x1x.mp3",
        "SCP-x1x (Gateway to Hell)", "Kevin MacLeod", "dark",
    ),
    "dark_02_darkest_child.mp3": (
        f"{INCOMPETECH}/Darkest%20Child.mp3",
        "Darkest Child", "Kevin MacLeod", "dark",
    ),
    "dark_03_crypto.mp3": (
        f"{INCOMPETECH}/Crypto.mp3",
        "Crypto", "Kevin MacLeod", "dark",
    ),
    "dark_04_heart_of_nowhere.mp3": (
        f"{INCOMPETECH}/Heart%20of%20Nowhere.mp3",
        "Heart of Nowhere", "Kevin MacLeod", "dark",
    ),

    # ── TENSE (suspense, building anxiety, thriller) ─────────────────────────
    "tense_01_stay_the_course.mp3": (
        f"{INCOMPETECH}/Stay%20the%20Course.mp3",
        "Stay the Course", "Kevin MacLeod", "tense",
    ),
    "tense_02_anxiety.mp3": (
        f"{INCOMPETECH}/Anxiety.mp3",
        "Anxiety", "Kevin MacLeod", "tense",
    ),
    "tense_03_volatile_reaction.mp3": (
        f"{INCOMPETECH}/Volatile%20Reaction.mp3",
        "Volatile Reaction", "Kevin MacLeod", "tense",
    ),
    "tense_04_immersed.mp3": (
        f"{INCOMPETECH}/Immersed.mp3",
        "Immersed", "Kevin MacLeod", "tense",
    ),

    # ── DRAMATIC (epic, powerful, cinematic) ─────────────────────────────────
    "dramatic_01_strength_of_titans.mp3": (
        f"{INCOMPETECH}/Strength%20of%20the%20Titans.mp3",
        "Strength of the Titans", "Kevin MacLeod", "dramatic",
    ),
    "dramatic_02_heroic_age.mp3": (
        f"{INCOMPETECH}/Heroic%20Age.mp3",
        "Heroic Age", "Kevin MacLeod", "dramatic",
    ),
    "dramatic_03_all_this.mp3": (
        f"{INCOMPETECH}/All%20This.mp3",
        "All This", "Kevin MacLeod", "dramatic",
    ),
    "dramatic_04_impact_lento.mp3": (
        f"{INCOMPETECH}/Impact%20Lento.mp3",
        "Impact Lento", "Kevin MacLeod", "dramatic",
    ),

    # ── COLD (desolate, lonely, atmospheric, minimal) ────────────────────────
    "cold_01_scp_x5x.mp3": (
        f"{INCOMPETECH}/SCP-x5x.mp3",
        "SCP-x5x (Outer Thoughts)", "Kevin MacLeod", "cold",
    ),
    "cold_02_echoes_of_time.mp3": (
        f"{INCOMPETECH}/Echoes%20of%20Time.mp3",
        "Echoes of Time", "Kevin MacLeod", "cold",
    ),
    "cold_03_sad_trio.mp3": (
        f"{INCOMPETECH}/Sad%20Trio.mp3",
        "Sad Trio", "Kevin MacLeod", "cold",
    ),
    "cold_04_ghost_story.mp3": (
        f"{INCOMPETECH}/Ghost%20Story.mp3",
        "Ghost Story", "Kevin MacLeod", "cold",
    ),

    # ── REVERENT (sacred, solemn, meditative) ────────────────────────────────
    "reverent_01_ancient_rite.mp3": (
        f"{INCOMPETECH}/Ancient%20Rite.mp3",
        "Ancient Rite", "Kevin MacLeod", "reverent",
    ),
    "reverent_02_gregorian_chant.mp3": (
        f"{INCOMPETECH}/Gregorian%20Chant.mp3",
        "Gregorian Chant", "Kevin MacLeod", "reverent",
    ),
    "reverent_03_perspectives.mp3": (
        f"{INCOMPETECH}/Perspectives.mp3",
        "Perspectives", "Kevin MacLeod", "reverent",
    ),
    "reverent_04_long_note_four.mp3": (
        f"{INCOMPETECH}/Long%20Note%20Four.mp3",
        "Long Note Four", "Kevin MacLeod", "reverent",
    ),

    # ── WONDER (awe, discovery, vast) ──────────────────────────────────────
    "wonder_01_the_descent.mp3": (
        f"{INCOMPETECH}/The%20Descent.mp3",
        "The Descent", "Kevin MacLeod", "wonder",
    ),
    "wonder_02_crossing_the_divide.mp3": (
        f"{INCOMPETECH}/Crossing%20the%20Divide.mp3",
        "Crossing the Divide", "Kevin MacLeod", "wonder",
    ),
    "wonder_03_temple_of_the_king.mp3": (
        f"{INCOMPETECH}/Enchanted%20Valley.mp3",
        "Enchanted Valley", "Kevin MacLeod", "wonder",
    ),
    "wonder_04_intrepid.mp3": (
        f"{INCOMPETECH}/Intrepid.mp3",
        "Intrepid", "Kevin MacLeod", "wonder",
    ),

    # ── WARMTH (tender, human, intimate) ───────────────────────────────────
    "warmth_01_hearth_and_home.mp3": (
        f"{INCOMPETECH}/Feather%20Waltz.mp3",
        "Feather Waltz", "Kevin MacLeod", "warmth",
    ),
    "warmth_02_peaceful_desolation.mp3": (
        f"{INCOMPETECH}/Peaceful%20Desolation.mp3",
        "Peaceful Desolation", "Kevin MacLeod", "warmth",
    ),
    "warmth_03_evening_fall.mp3": (
        f"{INCOMPETECH}/Dreamer.mp3",
        "Dreamer", "Kevin MacLeod", "warmth",
    ),
    "warmth_04_beauty_flow.mp3": (
        f"{INCOMPETECH}/Beauty%20Flow.mp3",
        "Beauty Flow", "Kevin MacLeod", "warmth",
    ),

    # ── ABSURDITY (bizarre, surreal, strange) ──────────────────────────────
    "absurdity_01_scheming_weasel.mp3": (
        f"{INCOMPETECH}/Scheming%20Weasel.mp3",
        "Scheming Weasel", "Kevin MacLeod", "absurdity",
    ),
    "absurdity_02_monkeys_spinning.mp3": (
        f"{INCOMPETECH}/Monkeys%20Spinning%20Monkeys.mp3",
        "Monkeys Spinning Monkeys", "Kevin MacLeod", "absurdity",
    ),
    "absurdity_03_fluffing_a_duck.mp3": (
        f"{INCOMPETECH}/Fluffing%20a%20Duck.mp3",
        "Fluffing a Duck", "Kevin MacLeod", "absurdity",
    ),
    "absurdity_04_the_builder.mp3": (
        f"{INCOMPETECH}/The%20Builder.mp3",
        "The Builder", "Kevin MacLeod", "absurdity",
    ),
}

# Fallback URLs (Internet Archive mirrors for key tracks)
FALLBACKS = {
    "dark_01_scp_x1x.mp3":               f"{ARCHIVE}/kevin-macleod-dark/SCP-x1x.mp3",
    "dramatic_01_strength_of_titans.mp3":  f"{ARCHIVE}/kevin-macleod-epic/StrengthOfTheTitans.mp3",
}


# ── Ambient sound loops ───────────────────────────────────────────────────
AMBIENT_DIR = Path(__file__).resolve().parent.parent / "remotion" / "public" / "ambient"

AMBIENT_CATEGORIES = [
    "wind",
    "rain",
    "fire_crackling",
    "crowd_murmur",
    "stone_echo",
    "ocean_waves",
]

AMBIENT_TRACKS = {
    f"ambient_{cat}.mp3": cat for cat in AMBIENT_CATEGORIES
}


def setup_ambient_dir():
    """Create ambient directory and print instructions for manual download."""
    AMBIENT_DIR.mkdir(parents=True, exist_ok=True)

    # Check which ambient files already exist
    existing = [f for f in AMBIENT_TRACKS if (AMBIENT_DIR / f).exists()]
    missing = [f for f in AMBIENT_TRACKS if f not in existing]

    if existing:
        print(f"[Ambient] Already have {len(existing)}/{len(AMBIENT_TRACKS)} ambient tracks")
    if not missing:
        print("[Ambient] All ambient tracks present")
        return

    print(f"[Ambient] Missing {len(missing)} ambient track(s).")
    print("[Ambient] ──────────────────────────────────────────────")
    print("[Ambient] Ambient tracks must be manually downloaded.")
    print("[Ambient] Place CC-licensed .mp3 loops in:")
    print(f"[Ambient]   {AMBIENT_DIR}")
    print("[Ambient]")
    print("[Ambient] Expected files:")
    for filename in missing:
        category = AMBIENT_TRACKS[filename]
        print(f"[Ambient]   {filename}  ({category})")
    print("[Ambient]")
    print("[Ambient] Suggested sources (CC-licensed):")
    print("[Ambient]   - freesound.org (CC0 / CC BY)")
    print("[Ambient]   - archive.org (search 'ambient loop CC')")
    print("[Ambient]   - BBC Sound Effects (personal/educational)")
    print("[Ambient] ──────────────────────────────────────────────")


def download(filename: str, url: str, title: str) -> bool:
    dest = MUSIC_DIR / filename
    if dest.exists() and dest.stat().st_size > 50_000:
        print(f"[Music] Already have: {filename}")
        return True
    print(f"[Music] Downloading: {title} -> {filename}")
    try:
        r = requests.get(url, timeout=30, stream=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            dest.write_bytes(r.content)
            size_kb = dest.stat().st_size // 1024
            if dest.stat().st_size > 50_000:
                print(f"[Music] {filename} ({size_kb} KB)")
                return True
            dest.unlink()  # too small — likely an error page
        # Try fallback if available
        fb = FALLBACKS.get(filename)
        if fb and fb != url:
            return download(filename, fb, title + " (fallback)")
        print(f"[Music] SKIP {filename} — HTTP {r.status_code}")
        return False
    except Exception as e:
        print(f"[Music] SKIP {filename} — {e}")
        return False


def _restore_premium_from_supabase():
    """Download premium tracks from Supabase Storage if not already present."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from clients.supabase_client import get_client
        sb = get_client()
    except Exception as e:
        print(f"[Music] Supabase not available for premium tracks: {e}")
        return 0

    try:
        files = sb.storage.from_("music").list()
    except Exception as e:
        print(f"[Music] Could not list Supabase music bucket: {e}")
        return 0

    if not files:
        return 0

    restored = 0
    for item in files:
        name = item.get("name", "")
        if not name.endswith(".mp3"):
            continue
        dest = MUSIC_DIR / name
        if dest.exists() and dest.stat().st_size > 50_000:
            continue  # Already have it

        try:
            data = sb.storage.from_("music").download(name)
            if data and len(data) > 50_000:
                dest.write_bytes(data)
                print(f"[Music] Restored premium: {name} ({len(data) // 1024} KB)")
                restored += 1
        except Exception as e:
            print(f"[Music] Could not restore {name}: {e}")

    if restored:
        print(f"[Music] Restored {restored} premium track(s) from Supabase Storage")
    return restored


def run():
    print("[Music] Checking background music tracks...")
    ok = 0
    for filename, (url, title, _artist, _mood) in TRACKS.items():
        if download(filename, url, title):
            ok += 1
        time.sleep(0.5)  # polite delay

    # Restore premium tracks from Supabase Storage (Epidemic Sound etc.)
    premium_count = _restore_premium_from_supabase()

    # Migrate old single-track filenames to new naming if they exist
    old_to_new = {
        "dark_ambient.mp3": "dark_01_scp_x1x.mp3",
        "tense_suspense.mp3": "tense_01_stay_the_course.mp3",
        "dramatic_orchestral.mp3": "dramatic_01_strength_of_titans.mp3",
        "cold_atmospheric.mp3": "cold_01_scp_x5x.mp3",
        "reverent.mp3": "reverent_01_ancient_rite.mp3",
    }
    for old_name, new_name in old_to_new.items():
        old_path = MUSIC_DIR / old_name
        new_path = MUSIC_DIR / new_name
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)
            print(f"[Music] Migrated {old_name} -> {new_name}")

    # Write attribution file
    attr_path = MUSIC_DIR / "ATTRIBUTION.txt"
    lines = [
        "Music by Kevin MacLeod (incompetech.com)",
        "Licensed under Creative Commons: By Attribution 4.0 License",
        "http://creativecommons.org/licenses/by/4.0/",
        "",
        "Tracks used:",
    ]
    for fn, (_, title, artist, mood) in TRACKS.items():
        lines.append(f"  [{mood}] {title} by {artist}")
    attr_path.write_text("\n".join(lines) + "\n")

    # Set up ambient sound loops directory
    setup_ambient_dir()

    total = ok + premium_count
    print(f"[Music] Setup complete: {ok} free + {premium_count} premium = {total} tracks available")
    return ok > 0


def get_track_catalog() -> dict:
    """Return the full track catalog for use by music_manager."""
    return {fn: {"title": t, "artist": a, "mood": m}
            for fn, (_, t, a, m) in TRACKS.items()}


if __name__ == "__main__":
    run()

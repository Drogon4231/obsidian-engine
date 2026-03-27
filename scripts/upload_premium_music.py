"""
Upload premium (Epidemic Sound) music tracks to Supabase Storage.

Run once from local machine where the tracks exist:
    python3 scripts/upload_premium_music.py

This uploads all epidemic_*.mp3 files to a 'music' bucket in Supabase Storage.
On Railway, setup_music.py will download them back on startup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MUSIC_DIR = Path(__file__).resolve().parent.parent / "remotion" / "public" / "music"


def run():
    from clients.supabase_client import get_client
    sb = get_client()

    # Create the bucket if it doesn't exist (public read for download)
    try:
        sb.storage.create_bucket("music", options={"public": True})
        print("[Upload] Created 'music' bucket")
    except Exception as e:
        if "already exists" in str(e).lower() or "Duplicate" in str(e):
            print("[Upload] 'music' bucket already exists")
        else:
            print(f"[Upload] Bucket creation note: {e}")

    # Find all premium tracks
    premium_files = sorted(MUSIC_DIR.glob("epidemic_*.mp3"))
    if not premium_files:
        print("[Upload] No epidemic_*.mp3 files found in remotion/public/music/")
        return

    print(f"[Upload] Found {len(premium_files)} premium tracks to upload")
    total_mb = sum(f.stat().st_size for f in premium_files) / (1024 * 1024)
    print(f"[Upload] Total size: {total_mb:.1f} MB")

    uploaded = 0
    skipped = 0
    for f in premium_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        try:
            # Check if already uploaded
            try:
                existing = sb.storage.from_("music").list(path="", options={"search": f.name})
                if any(item.get("name") == f.name for item in (existing or [])):
                    print(f"  [Skip] {f.name} ({size_mb:.1f} MB) — already uploaded")
                    skipped += 1
                    continue
            except Exception:
                pass  # List failed, try uploading anyway

            with open(f, "rb") as fp:
                sb.storage.from_("music").upload(
                    path=f.name,
                    file=fp.read(),
                    file_options={"content-type": "audio/mpeg"},
                )
            print(f"  [OK] {f.name} ({size_mb:.1f} MB)")
            uploaded += 1
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                print(f"  [Skip] {f.name} — already exists")
                skipped += 1
            else:
                print(f"  [FAIL] {f.name} — {e}")

    print(f"\n[Upload] Done: {uploaded} uploaded, {skipped} skipped, {len(premium_files)} total")


if __name__ == "__main__":
    run()

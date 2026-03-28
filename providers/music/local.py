"""
Local music provider — scans the local library for tracks.
"""

from __future__ import annotations

from pathlib import Path

from providers.base import MusicProvider


class LocalMusicProvider(MusicProvider):
    """Local music library provider using existing music_manager.py."""

    def search(self, mood: str, duration: float = 600, **kwargs) -> list[dict]:
        from media.music_manager import scan_library

        library = scan_library()
        tracks = library.get(mood, [])
        return [
            {
                "id": t["filename"],
                "title": t["filename"],
                "artist": "Kevin MacLeod" if not t["is_premium"] else "Epidemic Sound",
                "duration": 0,
                "bpm": 0,
                "mood": t["mood"],
            }
            for t in tracks
        ]

    def download(self, track_id: str, output_path: Path,
                 stem: str | None = None) -> Path:
        raise NotImplementedError("Local tracks are already on disk")

    def select_for_video(self, scenes: list[dict],
                         total_duration: float) -> dict | None:
        from media.music_manager import get_smart_music_for_video

        return get_smart_music_for_video(scenes, total_duration)

    @property
    def name(self) -> str:
        return "Local Library"

"""
Epidemic Sound music provider — API-powered music search and download.
"""

from __future__ import annotations

import os
from pathlib import Path

from providers.base import MusicProvider


class EpidemicMusicProvider(MusicProvider):
    """Epidemic Sound music provider using the MCP API."""

    def __init__(self):
        self._api_key = os.getenv("EPIDEMIC_SOUND_API_KEY")

    def search(self, mood: str, duration: float = 600, **kwargs) -> list[dict]:
        from media.epidemic_music_manager import MOOD_SEARCH_MAP

        params = MOOD_SEARCH_MAP.get(mood, MOOD_SEARCH_MAP.get("dark", {}))
        from clients.epidemic_client import EpidemicSoundClient

        client = EpidemicSoundClient()
        results = client.search_music(
            keyword=params.get("keyword", mood),
            bpm_min=params.get("bpm_min"),
            bpm_max=params.get("bpm_max"),
            mood=params.get("mood"),
            vocals=kwargs.get("vocals"),
            limit=kwargs.get("limit", 5),
        )
        return [
            {
                "id": str(r.get("id", "")),
                "title": r.get("title", ""),
                "artist": r.get("artist", {}).get("name", "") if isinstance(r.get("artist"), dict) else str(r.get("artist", "")),
                "duration": r.get("duration", 0),
                "bpm": r.get("bpm", 0),
                "mood": mood,
            }
            for r in results
        ]

    def download(self, track_id: str, output_path: Path,
                 stem: str | None = None) -> Path:
        from clients.epidemic_client import EpidemicSoundClient

        client = EpidemicSoundClient()
        return client.download_track(track_id, output_path, stem=stem)

    def select_for_video(self, scenes: list[dict],
                         total_duration: float) -> dict | None:
        from media.epidemic_music_manager import search_for_video

        return search_for_video(scenes, total_duration)

    def check_status(self) -> dict:
        if not self._api_key:
            return {"status": "no_key"}
        try:
            from clients.epidemic_client import EpidemicSoundClient

            client = EpidemicSoundClient()
            valid = client.check_key_valid()
            return {"status": "connected" if valid else "expired"}
        except Exception:
            return {"status": "error"}

    @property
    def name(self) -> str:
        return "Epidemic Sound"

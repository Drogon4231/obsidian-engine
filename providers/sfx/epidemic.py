"""
Epidemic Sound SFX provider — API-powered sound effect search and download.
"""

from __future__ import annotations

import os
from pathlib import Path

from providers.base import SFXProvider


class EpidemicSFXProvider(SFXProvider):
    """Epidemic Sound sound effects provider."""

    def __init__(self):
        self._api_key = os.getenv("EPIDEMIC_SOUND_API_KEY")

    def search(self, keyword: str, duration_max: float = 5.0,
               **kwargs) -> list[dict]:
        from clients.epidemic_client import EpidemicSoundClient

        client = EpidemicSoundClient()
        results = client.search_sfx(
            keyword=keyword,
            duration_max=duration_max,
            tags=kwargs.get("tags"),
            limit=kwargs.get("limit", 5),
        )
        return [
            {
                "id": str(r.get("id", "")),
                "title": r.get("title", ""),
                "duration": r.get("duration", 0),
                "tags": r.get("tags", []),
            }
            for r in results
        ]

    def download(self, sfx_id: str, output_path: Path) -> Path:
        from clients.epidemic_client import EpidemicSoundClient

        client = EpidemicSoundClient()
        return client.download_sfx(sfx_id, output_path)

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
        return "Epidemic Sound SFX"

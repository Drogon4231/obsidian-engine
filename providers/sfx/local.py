"""
Local SFX provider — uses existing setup_sfx.py and setup_ambience.py files.
"""

from __future__ import annotations

from pathlib import Path

from providers.base import SFXProvider


class LocalSFXProvider(SFXProvider):
    """Local sound effects provider using Pixabay downloads."""

    def search(self, keyword: str, duration_max: float = 5.0,
               **kwargs) -> list[dict]:
        from scripts.setup_sfx import SFX_TRACKS

        results = []
        for mood, info in SFX_TRACKS.items():
            if keyword.lower() in mood or mood in keyword.lower():
                results.append({
                    "id": info["file"],
                    "title": info["desc"],
                    "duration": 0,
                    "tags": [mood],
                })
        return results

    def download(self, sfx_id: str, output_path: Path) -> Path:
        raise NotImplementedError("Local SFX tracks are already on disk")

    @property
    def name(self) -> str:
        return "Local SFX"

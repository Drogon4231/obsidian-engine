"""
Pexels stock footage provider — default implementation.

Free API with generous limits. No attribution required for commercial use.
"""

from __future__ import annotations

import os
from pathlib import Path

from providers.base import FootageProvider


class PexelsProvider(FootageProvider):
    """Pexels stock footage provider."""

    API_BASE = "https://api.pexels.com/videos"

    def __init__(self):
        self._api_key = os.getenv("PEXELS_API_KEY")

    def search(
        self,
        query: str,
        orientation: str = "landscape",
        min_duration: int = 5,
        max_results: int = 5,
    ) -> list[dict]:
        import requests
        if not self._api_key:
            return []

        r = requests.get(
            f"{self.API_BASE}/search",
            headers={"Authorization": self._api_key},
            params={
                "query": query,
                "orientation": orientation,
                "per_page": max_results,
                "size": "large",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []

        results = []
        for video in r.json().get("videos", []):
            duration = video.get("duration", 0)
            if duration < min_duration:
                continue

            # Find best quality file
            files = video.get("video_files", [])
            best = max(files, key=lambda f: f.get("width", 0), default=None)
            if not best:
                continue

            results.append({
                "url": best.get("link", ""),
                "duration": duration,
                "width": best.get("width", 0),
                "height": best.get("height", 0),
                "preview_url": video.get("image", ""),
            })

        return results[:max_results]

    def download(self, url: str, output_path: Path) -> Path:
        from pipeline.helpers import download_file
        download_file(url, str(output_path))
        return output_path

    @property
    def name(self) -> str:
        return "Pexels"

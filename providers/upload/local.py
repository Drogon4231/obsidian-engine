"""
Local save upload provider — saves video to disk instead of uploading.

Useful for testing, preview, or workflows that handle upload separately.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from providers.base import UploadProvider


class LocalSaveProvider(UploadProvider):
    """Save video locally instead of uploading."""

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "final"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: Path | None = None,
    ) -> dict:
        import re
        import json

        # Create safe filename from title
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:80]
        dest = self._output_dir / f"{safe_title}.mp4"
        shutil.copy2(video_path, dest)

        # Save metadata
        meta_path = dest.with_suffix(".json")
        meta = {
            "title": title,
            "description": description,
            "tags": tags,
            "video_path": str(dest),
            "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        # Copy thumbnail if provided
        if thumbnail_path and Path(thumbnail_path).exists():
            thumb_dest = dest.with_suffix(".thumb.jpg")
            shutil.copy2(thumbnail_path, thumb_dest)

        return {
            "video_id": f"local_{safe_title}",
            "url": f"file://{dest}",
            "status": "saved_locally",
        }

    @property
    def name(self) -> str:
        return "Local Save"

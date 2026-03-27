"""
fal.ai image generation provider — default implementation.

Supports Recraft and Flux models via fal.ai's serverless GPU infrastructure.
"""

from __future__ import annotations

import os
from pathlib import Path

from providers.base import ImageProvider


class FalProvider(ImageProvider):
    """fal.ai image generation provider."""

    def __init__(self):
        self._ensure_keys()

    def _ensure_keys(self):
        """Verify fal.ai API keys are set."""
        if not os.getenv("FAL_KEY") and not os.getenv("FAL_API_KEY"):
            raise RuntimeError("FAL_KEY or FAL_API_KEY not set")

    def generate(
        self,
        prompt: str,
        style: str | None = None,
        width: int = 1920,
        height: int = 1080,
        seed: int | None = None,
    ) -> Path:
        from pipeline.images import _fal_subscribe_with_retry
        from pipeline.helpers import download_file
        from core.config import cfg
        import tempfile

        model = style or cfg.models.image_provider  # "recraft" or "flux"

        if model == "recraft":
            endpoint = cfg.models.fal_recraft
            args = {
                "prompt": prompt,
                "style": "digital_illustration/hand_drawn",
                "size": {"width": width, "height": height},
            }
        else:
            endpoint = cfg.models.fal_flux
            args = {
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
            }

        if seed is not None:
            args["seed"] = seed

        result = _fal_subscribe_with_retry(endpoint, args)

        # Extract image URL
        images = result.get("images") or result.get("output", {}).get("images", [])
        if not images:
            raise RuntimeError(f"fal.ai returned no images for prompt: {prompt[:50]}")

        url = images[0] if isinstance(images[0], str) else images[0].get("url", "")
        if not url:
            raise RuntimeError("fal.ai returned empty image URL")

        # Download to temp file
        suffix = ".png" if ".png" in url else ".jpg"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        download_file(url, tmp.name)
        return Path(tmp.name)

    def estimate_cost(self) -> float:
        # fal.ai: ~$0.01-0.05 per image depending on model
        return 0.03

    @property
    def name(self) -> str:
        return "fal.ai"

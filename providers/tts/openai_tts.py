"""
OpenAI TTS provider — default implementation.
"""

from __future__ import annotations

import os
from pathlib import Path
from providers.base import TTSProvider

class OpenAIProvider(TTSProvider):
    """OpenAI text-to-speech provider."""

    def __init__(self):
        self._api_key = os.getenv("OPENAI_API_KEY")

    def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        voice_settings: dict | None = None,
        speed: float = 1.0,
    ) -> tuple[Path, list[dict]]:
        import requests
        import tempfile
        import warnings

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        from core.config import cfg

        model = getattr(cfg.voice, "model", "tts-1")
        voice = voice_id or getattr(cfg.voice, "narrator_id", "alloy")

        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": text,
            "model": model,
            "voice": voice,
            "response_format": "mp3"
        }
        if speed != 1.0:
            payload["speed"] = speed

        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(r.content)
        tmp.close()

        warnings.warn(
            "OpenAI TTS does not provide word-level timestamps. "
            "Downstream captions in Remotion will not sync.",
            RuntimeWarning
        )

        return Path(tmp.name), []

    def list_voices(self) -> list[dict]:
        """Returns the default OpenAI voices."""
        voices = [
            "alloy", "ash", "ballad", "coral", "echo", "fable",
            "onyx", "nova", "sage", "shimmer", "verse", "marin", "cedar"
        ]
        return [
            {
                "id": v,
                "name": v.capitalize(),
                "description": "OpenAI built-in voice"
            }
            for v in voices
        ]

    def check_credits(self) -> dict:
        """
        OpenAI API does not expose a simple endpoint for TTS character limits.
        Billing is handled in USD across the entire organization.
        """
        return {
            "remaining": -1,
            "limit": -1,
            "unit": "USD (Check OpenAI Dashboard)"
        }

    @property
    def name(self) -> str:
        return "OpenAI"
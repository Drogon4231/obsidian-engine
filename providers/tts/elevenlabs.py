"""
ElevenLabs TTS provider — default implementation.

Uses the ElevenLabs API for high-quality text-to-speech with word timestamps.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from providers.base import TTSProvider


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs text-to-speech provider."""

    def __init__(self):
        self._api_key = os.getenv("ELEVENLABS_API_KEY")

    def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        voice_settings: dict | None = None,
        speed: float = 1.0,
    ) -> tuple[Path, list[dict]]:
        import requests
        import tempfile

        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")

        from core.config import cfg
        voice_id = voice_id or cfg.voice.narrator_id
        model = cfg.voice.model

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        headers = {"xi-api-key": self._api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": voice_settings or cfg.voice.body.to_dict(),
        }
        if speed != 1.0:
            payload["speed"] = speed

        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = json.loads(r.text, strict=False)

        # Save audio
        audio_bytes = __import__("base64").b64decode(data["audio_base64"])
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        # Parse timestamps
        timestamps = []
        alignment = data.get("alignment", {})
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])

        if chars and starts and ends:
            word = ""
            word_start = 0.0
            for i, ch in enumerate(chars):
                if ch == " " and word:
                    timestamps.append({"word": word, "start": word_start, "end": ends[i - 1]})
                    word = ""
                elif ch != " ":
                    if not word:
                        word_start = starts[i]
                    word += ch
            if word:
                timestamps.append({"word": word, "start": word_start, "end": ends[-1]})

        return Path(tmp.name), timestamps

    def list_voices(self) -> list[dict]:
        import requests
        if not self._api_key:
            return []
        r = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": self._api_key},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        voices = json.loads(r.text, strict=False).get("voices", [])
        return [
            {"id": v["voice_id"], "name": v["name"], "description": v.get("description", "")}
            for v in voices
        ]

    def check_credits(self) -> dict:
        import requests
        if not self._api_key:
            return {"remaining": 0, "limit": 0, "unit": "characters"}
        r = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": self._api_key},
            timeout=10,
        )
        if r.status_code != 200:
            return {"remaining": 0, "limit": 0, "unit": "characters"}
        sub = json.loads(r.text, strict=False).get("subscription", {})
        limit = sub.get("character_limit", 0)
        used = sub.get("character_count", 0)
        return {"remaining": limit - used, "limit": limit, "unit": "characters"}

    @property
    def name(self) -> str:
        return "ElevenLabs"

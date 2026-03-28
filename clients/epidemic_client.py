"""
Epidemic Sound API client — MCP server wrapper.

Auth: Bearer token (EPIDEMIC_SOUND_API_KEY env var).
Keys expire every 30 days — regenerate at epidemicsound.com/account/api-keys.
Base URL: https://www.epidemicsound.com/a/mcp-service

All methods fail gracefully with KeyExpiredError on 401/403.
Pipeline should catch this and fall back to local music library.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)


class KeyExpiredError(Exception):
    """Raised when the Epidemic Sound API key is expired or invalid (401/403)."""


class EpidemicSoundClient:
    """Stateless HTTP wrapper for the Epidemic Sound MCP API."""

    BASE_URL = "https://www.epidemicsound.com/a/mcp-service"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("EPIDEMIC_SOUND_API_KEY", "")

    # ── Core HTTP ─────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, *,
                 params: dict | None = None,
                 json_body: dict | None = None,
                 timeout: int = 30,
                 max_retries: int = 3) -> dict:
        """Make an authenticated request with retry logic."""
        import requests

        if not self._api_key:
            raise KeyExpiredError("EPIDEMIC_SOUND_API_KEY not set")

        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.request(
                    method, url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=timeout,
                )

                if r.status_code in (401, 403):
                    raise KeyExpiredError(
                        "Epidemic Sound API key expired or invalid — "
                        "regenerate at epidemicsound.com/account/api-keys"
                    )

                if r.status_code == 429 or r.status_code >= 500:
                    wait = min(30, 2 ** attempt * 5)
                    logger.warning(f"[Epidemic] {r.status_code} on {path}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                r.raise_for_status()
                return r.json() if r.text else {}

            except KeyExpiredError:
                raise
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    wait = min(30, 2 ** attempt * 5)
                    logger.warning(f"[Epidemic] Request error: {e}, retrying in {wait}s...")
                    time.sleep(wait)

        raise last_err or RuntimeError(f"[Epidemic] Failed after {max_retries} retries: {path}")

    def _download_file(self, url: str, output_path: Path, timeout: int = 120) -> Path:
        """Download a file from a URL to a local path."""
        import requests

        if not self._api_key:
            raise KeyExpiredError("EPIDEMIC_SOUND_API_KEY not set")

        headers = {"Authorization": f"Bearer {self._api_key}"}
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)

        if r.status_code in (401, 403):
            raise KeyExpiredError(
                "Epidemic Sound API key expired or invalid — "
                "regenerate at epidemicsound.com/account/api-keys"
            )
        r.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"[Epidemic] Downloaded: {output_path.name} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    # ── Validation ────────────────────────────────────────────────────────────

    def check_key_valid(self) -> bool:
        """Quick validation — used by setup wizard and health check."""
        if not self._api_key:
            return False
        try:
            self.search_music(keyword="test", limit=1)
            return True
        except KeyExpiredError:
            return False
        except Exception:
            return False

    # ── Music Discovery ───────────────────────────────────────────────────────

    def search_music(self, *, keyword: str = "", bpm_min: int | None = None,
                     bpm_max: int | None = None, mood: str | None = None,
                     duration_min: int | None = None,
                     duration_max: int | None = None,
                     instruments: list[str] | None = None,
                     key: str | None = None,
                     vocals: bool | None = None,
                     sort: str = "relevance",
                     limit: int = 10) -> list[dict]:
        """Search the music catalog.

        Returns list of recordings with: id, title, bpm, cover_art_url,
        audio_file (preview_url, waveform), stems, tags, artist.
        """
        params = {"limit": limit, "sort": sort}
        if keyword:
            params["q"] = keyword
        if bpm_min is not None:
            params["bpm_min"] = bpm_min
        if bpm_max is not None:
            params["bpm_max"] = bpm_max
        if mood:
            params["mood"] = mood
        if duration_min is not None:
            params["duration_min"] = duration_min
        if duration_max is not None:
            params["duration_max"] = duration_max
        if instruments:
            params["instruments"] = ",".join(instruments)
        if key:
            params["key"] = key
        if vocals is not None:
            params["vocals"] = str(vocals).lower()

        data = self._request("GET", "/recordings/search", params=params)
        return data.get("recordings", data.get("results", []))

    def find_similar(self, track_id: str, limit: int = 5) -> list[dict]:
        """Find tracks similar to a given Epidemic Sound track ID."""
        data = self._request("GET", f"/recordings/{track_id}/similar",
                             params={"limit": limit})
        return data.get("recordings", data.get("results", []))

    def search_external(self, term: str) -> list[dict]:
        """Find Epidemic Sound tracks matching external tracks (e.g., Spotify)."""
        data = self._request("GET", "/recordings/external-search",
                             params={"q": term})
        return data.get("results", [])

    # ── Sound Effects ─────────────────────────────────────────────────────────

    def search_sfx(self, *, keyword: str, duration_max: float | None = None,
                   tags: list[str] | None = None,
                   sort: str = "relevance",
                   limit: int = 10) -> list[dict]:
        """Search the sound effects catalog.

        Returns list with: id, title, audio_file (preview_url, waveform), tags.
        """
        params = {"q": keyword, "limit": limit, "sort": sort}
        if duration_max is not None:
            params["duration_max"] = int(duration_max * 1000)
        if tags:
            params["tags"] = ",".join(tags)

        data = self._request("GET", "/sfx/search", params=params)
        return data.get("sound_effects", data.get("results", []))

    def find_similar_sfx(self, sfx_id: str, limit: int = 5) -> list[dict]:
        """Find sound effects similar to a given SFX ID."""
        data = self._request("GET", f"/sfx/{sfx_id}/similar",
                             params={"limit": limit})
        return data.get("sound_effects", data.get("results", []))

    # ── Track Adaptation (beta) ───────────────────────────────────────────────

    def adapt_track(self, track_id: str, *,
                    target_duration_ms: int,
                    force_duration: bool = True,
                    loopable: bool = False,
                    max_results: int = 1,
                    preference_regions: list[dict] | None = None,
                    required_regions: list[dict] | None = None,
                    skip_stems: bool = False) -> dict:
        """Submit a track adaptation job (edit to exact duration).

        Returns {job_id, status} — poll with get_adaptation_status().
        Max target_duration_ms: 300000 (5 minutes).
        """
        body = {
            "recording_id": track_id,
            "target_duration": target_duration_ms,
            "forceDuration": force_duration,
            "loopable": loopable,
            "maxResults": max_results,
            "skipStems": skip_stems,
        }
        if preference_regions:
            body["preferenceRegions"] = preference_regions
        if required_regions:
            body["requiredRegionsAtOffsets"] = required_regions

        return self._request("POST", "/recordings/edit", json_body=body, timeout=60)

    def get_adaptation_status(self, job_id: str) -> dict:
        """Check adaptation job status: PENDING, IN_PROGRESS, COMPLETED, FAILED."""
        return self._request("GET", f"/recordings/edit/{job_id}")

    def download_adapted_track(self, job_id: str, edit_id: str,
                               output_path: Path) -> Path:
        """Download an adapted track version."""
        data = self._request("GET", f"/recordings/edit/{job_id}/download",
                             params={"edit_id": edit_id})
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for adaptation {job_id}/{edit_id}")
        return self._download_file(url, output_path)

    # ── Voiceovers ────────────────────────────────────────────────────────────

    def browse_voices(self, limit: int = 20) -> list[dict]:
        """Browse available AI voice artists.

        Returns list with: id, title, example_audio_url, artwork,
        language, gender, characteristics.
        """
        data = self._request("GET", "/voiceovers/voices",
                             params={"limit": limit})
        return data.get("voices", data.get("results", []))

    def list_user_voices(self) -> list[dict]:
        """List user-generated voice replicas."""
        data = self._request("GET", "/voiceovers/voices/user")
        return data.get("voices", data.get("results", []))

    def generate_voiceover(self, voice_id: str, text: str, *,
                           language: str = "en-US",
                           speed: float = 0.0) -> dict:
        """Generate a voiceover. Returns {voiceover_id, status}.

        speed: -1.0 to +1.0 (0.0 = default speed).
        """
        body = {
            "voice_id": voice_id,
            "text": text,
            "language": language,
            "speed": speed,
        }
        return self._request("POST", "/voiceovers/generate",
                             json_body=body, timeout=60)

    def get_voiceover_status(self, voiceover_id: str) -> dict:
        """Check voiceover generation status: DONE, GENERATING, FAILED."""
        return self._request("GET", f"/voiceovers/{voiceover_id}/status")

    def get_voiceover_details(self, voiceover_id: str) -> dict:
        """Get complete voiceover metadata: audio_url, duration_ms, waveform_url."""
        return self._request("GET", f"/voiceovers/{voiceover_id}")

    def download_voiceover(self, voiceover_id: str, output_path: Path) -> Path:
        """Download a completed voiceover audio file."""
        data = self._request("GET", f"/voiceovers/{voiceover_id}/download")
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for voiceover {voiceover_id}")
        return self._download_file(url, output_path)

    # ── Asset Downloads ───────────────────────────────────────────────────────

    def download_track(self, track_id: str, output_path: Path, *,
                       stem: str | None = None,
                       format: str = "mp3") -> Path:
        """Download a music track (full or stem).

        stem: None (full mix), "BASS", "DRUMS", or "INSTRUMENTS".
        format: "mp3" or "wav".
        """
        params = {"format": format}
        if stem:
            params["stem"] = stem.upper()

        data = self._request("GET", f"/recordings/{track_id}/download",
                             params=params)
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for track {track_id}")
        return self._download_file(url, output_path)

    def download_sfx(self, sfx_id: str, output_path: Path, *,
                     format: str = "mp3") -> Path:
        """Download a sound effect file."""
        data = self._request("GET", f"/sfx/{sfx_id}/download",
                             params={"format": format})
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for SFX {sfx_id}")
        return self._download_file(url, output_path)

    # ── Account ───────────────────────────────────────────────────────────────

    def check_subscription(self) -> dict:
        """Get subscription status and plan info."""
        try:
            return self._request("GET", "/account/subscription")
        except Exception:
            return {"status": "unknown", "plan": "unknown"}

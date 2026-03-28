"""
Epidemic Sound API client — MCP protocol wrapper.

Auth: Bearer token (EPIDEMIC_SOUND_API_KEY env var).
Keys expire every 30 days — regenerate at epidemicsound.com/account/api-keys.
MCP endpoint: https://www.epidemicsound.com/a/mcp-service/mcp

The Epidemic Sound API is an MCP server — all tool calls go through
JSON-RPC POST to a single endpoint. Each tool is invoked by name
with arguments.

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
    """MCP protocol client for the Epidemic Sound API."""

    MCP_ENDPOINT = "https://www.epidemicsound.com/a/mcp-service/mcp"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("EPIDEMIC_SOUND_API_KEY", "")
        self._request_id = 0

    # ── MCP Protocol Core ─────────────────────────────────────────────────────

    def _call_tool(self, tool_name: str, arguments: dict | None = None,
                   timeout: int = 30, max_retries: int = 3) -> dict:
        """Call an MCP tool via JSON-RPC POST.

        MCP protocol: POST to endpoint with
        {"jsonrpc": "2.0", "method": "tools/call",
         "params": {"name": tool_name, "arguments": arguments},
         "id": request_id}
        """
        import requests

        if not self._api_key:
            raise KeyExpiredError("EPIDEMIC_SOUND_API_KEY not set")

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
            "id": self._request_id,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    self.MCP_ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )

                if r.status_code in (401, 403):
                    raise KeyExpiredError(
                        "Epidemic Sound API key expired or invalid — "
                        "regenerate at epidemicsound.com/account/api-keys"
                    )

                if r.status_code == 429 or r.status_code >= 500:
                    wait = min(30, 2 ** attempt * 5)
                    logger.warning(f"[Epidemic] {r.status_code} on {tool_name}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                r.raise_for_status()
                resp = r.json() if r.text else {}

                # MCP JSON-RPC response: {"result": {...}} or {"error": {...}}
                if "error" in resp:
                    err = resp["error"]
                    msg = err.get("message", str(err))
                    raise RuntimeError(f"[Epidemic] MCP error on {tool_name}: {msg}")

                # Extract result — MCP wraps tool output in result.content
                result = resp.get("result", resp)
                if isinstance(result, dict) and "content" in result:
                    # MCP content is typically [{type: "text", text: "json_string"}]
                    content = result["content"]
                    if isinstance(content, list) and content:
                        text = content[0].get("text", "")
                        if text:
                            import json
                            try:
                                return json.loads(text)
                            except (json.JSONDecodeError, TypeError):
                                return {"raw": text}
                    return content if content else {}
                return result

            except KeyExpiredError:
                raise
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    wait = min(30, 2 ** attempt * 5)
                    logger.warning(f"[Epidemic] Request error on {tool_name}: {e}, retrying in {wait}s...")
                    time.sleep(wait)

        raise last_err or RuntimeError(f"[Epidemic] Failed after {max_retries} retries: {tool_name}")

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
        """Search the music catalog via MCP search_music tool."""
        args: dict = {"limit": limit, "sort": sort}
        if keyword:
            args["term"] = keyword
        if bpm_min is not None:
            args["bpmMin"] = bpm_min
        if bpm_max is not None:
            args["bpmMax"] = bpm_max
        if mood:
            args["moods"] = [mood]
        if duration_min is not None:
            args["durationMin"] = duration_min
        if duration_max is not None:
            args["durationMax"] = duration_max
        if instruments:
            args["instruments"] = instruments
        if key:
            args["keys"] = [key]
        if vocals is not None:
            args["vocals"] = vocals

        data = self._call_tool("search_music", args)
        return data.get("recordings", data.get("results", data.get("tracks", [])))

    def find_similar(self, track_id: str, limit: int = 5) -> list[dict]:
        """Find tracks similar to a given Epidemic Sound track ID."""
        data = self._call_tool("find_similar_track", {
            "trackId": track_id, "limit": limit,
        })
        return data.get("recordings", data.get("results", []))

    def search_external(self, term: str) -> list[dict]:
        """Find Epidemic Sound tracks matching external tracks (e.g., Spotify)."""
        data = self._call_tool("search_external_track", {"term": term})
        return data.get("results", [])

    # ── Sound Effects ─────────────────────────────────────────────────────────

    def search_sfx(self, *, keyword: str, duration_max: float | None = None,
                   tags: list[str] | None = None,
                   sort: str = "relevance",
                   limit: int = 10) -> list[dict]:
        """Search the sound effects catalog via MCP search_sound_effects tool."""
        args: dict = {"term": keyword, "limit": limit, "sort": sort}
        if duration_max is not None:
            args["durationMax"] = int(duration_max * 1000)
        if tags:
            args["tags"] = tags

        data = self._call_tool("search_sound_effects", args)
        return data.get("sound_effects", data.get("results", []))

    def find_similar_sfx(self, sfx_id: str, limit: int = 5) -> list[dict]:
        """Find sound effects similar to a given SFX ID."""
        data = self._call_tool("find_similar_sound_effects", {
            "soundEffectId": sfx_id, "limit": limit,
        })
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
        """Submit a track adaptation job via MCP edit_recording tool."""
        args: dict = {
            "recordingId": track_id,
            "targetDuration": target_duration_ms,
            "forceDuration": force_duration,
            "loopable": loopable,
            "maxResults": max_results,
            "skipStems": skip_stems,
        }
        if preference_regions:
            args["preferenceRegions"] = preference_regions
        if required_regions:
            args["requiredRegionsAtOffsets"] = required_regions

        return self._call_tool("edit_recording", args, timeout=60)

    def get_adaptation_status(self, job_id: str) -> dict:
        """Check adaptation job status."""
        return self._call_tool("get_edit_status", {"jobId": job_id})

    def download_adapted_track(self, job_id: str, edit_id: str,
                               output_path: Path) -> Path:
        """Download an adapted track version."""
        data = self._call_tool("download_edited_track", {
            "jobId": job_id, "editId": edit_id,
        })
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for adaptation {job_id}/{edit_id}")
        return self._download_file(url, output_path)

    # ── Voiceovers ────────────────────────────────────────────────────────────

    def browse_voices(self, limit: int = 20) -> list[dict]:
        """Browse available AI voice artists via MCP browse_voice_artists tool."""
        data = self._call_tool("browse_voice_artists", {"limit": limit})
        return data.get("voices", data.get("results", []))

    def list_user_voices(self) -> list[dict]:
        """List user-generated voice replicas."""
        data = self._call_tool("list_user_generated_voices", {})
        return data.get("voices", data.get("results", []))

    def generate_voiceover(self, voice_id: str, text: str, *,
                           language: str = "en-US",
                           speed: float = 0.0) -> dict:
        """Generate a voiceover via MCP generate_voiceover tool."""
        return self._call_tool("generate_voiceover", {
            "voiceId": voice_id,
            "text": text,
            "language": language,
            "speed": speed,
        }, timeout=60)

    def get_voiceover_status(self, voiceover_id: str) -> dict:
        """Check voiceover generation status."""
        return self._call_tool("get_voiceover_status", {
            "voiceoverId": voiceover_id,
        })

    def get_voiceover_details(self, voiceover_id: str) -> dict:
        """Get complete voiceover metadata."""
        return self._call_tool("get_voiceover_details", {
            "voiceoverId": voiceover_id,
        })

    def download_voiceover(self, voiceover_id: str, output_path: Path) -> Path:
        """Download a completed voiceover audio file."""
        data = self._call_tool("download_voiceover", {
            "voiceoverId": voiceover_id,
        })
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for voiceover {voiceover_id}")
        return self._download_file(url, output_path)

    # ── Asset Downloads ───────────────────────────────────────────────────────

    def download_track(self, track_id: str, output_path: Path, *,
                       stem: str | None = None,
                       format: str = "mp3") -> Path:
        """Download a music track via MCP download_music_track tool."""
        args: dict = {
            "recordingId": track_id,
            "format": format.upper(),
        }
        if stem:
            args["stemType"] = stem.upper()

        data = self._call_tool("download_music_track", args)
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for track {track_id}")
        return self._download_file(url, output_path)

    def download_sfx(self, sfx_id: str, output_path: Path, *,
                     format: str = "mp3") -> Path:
        """Download a sound effect via MCP download_sound_effect tool."""
        data = self._call_tool("download_sound_effect", {
            "soundEffectId": sfx_id,
            "format": format.upper(),
        })
        url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for SFX {sfx_id}")
        return self._download_file(url, output_path)

    # ── Account ───────────────────────────────────────────────────────────────

    def check_subscription(self) -> dict:
        """Get subscription status and plan info."""
        try:
            return self._call_tool("get_subscription_status", {})
        except Exception:
            return {"status": "unknown", "plan": "unknown"}

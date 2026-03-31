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

    # MCP tool name mapping: old names → new server names
    _TOOL_MAP = {
        "search_music": "SearchRecordings",
        "find_similar_track": "SearchSimilarToRecording",
        "search_sound_effects": "SearchSoundEffects",
        "find_similar_sound_effects": "SearchSimilarToSoundEffect",
        "download_music_track": "DownloadRecording",
        "download_sound_effect": "DownloadSoundEffect",
        "browse_voice_artists": "ListVoices",
        "generate_voiceover": "GenerateVoiceover",
        "get_voiceover_status": "PollVoiceoverGenerationStatus",
        "get_voiceover_details": "GetVoiceover",
        "download_voiceover": "DownloadVoiceover",
        "list_user_generated_voices": "ListUserGeneratedVoices",
        "edit_recording": "EditRecording",
        "poll_edit_recording": "PollEditRecordingJob",
        "download_recording_edit": "DownloadRecordingEdit",
    }

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("EPIDEMIC_SOUND_API_KEY", "")
        self._request_id = 0
        self._session_id = None  # MCP session ID from initialize
        self._session_headers = {}  # Headers with session ID

    # ── MCP Protocol Core ─────────────────────────────────────────────────────

    def _parse_sse_response(self, response_text: str) -> dict:
        """Parse Server-Sent Events (SSE) response to extract JSON-RPC data."""
        import json as _json
        for line in response_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                try:
                    return _json.loads(line[6:])
                except (ValueError, TypeError):
                    continue
        # Fallback: try parsing as plain JSON
        try:
            return _json.loads(response_text)
        except (ValueError, TypeError):
            return {}

    def _ensure_session(self, timeout: int = 30) -> None:
        """Initialize MCP session if not already established."""
        import requests

        if self._session_id:
            return

        if not self._api_key:
            raise KeyExpiredError("EPIDEMIC_SOUND_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        # Step 1: Initialize
        self._request_id += 1
        init_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "obsidian-archive", "version": "1.0.0"},
            },
            "id": self._request_id,
        }
        r = requests.post(self.MCP_ENDPOINT, headers=headers, json=init_payload, timeout=timeout)
        if r.status_code in (401, 403):
            raise KeyExpiredError("Epidemic Sound API key expired or invalid")
        r.raise_for_status()

        self._parse_sse_response(r.text)  # validate response
        self._session_id = r.headers.get("mcp-session-id", "")
        # Store session ID in headers for all subsequent requests
        self._session_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self._session_id,
        }

        # Step 2: Send initialized notification
        requests.post(
            self.MCP_ENDPOINT, headers=self._session_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=timeout,
        )
        logger.info(f"[Epidemic] MCP session initialized (session: {self._session_id[:12]}...)")

    def _call_tool(self, tool_name: str, arguments: dict | None = None,
                   timeout: int = 30, max_retries: int = 3) -> dict:
        """Call an MCP tool via JSON-RPC POST with session support.

        MCP protocol requires: initialize → notifications/initialized → tools/call
        Server responds with SSE format (data: {...}).
        """
        import requests

        if not self._api_key:
            raise KeyExpiredError("EPIDEMIC_SOUND_API_KEY not set")

        # Ensure session is initialized
        self._ensure_session(timeout=timeout)

        # Map old tool names to new server names
        server_tool_name = self._TOOL_MAP.get(tool_name, tool_name)

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": server_tool_name,
                "arguments": arguments or {},
            },
            "id": self._request_id,
        }

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    self.MCP_ENDPOINT,
                    headers=self._session_headers,
                    json=payload,
                    timeout=timeout,
                )

                if r.status_code in (401, 403):
                    raise KeyExpiredError(
                        "Epidemic Sound API key expired or invalid — "
                        "regenerate at epidemicsound.com/account/api-keys"
                    )

                if r.status_code == 422:
                    # Session expired — reinitialize
                    self._session_id = None
                    self._ensure_session(timeout=timeout)
                    continue

                if r.status_code == 429 or r.status_code >= 500:
                    wait = min(30, 2 ** attempt * 5)
                    logger.warning(f"[Epidemic] {r.status_code} on {tool_name}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                r.raise_for_status()

                # Parse SSE response
                resp = self._parse_sse_response(r.text)

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
        args: dict = {}
        if keyword:
            args["searchTerm"] = keyword
        if limit:
            args["first"] = limit  # New API uses 'first' for pagination
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
        # New API: data.recordings.nodes[].recording, Old API: tracks[]
        inner = data.get("data") or {}
        recs = (inner.get("recordings") or {}).get("nodes", [])
        if recs:
            return [node.get("recording", node) for node in recs]
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
        args: dict = {"searchTerm": keyword}
        if limit:
            args["first"] = limit
        if duration_max is not None:
            args["durationMax"] = int(duration_max * 1000)
        if tags:
            args["tags"] = tags

        data = self._call_tool("search_sound_effects", args)
        # New API: data.soundEffects.nodes[].soundEffect
        inner = (data.get("data") or {}).get("soundEffects", {}).get("nodes", [])
        if inner:
            return [node.get("soundEffect", node) for node in inner]
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
        """Submit a track adaptation job via MCP EditRecording tool."""
        edit_input: dict = {
            "targetDurationMs": target_duration_ms,
            "downloadAudioFormat": "MP3",
            "forceDuration": force_duration,
            "loopable": loopable,
            "maxResults": max_results,
            "skipStems": skip_stems,
        }
        if preference_regions:
            edit_input["preferenceRegions"] = preference_regions
        if required_regions:
            edit_input["requiredRegionsAtOffsets"] = required_regions

        data = self._call_tool("edit_recording", {
            "id": track_id,
            "input": edit_input,
        }, timeout=60)
        # New API: data.recordingEdit.{id, status}
        inner = (data.get("data") or {}).get("recordingEdit", {})
        return {"job_id": inner.get("id", ""), "status": inner.get("status", "")}

    def get_adaptation_status(self, job_id: str) -> dict:
        """Check adaptation job status."""
        data = self._call_tool("poll_edit_recording", {"id": job_id})
        inner = (data.get("data") or {}).get("recordingEditJob", data)
        return inner

    def download_adapted_track(self, job_id: str, edit_id: str,
                               output_path: Path) -> Path:
        """Download an adapted track version."""
        data = self._call_tool("download_recording_edit", {
            "input": {"recordingEditJobId": job_id},
        })
        # New API: data.recordingEditDownload.assetUrl
        url = ((data.get("data") or {}).get("recordingEditDownload") or {}).get("assetUrl", "")
        if not url:
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
        """Download a music track via MCP DownloadRecording tool."""
        stem_type = (stem or "FULL").upper()
        args: dict = {
            "id": track_id,
            "options": {
                "fileType": format.upper(),
                "stemType": stem_type,
            },
        }

        data = self._call_tool("download_music_track", args)
        # New API: data.recordingDownload.assetUrl
        url = ((data.get("data") or {}).get("recordingDownload") or {}).get("assetUrl", "")
        if not url:
            url = data.get("url", data.get("download_url", ""))
        if not url:
            raise RuntimeError(f"No download URL for track {track_id}")
        return self._download_file(url, output_path)

    def download_sfx(self, sfx_id: str, output_path: Path, *,
                     format: str = "mp3") -> Path:
        """Download a sound effect via MCP DownloadSoundEffect tool."""
        data = self._call_tool("download_sound_effect", {
            "id": sfx_id,
            "options": {"fileType": format.upper()},
        })
        # New API: data.soundEffectDownload.assetUrl
        url = ((data.get("data") or {}).get("soundEffectDownload") or {}).get("assetUrl", "")
        if not url:
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

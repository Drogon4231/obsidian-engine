"""Tests for clients/epidemic_client.py — Epidemic Sound MCP API client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEpidemicSoundClient:
    """Test the MCP protocol wrapper for Epidemic Sound API."""

    def _make_client(self, key="fake-test-key"):
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": key}):
            from clients.epidemic_client import EpidemicSoundClient
            return EpidemicSoundClient()

    def _mock_mcp_response(self, result_data):
        """Create a mock response matching MCP JSON-RPC format."""
        import json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": json.dumps(result_data)}]
            },
            "id": 1,
        })
        mock_resp.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": json.dumps(result_data)}]
            },
            "id": 1,
        }
        return mock_resp

    def test_init_reads_env_var(self):
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": "test-key-123"}):
            from clients.epidemic_client import EpidemicSoundClient
            c = EpidemicSoundClient()
            assert c._api_key == "test-key-123"

    def test_init_explicit_key(self):
        from clients.epidemic_client import EpidemicSoundClient
        c = EpidemicSoundClient(api_key="explicit-key")
        assert c._api_key == "explicit-key"

    def test_no_key_raises_on_request(self):
        with patch.dict("os.environ", {}, clear=True):
            from clients.epidemic_client import EpidemicSoundClient
            from clients.epidemic_client import KeyExpiredError
            c = EpidemicSoundClient(api_key="")
            with pytest.raises(KeyExpiredError, match="not set"):
                c._call_tool("test_tool")

    @patch("requests.post")
    def test_bearer_auth_header(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({"results": []})

        c = self._make_client()
        c._call_tool("test_tool", {"arg": "val"})

        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer fake-test-key"
        assert kwargs["json"]["method"] == "tools/call"
        assert kwargs["json"]["params"]["name"] == "test_tool"

    @patch("requests.post")
    def test_401_raises_key_expired(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        from clients.epidemic_client import KeyExpiredError
        c = self._make_client()
        with pytest.raises(KeyExpiredError, match="expired"):
            c._call_tool("test_tool")

    @patch("requests.post")
    def test_403_raises_key_expired(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_post.return_value = mock_resp

        from clients.epidemic_client import KeyExpiredError
        c = self._make_client()
        with pytest.raises(KeyExpiredError, match="expired"):
            c._call_tool("test_tool")

    @patch("requests.post")
    def test_search_music(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "recordings": [{"id": "123", "title": "Test Track", "bpm": 90}]
        })

        c = self._make_client()
        results = c.search_music(keyword="dark cinematic", bpm_min=60, bpm_max=100, limit=5)

        assert len(results) == 1
        assert results[0]["id"] == "123"
        # Verify tool name
        call_json = mock_post.call_args[1]["json"]
        assert call_json["params"]["name"] == "search_music"

    @patch("requests.post")
    def test_search_sfx(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "sound_effects": [{"id": "sfx1", "title": "Boom"}]
        })

        c = self._make_client()
        results = c.search_sfx(keyword="dramatic boom")

        assert len(results) == 1
        assert results[0]["id"] == "sfx1"
        call_json = mock_post.call_args[1]["json"]
        assert call_json["params"]["name"] == "search_sound_effects"

    @patch("requests.post")
    def test_adapt_track(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "job_id": "job123", "status": "PENDING"
        })

        c = self._make_client()
        result = c.adapt_track("track1", target_duration_ms=300000)

        assert result["job_id"] == "job123"
        call_json = mock_post.call_args[1]["json"]
        assert call_json["params"]["name"] == "edit_recording"

    @patch("requests.post")
    def test_check_key_valid_true(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({"recordings": []})

        c = self._make_client()
        assert c.check_key_valid() is True

    @patch("requests.post")
    def test_check_key_valid_false_on_401(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        c = self._make_client()
        assert c.check_key_valid() is False

    def test_check_key_valid_false_no_key(self):
        from clients.epidemic_client import EpidemicSoundClient
        c = EpidemicSoundClient(api_key="")
        assert c.check_key_valid() is False

    @patch("requests.post")
    def test_browse_voices(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "voices": [{"id": "v1", "title": "Alex"}]
        })

        c = self._make_client()
        voices = c.browse_voices()
        assert len(voices) == 1
        assert voices[0]["id"] == "v1"

    @patch("requests.post")
    def test_find_similar(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "recordings": [{"id": "sim1"}]
        })

        c = self._make_client()
        results = c.find_similar("track1")
        assert len(results) == 1

    @patch("requests.post")
    def test_download_track(self, mock_post):
        mock_post.return_value = self._mock_mcp_response({
            "url": "https://cdn.epidemic.com/test.mp3"
        })

        c = self._make_client()
        with patch("requests.get") as mock_get:
            mock_dl = MagicMock()
            mock_dl.status_code = 200
            mock_dl.iter_content.return_value = [b"fake mp3 data"]
            mock_get.return_value = mock_dl

            result = c.download_track("track1", Path("/tmp/test_epidemic.mp3"))
            assert result == Path("/tmp/test_epidemic.mp3")

    @patch("requests.post")
    def test_mcp_error_response(self, mock_post):
        import json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Tool not found"},
            "id": 1,
        })
        mock_resp.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Tool not found"},
            "id": 1,
        }
        mock_post.return_value = mock_resp

        c = self._make_client()
        with pytest.raises(RuntimeError, match="Tool not found"):
            c._call_tool("nonexistent_tool")


class TestKeyExpiredError:
    """Test that KeyExpiredError is importable and behaves as expected."""

    def test_is_exception(self):
        from clients.epidemic_client import KeyExpiredError
        assert issubclass(KeyExpiredError, Exception)

    def test_message(self):
        from clients.epidemic_client import KeyExpiredError
        err = KeyExpiredError("test message")
        assert str(err) == "test message"

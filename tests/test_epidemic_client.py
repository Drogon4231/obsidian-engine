"""Tests for clients/epidemic_client.py — Epidemic Sound API client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEpidemicSoundClient:
    """Test the HTTP wrapper for Epidemic Sound MCP API."""

    def _make_client(self, key="fake-test-key"):
        with patch.dict("os.environ", {"EPIDEMIC_SOUND_API_KEY": key}):
            from clients.epidemic_client import EpidemicSoundClient
            return EpidemicSoundClient()

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
                c._request("GET", "/test")

    @patch("requests.request")
    def test_bearer_auth_header(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"results": []}'
        mock_resp.json.return_value = {"results": []}
        mock_req.return_value = mock_resp

        c = self._make_client()
        c._request("GET", "/test")

        args, kwargs = mock_req.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer fake-test-key"

    @patch("requests.request")
    def test_401_raises_key_expired(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_req.return_value = mock_resp

        from clients.epidemic_client import KeyExpiredError
        c = self._make_client()
        with pytest.raises(KeyExpiredError, match="expired"):
            c._request("GET", "/test")

    @patch("requests.request")
    def test_403_raises_key_expired(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp

        from clients.epidemic_client import KeyExpiredError
        c = self._make_client()
        with pytest.raises(KeyExpiredError, match="expired"):
            c._request("GET", "/test")

    @patch("requests.request")
    def test_search_music(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"recordings": [{"id": "123", "title": "Test Track", "bpm": 90}]}'
        mock_resp.json.return_value = {"recordings": [{"id": "123", "title": "Test Track", "bpm": 90}]}
        mock_req.return_value = mock_resp

        c = self._make_client()
        results = c.search_music(keyword="dark cinematic", bpm_min=60, bpm_max=100, limit=5)

        assert len(results) == 1
        assert results[0]["id"] == "123"
        assert results[0]["title"] == "Test Track"

    @patch("requests.request")
    def test_search_sfx(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"sound_effects": [{"id": "sfx1", "title": "Boom"}]}'
        mock_resp.json.return_value = {"sound_effects": [{"id": "sfx1", "title": "Boom"}]}
        mock_req.return_value = mock_resp

        c = self._make_client()
        results = c.search_sfx(keyword="dramatic boom")

        assert len(results) == 1
        assert results[0]["id"] == "sfx1"

    @patch("requests.request")
    def test_adapt_track(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"job_id": "job123", "status": "PENDING"}'
        mock_resp.json.return_value = {"job_id": "job123", "status": "PENDING"}
        mock_req.return_value = mock_resp

        c = self._make_client()
        result = c.adapt_track("track1", target_duration_ms=300000)

        assert result["job_id"] == "job123"
        assert result["status"] == "PENDING"

    @patch("requests.request")
    def test_check_key_valid_true(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"recordings": []}'
        mock_resp.json.return_value = {"recordings": []}
        mock_req.return_value = mock_resp

        c = self._make_client()
        assert c.check_key_valid() is True

    @patch("requests.request")
    def test_check_key_valid_false_on_401(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_req.return_value = mock_resp

        c = self._make_client()
        assert c.check_key_valid() is False

    def test_check_key_valid_false_no_key(self):
        from clients.epidemic_client import EpidemicSoundClient
        c = EpidemicSoundClient(api_key="")
        assert c.check_key_valid() is False

    @patch("requests.request")
    def test_browse_voices(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"voices": [{"id": "v1", "title": "Alex"}]}'
        mock_resp.json.return_value = {"voices": [{"id": "v1", "title": "Alex"}]}
        mock_req.return_value = mock_resp

        c = self._make_client()
        voices = c.browse_voices()
        assert len(voices) == 1
        assert voices[0]["id"] == "v1"

    @patch("requests.request")
    def test_find_similar(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"recordings": [{"id": "sim1"}]}'
        mock_resp.json.return_value = {"recordings": [{"id": "sim1"}]}
        mock_req.return_value = mock_resp

        c = self._make_client()
        results = c.find_similar("track1")
        assert len(results) == 1

    @patch("requests.request")
    def test_download_track(self, mock_req):
        # First call: get download URL
        mock_resp_url = MagicMock()
        mock_resp_url.status_code = 200
        mock_resp_url.text = '{"url": "https://cdn.epidemic.com/test.mp3"}'
        mock_resp_url.json.return_value = {"url": "https://cdn.epidemic.com/test.mp3"}

        # Second call: actual download
        mock_resp_dl = MagicMock()
        mock_resp_dl.status_code = 200
        mock_resp_dl.iter_content.return_value = [b"fake mp3 data"]

        mock_req.side_effect = [mock_resp_url]

        c = self._make_client()
        with patch("requests.get") as mock_get:
            mock_get.return_value = mock_resp_dl
            result = c.download_track("track1", Path("/tmp/test_epidemic.mp3"))
            assert result == Path("/tmp/test_epidemic.mp3")


class TestKeyExpiredError:
    """Test that KeyExpiredError is importable and behaves as expected."""

    def test_is_exception(self):
        from clients.epidemic_client import KeyExpiredError
        assert issubclass(KeyExpiredError, Exception)

    def test_message(self):
        from clients.epidemic_client import KeyExpiredError
        err = KeyExpiredError("test message")
        assert str(err) == "test message"

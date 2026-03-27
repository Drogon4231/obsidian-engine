"""Tests for server/notify.py — Telegram + Discord dual-send notification system."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── _tg() transport ──────────────────────────────────────────────────────────

class TestTgTransport:
    @patch("server.notify.requests.post")
    def test_successful_send_returns_true(self, mock_post):
        """_tg() returns True when Telegram API returns 200."""
        mock_post.return_value = MagicMock(status_code=200)
        with patch("server.notify.TG_TOKEN", "tok123"), \
             patch("server.notify.TG_CHAT_ID", "chat456"):
            from server.notify import _tg
            result = _tg("Hello world")
        assert result is True
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "bot" in url and "tok123" in url and "sendMessage" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "chat456"
        assert payload["text"] == "Hello world"
        assert payload["parse_mode"] == "Markdown"

    def test_missing_token_returns_false(self):
        """_tg() returns False when TELEGRAM_BOT_TOKEN is empty."""
        with patch("server.notify.TG_TOKEN", ""), \
             patch("server.notify.TG_CHAT_ID", "chat456"):
            from server.notify import _tg
            result = _tg("Hello")
        assert result is False

    def test_missing_chat_id_returns_false(self):
        """_tg() returns False when TELEGRAM_CHAT_ID is empty."""
        with patch("server.notify.TG_TOKEN", "tok123"), \
             patch("server.notify.TG_CHAT_ID", ""):
            from server.notify import _tg
            result = _tg("Hello")
        assert result is False

    @patch("server.notify.requests.post", side_effect=ConnectionError("network down"))
    def test_request_exception_returns_false(self, mock_post):
        """_tg() returns False when requests.post raises."""
        with patch("server.notify.TG_TOKEN", "tok123"), \
             patch("server.notify.TG_CHAT_ID", "chat456"):
            from server.notify import _tg
            result = _tg("Hello")
        assert result is False


# ── _send() transport ────────────────────────────────────────────────────────

class TestSendTransport:
    @patch("server.notify.requests.post")
    def test_successful_send_returns_true(self, mock_post):
        """_send() returns True when Discord returns 204."""
        mock_post.return_value = MagicMock(status_code=204)
        with patch("server.notify.WEBHOOK_URL", "https://discord.com/api/webhooks/test"):
            from server.notify import _send
            result = _send({"embeds": [{"title": "Test"}]})
        assert result is True
        mock_post.assert_called_once()

    @patch("server.notify.requests.post")
    def test_send_200_also_succeeds(self, mock_post):
        """_send() returns True for status 200 as well."""
        mock_post.return_value = MagicMock(status_code=200)
        with patch("server.notify.WEBHOOK_URL", "https://discord.com/api/webhooks/test"):
            from server.notify import _send
            result = _send({"content": "hi"})
        assert result is True

    def test_missing_webhook_url_returns_false(self):
        """_send() returns False when DISCORD_WEBHOOK_URL is empty."""
        with patch("server.notify.WEBHOOK_URL", ""):
            from server.notify import _send
            result = _send({"embeds": [{"title": "Test"}]})
        assert result is False

    @patch("server.notify.requests.post", side_effect=Exception("timeout"))
    def test_request_exception_returns_false(self, mock_post):
        """_send() returns False when requests.post raises."""
        with patch("server.notify.WEBHOOK_URL", "https://discord.com/api/webhooks/test"):
            from server.notify import _send
            result = _send({"embeds": [{"title": "Test"}]})
        assert result is False


# ── notify_pipeline_start ────────────────────────────────────────────────────

class TestNotifyPipelineStart:
    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_calls_both_transports_with_topic(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_start
        notify_pipeline_start("Ancient Rome")
        mock_tg.assert_called_once()
        assert "Ancient Rome" in mock_tg.call_args[0][0]
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert "Ancient Rome" in payload["embeds"][0]["description"]


# ── notify_pipeline_complete ─────────────────────────────────────────────────

class TestNotifyPipelineComplete:
    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_formats_all_fields(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_complete
        notify_pipeline_complete(
            topic="Ancient Rome",
            title="The Fall of Rome",
            youtube_url="https://youtube.com/watch?v=abc",
            elapsed_minutes=42.5,
        )
        mock_tg.assert_called_once()
        tg_msg = mock_tg.call_args[0][0]
        assert "42.5" in tg_msg
        assert "The Fall of Rome" in tg_msg
        assert "youtube.com" in tg_msg

        mock_send.assert_called_once()
        desc = mock_send.call_args[0][0]["embeds"][0]["description"]
        assert "Ancient Rome" in desc
        assert "The Fall of Rome" in desc
        assert "42.5" in desc

    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_includes_short_url_when_provided(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_complete
        notify_pipeline_complete(
            topic="Rome",
            title="Fall",
            youtube_url="https://youtube.com/watch?v=abc",
            elapsed_minutes=10.0,
            short_url="https://youtube.com/shorts/xyz",
        )
        tg_msg = mock_tg.call_args[0][0]
        assert "shorts/xyz" in tg_msg
        desc = mock_send.call_args[0][0]["embeds"][0]["description"]
        assert "shorts/xyz" in desc

    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_calls_both_transports(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_complete
        notify_pipeline_complete("T", "Title", "url", 1.0)
        mock_tg.assert_called_once()
        mock_send.assert_called_once()


# ── notify_pipeline_failed ───────────────────────────────────────────────────

class TestNotifyPipelineFailed:
    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_formats_stage_and_error(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_failed
        notify_pipeline_failed("Rome", "Stage 3", "NullPointerError in narrative")
        tg_msg = mock_tg.call_args[0][0]
        assert "Stage 3" in tg_msg
        assert "NullPointerError" in tg_msg
        desc = mock_send.call_args[0][0]["embeds"][0]["description"]
        assert "Stage 3" in desc
        assert "NullPointerError" in desc

    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_calls_both_transports(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_failed
        notify_pipeline_failed("T", "S", "E")
        mock_tg.assert_called_once()
        mock_send.assert_called_once()

    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_truncates_long_error(self, mock_tg, mock_send):
        from server.notify import notify_pipeline_failed
        long_error = "x" * 1000
        notify_pipeline_failed("T", "S", long_error)
        tg_msg = mock_tg.call_args[0][0]
        assert len(long_error) > 300
        # TG message truncates to 300 chars
        assert "x" * 300 in tg_msg
        assert "x" * 301 not in tg_msg


# ── notify_short_complete ────────────────────────────────────────────────────

class TestNotifyShortComplete:
    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_calls_both_transports(self, mock_tg, mock_send):
        from server.notify import notify_short_complete
        notify_short_complete("Short Title", "https://youtube.com/shorts/abc")
        mock_tg.assert_called_once()
        assert "Short Title" in mock_tg.call_args[0][0]
        assert "shorts/abc" in mock_tg.call_args[0][0]
        mock_send.assert_called_once()
        desc = mock_send.call_args[0][0]["embeds"][0]["description"]
        assert "Short Title" in desc


# ── notify_community_teaser ──────────────────────────────────────────────────

class TestNotifyCommunityTeaser:
    @patch("server.notify._send", return_value=True)
    @patch("server.notify._tg", return_value=True)
    def test_calls_tg(self, mock_tg, mock_send):
        from server.notify import notify_community_teaser
        notify_community_teaser("Ancient Rome", "The Fall of Rome")
        mock_tg.assert_called_once()
        tg_msg = mock_tg.call_args[0][0]
        assert "The Fall of Rome" in tg_msg
        assert "Community" in tg_msg

"""Tests for notifier.py — Discord webhook notifications."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import notifier


class TestNotifier:
    def test_notify_no_webhook_url(self, capsys):
        """notify() prints fallback when no webhook URL configured."""
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', ''):
            notifier.notify("Test", "Hello")
        captured = capsys.readouterr()
        assert "Test" in captured.out or "notifier" in captured.out.lower()

    @patch('server.notifier.requests')
    def test_notify_sends_embed(self, mock_requests):
        """notify() sends a proper Discord embed when URL is set."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_requests.post.return_value = mock_resp

        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/test'):
            notifier.notify("Test Title", "Test message", color=0x10B981)

        mock_requests.post.assert_called_once()
        payload = mock_requests.post.call_args.kwargs.get('json')
        assert payload is not None
        embeds = payload.get("embeds", [])
        assert len(embeds) == 1
        assert embeds[0]["title"] == "Test Title"

    @patch('server.notifier.requests')
    def test_notify_never_crashes(self, mock_requests):
        """notify() must never raise, even with bad data."""
        mock_requests.post.side_effect = ConnectionError("mock network error")
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', 'https://invalid'):
            # Should not raise even with bad data and network errors
            notifier.notify(None, None)
            notifier.notify("", "")

    def test_pipeline_start(self, capsys):
        """notify_pipeline_start produces output."""
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', ''):
            notifier.notify_pipeline_start("Test Topic")
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_pipeline_complete(self, capsys):
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', ''):
            notifier.notify_pipeline_complete("Test Topic", 12.5)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_pipeline_failed(self, capsys):
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', ''):
            notifier.notify_pipeline_failed("Test Topic", "Some error", "Stage 3")
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_trend_alert(self, capsys):
        with patch.object(notifier, 'DISCORD_WEBHOOK_URL', ''):
            notifier.notify_trend_alert("Trending Topic", 0.85, ["google", "reddit"])
        captured = capsys.readouterr()
        assert len(captured.out) > 0

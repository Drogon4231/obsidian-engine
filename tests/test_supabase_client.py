"""Tests for supabase_client.py — topic claiming, save_video dedup, era rotation."""
import sys
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from clients import supabase_client


class TestGetClient:
    def test_singleton_caches_client(self):
        mock_client = MagicMock()
        with patch.object(supabase_client, '_cached_client', mock_client):
            result = supabase_client.get_client()
            assert result is mock_client

    def test_thread_lock_exists(self):
        assert supabase_client._client_lock is not None
        assert isinstance(supabase_client._client_lock, type(threading.Lock()))

    def test_raises_without_credentials(self):
        original = supabase_client._cached_client
        try:
            supabase_client._cached_client = None
            with patch.object(supabase_client, 'SUPABASE_URL', ''):
                with patch.object(supabase_client, 'SUPABASE_KEY', ''):
                    try:
                        supabase_client.get_client()
                        assert False, "Should have raised"
                    except Exception as e:
                        assert "SUPABASE_URL" in str(e)
        finally:
            supabase_client._cached_client = original


class TestClaimTopic:
    def test_successful_claim(self):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "abc", "status": "in_progress"}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        with patch.object(supabase_client, 'get_client', return_value=mock_client):
            assert supabase_client.claim_topic("abc") is True

    def test_failed_claim_already_taken(self):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []  # No rows matched — already claimed
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        with patch.object(supabase_client, 'get_client', return_value=mock_client):
            assert supabase_client.claim_topic("abc") is False


class TestMarkTopicStatus:
    def test_done_sets_processed_at(self):
        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        with patch.object(supabase_client, 'get_client', return_value=mock_client):
            supabase_client.mark_topic_status("id-1", "done")
            call_args = mock_client.table.return_value.update.call_args[0][0]
            assert "processed_at" in call_args
            assert call_args["status"] == "done"

    def test_failed_sets_processed_at(self):
        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        with patch.object(supabase_client, 'get_client', return_value=mock_client):
            supabase_client.mark_topic_status("id-1", "failed")
            call_args = mock_client.table.return_value.update.call_args[0][0]
            assert "processed_at" in call_args

    def test_queued_no_processed_at(self):
        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        with patch.object(supabase_client, 'get_client', return_value=mock_client):
            supabase_client.mark_topic_status("id-1", "queued")
            call_args = mock_client.table.return_value.update.call_args[0][0]
            assert "processed_at" not in call_args
            assert call_args["status"] == "queued"


class TestSaveVideo:
    def _mock_client(self):
        mock = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "vid-1"}]
        mock.table.return_value.insert.return_value.execute.return_value = mock_result
        mock.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result
        mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock.table.return_value.select.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return mock

    def test_inserts_new_video(self):
        mock = self._mock_client()
        with patch.object(supabase_client, 'get_client', return_value=mock):
            result = supabase_client.save_video(
                "Rome", "Fall of Rome", "https://yt.be/x", "abc123",
                "/path/script.txt", "/path/video.mp4", 600, 1500, {}
            )
            assert result is not None
            mock.table.return_value.insert.assert_called_once()

    def test_updates_existing_by_youtube_id(self):
        mock = self._mock_client()
        # Simulate existing video found
        mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "existing-vid"}]
        )
        with patch.object(supabase_client, 'get_client', return_value=mock):
            supabase_client.save_video(
                "Rome", "Fall of Rome", "https://yt.be/x", "abc123",
                "/path/script.txt", "/path/video.mp4", 600, 1500, {}
            )
            mock.table.return_value.update.assert_called()

    def test_dedup_without_youtube_id(self):
        """When youtube_id is None, should check for existing by topic."""
        mock = self._mock_client()
        # Simulate existing video with null youtube_id for same topic
        mock.table.return_value.select.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "existing-null-vid"}]
        )
        with patch.object(supabase_client, 'get_client', return_value=mock):
            supabase_client.save_video(
                "Rome", "Fall of Rome", None, None,
                "/path/script.txt", "/path/video.mp4", 600, 1500, {}
            )
            # Should update, not insert
            mock.table.return_value.update.assert_called()

    def test_insert_when_no_youtube_id_no_existing(self):
        """When youtube_id is None and no existing record, should insert."""
        mock = self._mock_client()
        with patch.object(supabase_client, 'get_client', return_value=mock):
            supabase_client.save_video(
                "New Topic", "New Video", None, None,
                "/path/script.txt", "/path/video.mp4", 600, 1500, {}
            )
            mock.table.return_value.insert.assert_called_once()


class TestGetNextTopic:
    def _mock_client_with_topics(self, topics, recent_videos=None):
        mock = MagicMock()
        # Topics query
        topic_result = MagicMock()
        topic_result.data = topics
        mock.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value = topic_result

        # Recent videos query (for era rotation)
        video_result = MagicMock()
        video_result.data = recent_videos or []
        mock.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = video_result

        # claim_topic success
        claim_result = MagicMock()
        claim_result.data = [{"id": "claimed"}]
        mock.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = claim_result

        return mock

    def test_returns_none_when_empty(self):
        mock = self._mock_client_with_topics([])
        with patch.object(supabase_client, 'get_client', return_value=mock):
            assert supabase_client.get_next_topic() is None

    def test_returns_highest_scored(self):
        topics = [
            {"id": "1", "topic": "Caesar", "score": 0.9},
            {"id": "2", "topic": "Pyramids", "score": 0.5},
        ]
        mock = self._mock_client_with_topics(topics)
        with patch.object(supabase_client, 'get_client', return_value=mock):
            result = supabase_client.get_next_topic()
            assert result is not None
            assert result["topic"] == "Caesar"


class TestAddTopic:
    def test_successful_add(self):
        mock = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "new", "topic": "Test Topic"}]
        mock.table.return_value.insert.return_value.execute.return_value = mock_result
        with patch.object(supabase_client, 'get_client', return_value=mock):
            result = supabase_client.add_topic("Test Topic", source="manual", score=0.8)
            assert result is not None

    def test_duplicate_handled(self):
        mock = MagicMock()
        mock.table.return_value.insert.return_value.execute.side_effect = Exception("duplicate key value violates unique constraint")
        with patch.object(supabase_client, 'get_client', return_value=mock):
            # Should not raise, just print warning
            result = supabase_client.add_topic("Existing Topic")
            assert result is None


class TestThreadSafety:
    def test_lock_exists(self):
        assert hasattr(supabase_client, '_client_lock')

    def test_cached_client_starts_populated(self):
        """After module import, cached client may be set from previous tests."""
        # Just verify the attribute exists
        assert hasattr(supabase_client, '_cached_client')

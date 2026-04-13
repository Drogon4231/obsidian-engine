"""Tests for server/topic_store.py — SQLite topic deduplication."""
import pytest
from unittest.mock import patch

import server.topic_store as ts


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path):
    """Redirect DB to a temp file so tests don't pollute the real store."""
    db = tmp_path / "topic_store.db"
    with patch.object(ts, "DB_PATH", db):
        yield db


@pytest.mark.unit
class TestGetConn:
    """Test SQLite connection and table creation."""

    def test_creates_table(self, use_temp_db):
        conn = ts._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='covered_topics'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_wal_mode_enabled(self, use_temp_db):
        conn = ts._get_conn()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()


@pytest.mark.unit
class TestRecordTopic:
    """Test recording covered topics."""

    def test_inserts_row(self, use_temp_db):
        ts.record_topic("The Fall of Rome", angle="military decline")
        conn = ts._get_conn()
        rows = conn.execute("SELECT topic, angle FROM covered_topics").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "The Fall of Rome"
        assert rows[0][1] == "military decline"

    def test_all_fields_stored(self, use_temp_db):
        ts.record_topic("Topic A", angle="angle", title="Title", youtube_id="abc123")
        conn = ts._get_conn()
        row = conn.execute(
            "SELECT topic, angle, title, youtube_id, covered_at FROM covered_topics"
        ).fetchone()
        conn.close()
        assert row[0] == "Topic A"
        assert row[1] == "angle"
        assert row[2] == "Title"
        assert row[3] == "abc123"
        assert row[4]  # covered_at should be non-empty ISO timestamp

    def test_multiple_inserts(self, use_temp_db):
        ts.record_topic("Topic A")
        ts.record_topic("Topic B")
        ts.record_topic("Topic C")
        conn = ts._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM covered_topics").fetchone()[0]
        conn.close()
        assert count == 3


@pytest.mark.unit
class TestListCovered:
    """Test listing covered topics."""

    def test_empty_store(self, use_temp_db):
        assert ts.list_covered() == []

    def test_returns_recent_first(self, use_temp_db):
        ts.record_topic("First")
        ts.record_topic("Second")
        result = ts.list_covered()
        assert result[0]["topic"] == "Second"
        assert result[1]["topic"] == "First"

    def test_limit_parameter(self, use_temp_db):
        for i in range(10):
            ts.record_topic(f"Topic {i}")
        result = ts.list_covered(limit=3)
        assert len(result) == 3

    def test_dict_structure(self, use_temp_db):
        ts.record_topic("Test", angle="a", title="t", youtube_id="yt1")
        result = ts.list_covered()[0]
        assert set(result.keys()) == {"topic", "angle", "title", "youtube_id", "covered_at"}


@pytest.mark.unit
class TestKeywordMatch:
    """Test fallback keyword matching."""

    def test_substring_match(self):
        past = [{"topic": "The Fall of Rome"}]
        is_dup, matched = ts._keyword_match("Fall of Rome", past)
        assert is_dup
        assert matched == "The Fall of Rome"

    def test_reverse_substring(self):
        past = [{"topic": "Rome"}]
        is_dup, matched = ts._keyword_match("The Fall of Rome and its Legacy", past)
        assert is_dup

    def test_no_match(self):
        past = [{"topic": "Ancient Egypt"}]
        is_dup, _ = ts._keyword_match("Medieval Japan", past)
        assert not is_dup

    def test_case_insensitive(self):
        past = [{"topic": "THE FALL OF ROME"}]
        is_dup, _ = ts._keyword_match("the fall of rome", past)
        assert is_dup

    def test_empty_past(self):
        is_dup, _ = ts._keyword_match("anything", [])
        assert not is_dup


@pytest.mark.unit
class TestIsDuplicate:
    """Test the full dedup pipeline."""

    def test_no_duplicates_when_empty(self, use_temp_db):
        is_dup, _ = ts.is_duplicate("Any Topic")
        assert not is_dup

    @patch.object(ts, "_claude_similarity_check", return_value=(False, ""))
    def test_falls_back_to_keyword(self, mock_claude, use_temp_db):
        ts.record_topic("The Black Death")
        is_dup, matched = ts.is_duplicate("The Black Death in Europe")
        assert is_dup
        assert "Black Death" in matched

    @patch.object(ts, "_claude_similarity_check", return_value=(True, "The Fall of Rome"))
    def test_claude_detects_semantic_duplicate(self, mock_claude, use_temp_db):
        ts.record_topic("The Fall of Rome")
        is_dup, matched = ts.is_duplicate("Why the Roman Empire Collapsed")
        assert is_dup
        assert matched == "The Fall of Rome"

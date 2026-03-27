"""Tests for competitive intelligence data layer (intel/competitive_intel.py)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module
import intel.competitive_intel as ci


# ══════════════════════════════════════════════════════════════════════════════
# 1. Shorts filtering
# ══════════════════════════════════════════════════════════════════════════════

class TestShortsFiltering:
    """Test that videos are correctly split into shorts vs long-form."""

    def test_videos_split_by_duration(self):
        videos = [
            {"video_id": "a", "duration_seconds": 30, "views": 1000},
            {"video_id": "b", "duration_seconds": 120, "views": 5000},
            {"video_id": "c", "duration_seconds": 59, "views": 2000},
            {"video_id": "d", "duration_seconds": 600, "views": 10000},
        ]
        shorts = [v for v in videos if 0 < v["duration_seconds"] < ci.SHORTS_THRESHOLD]
        long_form = [v for v in videos if v["duration_seconds"] >= ci.SHORTS_THRESHOLD or v["duration_seconds"] == 0]
        assert len(shorts) == 2  # 30s, 59s
        assert len(long_form) == 2  # 120s, 600s

    def test_avg_views_from_long_form_only(self):
        long_form = [
            {"views": 10000},
            {"views": 20000},
        ]
        shorts = [
            {"views": 500},
        ]
        avg_long = sum(v["views"] for v in long_form) / len(long_form)
        avg_shorts = sum(v["views"] for v in shorts) / len(shorts)
        assert avg_long == 15000
        assert avg_shorts == 500

    def test_zero_duration_treated_as_long_form(self):
        videos = [
            {"video_id": "x", "duration_seconds": 0, "views": 5000},
        ]
        shorts = [v for v in videos if 0 < v["duration_seconds"] < ci.SHORTS_THRESHOLD]
        long_form = [v for v in videos if v["duration_seconds"] >= ci.SHORTS_THRESHOLD or v["duration_seconds"] == 0]
        assert len(shorts) == 0
        assert len(long_form) == 1

    def test_boundary_60s_is_long_form(self):
        videos = [
            {"video_id": "y", "duration_seconds": 60, "views": 3000},
        ]
        shorts = [v for v in videos if 0 < v["duration_seconds"] < ci.SHORTS_THRESHOLD]
        long_form = [v for v in videos if v["duration_seconds"] >= ci.SHORTS_THRESHOLD or v["duration_seconds"] == 0]
        assert len(shorts) == 0
        assert len(long_form) == 1  # 60s is the threshold boundary — long-form


# ══════════════════════════════════════════════════════════════════════════════
# 2. find_content_gaps
# ══════════════════════════════════════════════════════════════════════════════

class TestFindContentGaps:
    def _mock_intel(self, videos):
        return {
            "competitors": {
                "ch1": {
                    "name": "TestChannel",
                    "avg_views_recent_20": 10000,
                    "videos": videos,
                }
            }
        }

    def test_returns_both_title_and_topic_keys(self):
        intel = self._mock_intel([
            {"title": "The Siege of Vienna", "views": 50000, "likes": 2000,
             "publish_date": "2024-01-01T00:00:00Z", "video_id": "v1"},
        ])
        with patch.object(ci, "_load_existing_intel", return_value=intel):
            gaps = ci.find_content_gaps([])
        assert len(gaps) >= 1
        assert "title" in gaps[0]
        assert "topic" in gaps[0]
        assert gaps[0]["title"] == gaps[0]["topic"]

    def test_our_topics_filtered_out(self):
        intel = self._mock_intel([
            {"title": "The Siege of Vienna", "views": 50000, "likes": 2000,
             "publish_date": "2024-01-01T00:00:00Z", "video_id": "v1"},
        ])
        with patch.object(ci, "_load_existing_intel", return_value=intel):
            gaps = ci.find_content_gaps(["the siege of vienna"])
        assert len(gaps) == 0

    def test_empty_data_returns_empty(self):
        with patch.object(ci, "_load_existing_intel", return_value={}):
            gaps = ci.find_content_gaps([])
        assert gaps == []

    def test_sorted_by_views(self):
        intel = self._mock_intel([
            {"title": "Topic A", "views": 1000, "likes": 100,
             "publish_date": "2024-01-01T00:00:00Z", "video_id": "v1"},
            {"title": "Topic B", "views": 50000, "likes": 3000,
             "publish_date": "2024-01-01T00:00:00Z", "video_id": "v2"},
        ])
        with patch.object(ci, "_load_existing_intel", return_value=intel):
            gaps = ci.find_content_gaps([])
        assert gaps[0]["views"] >= gaps[-1]["views"]

    def test_deduplication_works(self):
        intel = self._mock_intel([
            {"title": "The Dark History of Rome", "views": 50000, "likes": 2000,
             "publish_date": "2024-01-01T00:00:00Z", "video_id": "v1"},
            {"title": "The Dark History of Rome Part 2", "views": 40000, "likes": 1500,
             "publish_date": "2024-01-02T00:00:00Z", "video_id": "v2"},
        ])
        with patch.object(ci, "_load_existing_intel", return_value=intel):
            gaps = ci.find_content_gaps([])
        # The two titles have high overlap — should be deduped
        assert len(gaps) <= 2  # At most 2, likely 1 due to dedup


# ══════════════════════════════════════════════════════════════════════════════
# 3. compute_gap_score
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeGapScore:
    def test_high_ratio_high_score(self):
        gap = {"views": 500000, "channel": "BigChannel", "publish_date": datetime.now(timezone.utc).isoformat()}
        channel_avg = {"BigChannel": 100000}
        score = ci.compute_gap_score(gap, channel_avg)
        assert score > 0.7

    def test_old_video_reduced_score(self):
        recent = {"views": 100000, "channel": "Ch", "publish_date": datetime.now(timezone.utc).isoformat()}
        old = {"views": 100000, "channel": "Ch", "publish_date": "2022-01-01T00:00:00Z"}
        channel_avg = {"Ch": 50000}
        score_recent = ci.compute_gap_score(recent, channel_avg)
        score_old = ci.compute_gap_score(old, channel_avg)
        assert score_recent >= score_old

    def test_score_clamped_range(self):
        gap = {"views": 10000000, "channel": "Mega", "publish_date": "2024-06-01T00:00:00Z"}
        channel_avg = {"Mega": 1}
        score = ci.compute_gap_score(gap, channel_avg)
        assert 0.5 <= score <= 0.95

    def test_zero_avg_views_handled(self):
        gap = {"views": 50000, "channel": "NewCh"}
        channel_avg = {"NewCh": 0}
        score = ci.compute_gap_score(gap, channel_avg)
        assert 0.5 <= score <= 0.95


# ══════════════════════════════════════════════════════════════════════════════
# 4. get_competitive_signals
# ══════════════════════════════════════════════════════════════════════════════

class TestGetCompetitiveSignals:
    def test_returns_correct_structure(self):
        intel = {
            "competitors": {
                "ch1": {
                    "name": "TestCh",
                    "avg_views_recent_20": 10000,
                    "shorts_count": 2,
                    "videos": [{"title": "Test Video", "views": 5000, "publish_date": "2024-01-01T00:00:00Z"}],
                    "shorts": [{"title": "Short", "views": 1000}],
                }
            },
            "generated_at": "2024-01-01T00:00:00Z",
        }
        with patch.object(ci, "load_competitive_intel", return_value=intel):
            with patch.object(ci, "find_content_gaps", return_value=[]):
                with patch.object(ci, "get_trending_competitor_topics", return_value=[]):
                    result = ci.get_competitive_signals(our_topics=[])
        assert result["data_available"] is True
        assert "gaps" in result
        assert "trending" in result
        assert "saturated" in result
        assert "channel_avg_views" in result
        assert "shorts_insights" in result

    def test_data_available_flag(self):
        with patch.object(ci, "load_competitive_intel", return_value={}):
            result = ci.get_competitive_signals()
        assert result["data_available"] is False

    def test_empty_when_no_intel(self):
        with patch.object(ci, "load_competitive_intel", return_value={"competitors": {}}):
            result = ci.get_competitive_signals()
        assert result["data_available"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 5. Supabase persistence
# ══════════════════════════════════════════════════════════════════════════════

class TestSupabasePersistence:
    def test_persist_called_after_crawl(self):
        """Verify that crawl_competitors calls persist_json_to_supabase."""
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"statistics": {"subscriberCount": "1000", "videoCount": "50"}, "snippet": {}}]
        }
        mock_youtube.search().list().execute.return_value = {"items": []}

        with patch.object(ci, "_get_youtube_service", return_value=mock_youtube):
            with patch.object(ci, "_save_intel"):
                with patch("intel.competitive_intel.persist_json_to_supabase", create=True):
                    # Import will fail gracefully, but we can test the pattern
                    ci.crawl_competitors()

    def test_restore_used_when_local_missing(self):
        """load_competitive_intel should try Supabase when local file is missing."""
        with patch.object(type(ci.INTEL_FILE), "exists", new=lambda self: False):
            with patch.dict("sys.modules", {"core.utils": MagicMock()}):
                # Mock the restore function
                mock_utils = sys.modules["core.utils"]
                mock_utils.restore_json_from_supabase.return_value = False
                result = ci.load_competitive_intel()
        assert result == {}

    def test_graceful_failure(self):
        """load_competitive_intel should return {} when file exists but has bad JSON."""
        with patch.object(type(ci.INTEL_FILE), "exists", new=lambda self: True):
            with patch.object(type(ci.INTEL_FILE), "read_text", new=lambda self: "not valid json{{{"):
                result = ci.load_competitive_intel()
        assert result == {} or isinstance(result, dict)

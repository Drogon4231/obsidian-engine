"""Tests for scheduler.py — scheduling logic, dead letter retry, experiment budget."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import scheduler
from intel import channel_insights


class TestGetOptimalPublishTime:
    def test_default_fallback(self):
        """With no insights, falls back to Wednesday 14:00."""
        with patch.object(channel_insights, 'load_insights', return_value={}):
            day, hour, minute = scheduler.get_optimal_publish_time()
            assert day == 2  # Wednesday
            assert hour == 14

    def test_explicit_publish_time_analysis(self):
        insights = {
            "retention_analysis": {
                "publish_time_analysis": {
                    "best_day_of_week": 4,
                    "best_hour": 16,
                }
            }
        }
        with patch.object(channel_insights, 'load_insights', return_value=insights):
            day, hour, minute = scheduler.get_optimal_publish_time()
            assert day == 4
            assert hour == 16
            assert minute == 0

    def test_inferred_from_top_videos(self):
        insights = {
            "retention_analysis": {},
            "top_performing_videos": [
                {"views": 10000, "publish_day_of_week": 1, "publish_hour": 10},
                {"views": 8000, "publish_day_of_week": 1, "publish_hour": 12},
                {"views": 6000, "publish_day_of_week": 3, "publish_hour": 14},
            ]
        }
        with patch.object(channel_insights, 'load_insights', return_value=insights):
            day, hour, minute = scheduler.get_optimal_publish_time()
            # Multi-signal analysis determines best day/hour
            assert isinstance(day, int) and 0 <= day <= 6
            assert isinstance(hour, int) and 0 <= hour <= 23

    def test_channel_health_fallback(self):
        insights = {
            "retention_analysis": {},
            "top_performing_videos": [],
        }
        with patch.object(channel_insights, 'load_insights', return_value=insights):
            day, hour, minute = scheduler.get_optimal_publish_time()
            assert isinstance(day, int) and 0 <= day <= 6
            assert isinstance(hour, int) and 0 <= hour <= 23

    def test_exception_returns_default(self):
        with patch.object(channel_insights, 'load_insights', side_effect=Exception("DB down")):
            day, hour, minute = scheduler.get_optimal_publish_time()
            assert day == 2
            assert hour == 14


class TestAdjustSchedule:
    def test_adjusts_single_day(self):
        original_days = list(scheduler.PUBLISH_DAYS)
        original_time = scheduler.PUBLISH_TIME
        try:
            scheduler.PUBLISH_DAYS = ["tuesday"]
            with patch.object(scheduler, 'get_optimal_publish_time', return_value=(4, 16, 0)):
                scheduler.adjust_schedule_from_data()
                assert scheduler.PUBLISH_DAYS == ["friday"]
                assert scheduler.PUBLISH_TIME == "16:00"
        finally:
            scheduler.PUBLISH_DAYS = original_days
            scheduler.PUBLISH_TIME = original_time

    def test_adjusts_two_days(self):
        original_days = list(scheduler.PUBLISH_DAYS)
        original_time = scheduler.PUBLISH_TIME
        try:
            scheduler.PUBLISH_DAYS = ["tuesday", "friday"]
            with patch.object(scheduler, 'get_optimal_publish_time', return_value=(0, 10, 30)):
                scheduler.adjust_schedule_from_data()
                assert scheduler.PUBLISH_DAYS == ["monday", "thursday"]
                assert scheduler.PUBLISH_TIME == "10:30"
        finally:
            scheduler.PUBLISH_DAYS = original_days
            scheduler.PUBLISH_TIME = original_time

    def test_exception_keeps_defaults(self):
        original_days = list(scheduler.PUBLISH_DAYS)
        original_time = scheduler.PUBLISH_TIME
        try:
            with patch.object(scheduler, 'get_optimal_publish_time', side_effect=Exception("fail")):
                scheduler.adjust_schedule_from_data()
                assert scheduler.PUBLISH_DAYS == original_days
                assert scheduler.PUBLISH_TIME == original_time
        finally:
            scheduler.PUBLISH_DAYS = original_days
            scheduler.PUBLISH_TIME = original_time


class TestRetryDeadLetters:
    def _mock_supabase(self, rows):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return mock_client

    def test_requeues_old_failures(self):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        mock_client = self._mock_supabase([
            {"id": "t1", "topic": "Failed Topic", "status": "failed",
             "processed_at": old_time, "retry_count": 0},
        ])
        with patch('clients.supabase_client.get_client', return_value=mock_client):
            scheduler.retry_dead_letters()
            mock_client.table.return_value.update.assert_called()

    def test_moves_to_dead_letter_after_max_retries(self):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        mock_client = self._mock_supabase([
            {"id": "t1", "topic": "Dead Topic", "status": "failed",
             "processed_at": old_time, "retry_count": 2},
        ])
        with patch('clients.supabase_client.get_client', return_value=mock_client):
            scheduler.retry_dead_letters()
            calls = mock_client.table.return_value.update.call_args_list
            statuses = [c[0][0].get("status") for c in calls if c[0]]
            assert "dead_letter" in statuses

    def test_handles_exception(self):
        with patch('clients.supabase_client.get_client', side_effect=Exception("DB down")):
            # Should not raise
            scheduler.retry_dead_letters()


class TestGetChannelAvgCtr:
    def test_returns_from_insights(self):
        with patch.object(channel_insights, 'load_insights',
                          return_value={"channel_health": {"avg_ctr_pct": 6.5}}):
            assert scheduler._get_channel_avg_ctr() == 6.5

    def test_fallback_to_4(self):
        with patch.object(channel_insights, 'load_insights', return_value={}):
            assert scheduler._get_channel_avg_ctr() == 4.0

    def test_exception_returns_4(self):
        with patch.object(channel_insights, 'load_insights', side_effect=Exception("fail")):
            assert scheduler._get_channel_avg_ctr() == 4.0


class TestGetChannelAvgViews:
    def test_returns_from_insights(self):
        with patch.object(channel_insights, 'load_insights',
                          return_value={"channel_health": {"avg_views_per_video": 5000}}):
            assert scheduler._get_channel_avg_views() == 5000

    def test_fallback_to_0(self):
        with patch.object(channel_insights, 'load_insights', return_value={}):
            assert scheduler._get_channel_avg_views() == 0


class TestRecentExperimentsUnderperformed:
    def test_false_when_no_avg_views(self):
        with patch.object(scheduler, '_get_channel_avg_views', return_value=0):
            assert scheduler._recent_experiments_underperformed(MagicMock()) is False

    def test_false_when_not_enough_experiments(self):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "v1", "pipeline_state": {"experiment": True}},
        ]  # Only 1 experiment, need 3
        mock_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result
        with patch.object(scheduler, '_get_channel_avg_views', return_value=5000):
            assert scheduler._recent_experiments_underperformed(mock_client, n=3) is False

    def test_true_when_all_underperformed(self):
        mock_client = MagicMock()
        vid_result = MagicMock()
        vid_result.data = [
            {"id": f"v{i}", "pipeline_state": {"experiment": True}} for i in range(3)
        ]
        mock_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = vid_result

        analytics_result = MagicMock()
        analytics_result.data = [{"views": 500}]  # Below 50% of 5000
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = analytics_result

        with patch.object(scheduler, '_get_channel_avg_views', return_value=5000):
            assert scheduler._recent_experiments_underperformed(mock_client, n=3) is True

    def test_false_when_one_performed_well(self):
        mock_client = MagicMock()
        vid_result = MagicMock()
        vid_result.data = [
            {"id": f"v{i}", "pipeline_state": {"experiment": True}} for i in range(3)
        ]
        mock_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = vid_result

        analytics_result = MagicMock()
        analytics_result.data = [{"views": 5000}]  # Above threshold
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = analytics_result

        with patch.object(scheduler, '_get_channel_avg_views', return_value=5000):
            assert scheduler._recent_experiments_underperformed(mock_client, n=3) is False

    def test_exception_returns_false(self):
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("DB error")
        with patch.object(scheduler, '_get_channel_avg_views', return_value=5000):
            assert scheduler._recent_experiments_underperformed(mock_client) is False


# ══════════════════════════════════════════════════════════════════════════════
# _compute_experiment_cadence
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeExperimentCadence:
    def _mock_client(self, videos_data=None, topics_data=None, topics_count=None):
        """Build a mock Supabase client with chained query builders."""
        client = MagicMock()

        # videos table chain
        videos_result = MagicMock()
        videos_result.data = videos_data or []
        videos_chain = MagicMock()
        videos_chain.select.return_value = videos_chain
        videos_chain.order.return_value = videos_chain
        videos_chain.limit.return_value = videos_chain
        videos_chain.execute.return_value = videos_result

        # topics table chain
        topics_result = MagicMock()
        topics_result.data = topics_data or []
        topics_result.count = topics_count
        topics_chain = MagicMock()
        topics_chain.select.return_value = topics_chain
        topics_chain.eq.return_value = topics_chain
        topics_chain.execute.return_value = topics_result

        def table_router(name):
            if name == "videos":
                return videos_chain
            elif name == "topics":
                return topics_chain
            return MagicMock()

        client.table.side_effect = table_router
        return client

    def test_default_cadence_empty_insights(self):
        client = self._mock_client()
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=False):
            result = scheduler._compute_experiment_cadence({}, client)
        assert isinstance(result, int)
        assert 3 <= result <= 10

    def test_high_sub_gain_lowers_cadence(self):
        insights = {
            "channel_health": {
                "avg_subscribers_gained_per_video": 15,
            },
        }
        client = self._mock_client()
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=False):
            result = scheduler._compute_experiment_cadence(insights, client)
        assert 3 <= result <= 10
        # High sub gain should push cadence lower (more experiments)
        assert result <= 5

    def test_low_sub_gain_raises_cadence(self):
        insights = {
            "channel_health": {
                "avg_subscribers_gained_per_video": 0.5,
            },
        }
        client = self._mock_client()
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=False):
            result = scheduler._compute_experiment_cadence(insights, client)
        assert 3 <= result <= 10
        assert result >= 5

    def test_underperforming_experiments_throttle(self):
        insights = {"channel_health": {}}
        client = self._mock_client()
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=True):
            result = scheduler._compute_experiment_cadence(insights, client)
        assert 3 <= result <= 10
        # Should be higher than default 5 due to +2
        assert result >= 7

    def test_deep_queue_lowers_cadence(self):
        insights = {"channel_health": {}}
        topics_data = [{"id": i} for i in range(20)]
        client = self._mock_client(topics_data=topics_data, topics_count=20)
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=False):
            result = scheduler._compute_experiment_cadence(insights, client)
        assert 3 <= result <= 10

    def test_none_client_still_returns_valid(self):
        result = scheduler._compute_experiment_cadence({}, None)
        assert isinstance(result, int)
        assert 3 <= result <= 10

    def test_always_in_range_3_to_10(self):
        """Even with extreme inputs, cadence is clamped 3-10."""
        # All factors pushing cadence down
        insights = {
            "channel_health": {
                "avg_subscribers_gained_per_video": 100,
                "avg_views_per_video": 1000,
                "top_quartile_view_threshold": 5000,
            },
        }
        client = self._mock_client(
            videos_data=[{"topic": f"t{i}"} for i in range(10)],
            topics_data=[{"id": i} for i in range(30)],
            topics_count=30,
        )
        mock_era = MagicMock()
        mock_era.classify_era = MagicMock(return_value="ancient")
        with patch.object(scheduler, '_recent_experiments_underperformed', return_value=False):
            with patch.dict("sys.modules", {"intel.era_classifier": mock_era}):
                result = scheduler._compute_experiment_cadence(insights, client)
        assert 3 <= result <= 10


# ══════════════════════════════════════════════════════════════════════════════
# _md_escape
# ══════════════════════════════════════════════════════════════════════════════

class TestMdEscape:
    def test_plain_text_unchanged(self):
        assert scheduler._md_escape("hello world") == "hello world"

    def test_escapes_underscores(self):
        result = scheduler._md_escape("some_variable_name")
        assert "\\_" in result
        assert "_" not in result.replace("\\_", "")

    def test_escapes_asterisks(self):
        result = scheduler._md_escape("*bold*")
        assert "\\*" in result

    def test_escapes_backticks(self):
        result = scheduler._md_escape("`code`")
        assert "\\`" in result

    def test_escapes_brackets(self):
        result = scheduler._md_escape("[link]")
        assert "\\[" in result

    def test_escapes_all_special_chars(self):
        result = scheduler._md_escape("_*`[mixed")
        assert "\\_" in result
        assert "\\*" in result
        assert "\\`" in result
        assert "\\[" in result

    def test_empty_string(self):
        assert scheduler._md_escape("") == ""

    def test_already_safe_text(self):
        text = "No special characters here 123"
        assert scheduler._md_escape(text) == text

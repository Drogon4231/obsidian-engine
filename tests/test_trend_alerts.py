"""Tests for intel/trend_alerts.py — content quality trend detection."""

from unittest.mock import patch

from intel.trend_alerts import (
    detect_trends,
    send_trend_alerts,
    run_trend_analysis,
    _check_declining_metric,
    _check_hook_retention,
    _check_positive_trends,
    _check_below_average,
)


def _make_video(title, retention=50.0, engagement=5.0, views=1000, subs=10):
    return {
        "title": title,
        "youtube_id": "test",
        "views": views,
        "avg_retention_pct": retention,
        "engagement_rate": engagement,
        "subscribers_gained": subs,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Declining Metric Detection
# ══════════════════════════════════════════════════════════════════════════════

class TestDecliningMetric:
    def test_detects_retention_drop(self):
        recent = [_make_video(f"r{i}", retention=35) for i in range(3)]
        older = [_make_video(f"o{i}", retention=50) for i in range(5)]
        alert = _check_declining_metric(
            recent, older, "avg_retention_pct", "Retention", "%", 10
        )
        assert alert is not None
        assert alert["severity"] in ("warning", "critical")
        assert alert["change_pct"] < -10

    def test_no_alert_on_stable(self):
        recent = [_make_video(f"r{i}", retention=50) for i in range(3)]
        older = [_make_video(f"o{i}", retention=48) for i in range(5)]
        alert = _check_declining_metric(
            recent, older, "avg_retention_pct", "Retention", "%", 10
        )
        assert alert is None

    def test_critical_on_severe_drop(self):
        recent = [_make_video(f"r{i}", retention=25) for i in range(3)]
        older = [_make_video(f"o{i}", retention=50) for i in range(5)]
        alert = _check_declining_metric(
            recent, older, "avg_retention_pct", "Retention", "%", 10
        )
        assert alert is not None
        assert alert["severity"] == "critical"

    def test_insufficient_data_returns_none(self):
        recent = [_make_video("r1", retention=30)]
        older = [_make_video("o1", retention=50)]
        alert = _check_declining_metric(
            recent, older, "avg_retention_pct", "Retention", "%", 10
        )
        assert alert is None

    def test_zero_older_avg_returns_none(self):
        recent = [_make_video(f"r{i}", views=100) for i in range(3)]
        older = [_make_video(f"o{i}", views=0) for i in range(3)]
        alert = _check_declining_metric(
            recent, older, "views", "Views", "", 20
        )
        assert alert is None


# ══════════════════════════════════════════════════════════════════════════════
# Hook Retention
# ══════════════════════════════════════════════════════════════════════════════

class TestHookRetention:
    def test_detects_hook_drop(self):
        insights = {
            "retention_curves": {
                "per_video": [
                    {"hook_retention_30s": 60},
                    {"hook_retention_30s": 58},
                    {"hook_retention_30s": 55},
                    {"hook_retention_30s": 75},
                    {"hook_retention_30s": 78},
                    {"hook_retention_30s": 80},
                ]
            }
        }
        alert = _check_hook_retention(insights)
        assert alert is not None
        assert "hook" in alert["title"].lower()

    def test_no_alert_stable_hooks(self):
        insights = {
            "retention_curves": {
                "per_video": [
                    {"hook_retention_30s": 72},
                    {"hook_retention_30s": 74},
                    {"hook_retention_30s": 70},
                    {"hook_retention_30s": 71},
                    {"hook_retention_30s": 73},
                ]
            }
        }
        alert = _check_hook_retention(insights)
        assert alert is None

    def test_no_data_returns_none(self):
        assert _check_hook_retention({}) is None
        assert _check_hook_retention({"retention_curves": {}}) is None


# ══════════════════════════════════════════════════════════════════════════════
# Positive Trends
# ══════════════════════════════════════════════════════════════════════════════

class TestPositiveTrends:
    def test_detects_improvement(self):
        recent = [_make_video(f"r{i}", retention=65) for i in range(3)]
        older = [_make_video(f"o{i}", retention=50) for i in range(5)]
        alerts = _check_positive_trends(recent, older)
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "positive"
        assert alerts[0]["change_pct"] > 0

    def test_no_alert_on_flat(self):
        recent = [_make_video(f"r{i}", retention=50) for i in range(3)]
        older = [_make_video(f"o{i}", retention=49) for i in range(5)]
        alerts = _check_positive_trends(recent, older)
        assert len(alerts) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Below Average Streak
# ══════════════════════════════════════════════════════════════════════════════

class TestBelowAverage:
    def test_detects_streak(self):
        # Channel avg retention ~50, recent all at 35
        all_videos = [_make_video(f"v{i}", retention=50) for i in range(10)]
        recent = [_make_video(f"r{i}", retention=35) for i in range(3)]
        # Prepend recent to all_videos so avg includes them
        combined = recent + all_videos
        alerts = _check_below_average(recent, combined)
        assert len(alerts) >= 1
        assert "below average" in alerts[0]["title"].lower()

    def test_no_alert_when_above(self):
        all_videos = [_make_video(f"v{i}", retention=50) for i in range(10)]
        recent = [_make_video(f"r{i}", retention=55) for i in range(3)]
        alerts = _check_below_average(recent, recent + all_videos)
        retention_alerts = [a for a in alerts if a["metric"] == "avg_retention_pct"]
        assert len(retention_alerts) == 0

    def test_insufficient_data(self):
        alerts = _check_below_average(
            [_make_video("r1")],
            [_make_video("v1"), _make_video("v2")]
        )
        assert len(alerts) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Full detect_trends
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectTrends:
    def test_returns_empty_with_few_videos(self):
        insights = {"per_video_stats": [_make_video("v1"), _make_video("v2")]}
        assert detect_trends(insights) == []

    def test_detects_multiple_issues(self):
        # Recent: low retention + low engagement
        recent = [_make_video(f"r{i}", retention=30, engagement=1.0, views=200) for i in range(5)]
        older = [_make_video(f"o{i}", retention=55, engagement=6.0, views=1500) for i in range(10)]
        insights = {"per_video_stats": recent + older}
        alerts = detect_trends(insights)
        # Should detect at least retention and engagement drops
        metrics = [a["metric"] for a in alerts]
        assert "avg_retention_pct" in metrics
        assert "engagement_rate" in metrics

    def test_no_alerts_on_healthy_channel(self):
        videos = [_make_video(f"v{i}", retention=52 + i % 5, engagement=5.0 + i % 2)
                  for i in range(15)]
        insights = {"per_video_stats": videos}
        alerts = detect_trends(insights)
        # Should have no warnings or critical
        warnings = [a for a in alerts if a["severity"] in ("warning", "critical")]
        assert len(warnings) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Telegram Sending
# ══════════════════════════════════════════════════════════════════════════════

class TestSendAlerts:
    def test_no_alerts_sends_nothing(self):
        assert send_trend_alerts([]) == 0

    @patch("server.notify._tg", return_value=True)
    def test_sends_grouped_message(self, mock_tg):
        alerts = [
            {"type": "declining_metric", "severity": "critical",
             "title": "Retention Declining", "detail": "50% → 30%"},
            {"type": "improving_metric", "severity": "positive",
             "title": "Views Improving", "detail": "1000 → 1500"},
        ]
        sent = send_trend_alerts(alerts)
        assert sent == 2
        mock_tg.assert_called_once()
        msg = mock_tg.call_args[0][0]
        assert "Retention Declining" in msg
        assert "Views Improving" in msg

    @patch("server.notify._tg", return_value=True)
    def test_critical_sorted_first(self, mock_tg):
        alerts = [
            {"type": "x", "severity": "positive", "title": "Good", "detail": "d"},
            {"type": "x", "severity": "critical", "title": "Bad", "detail": "d"},
        ]
        send_trend_alerts(alerts)
        msg = mock_tg.call_args[0][0]
        bad_pos = msg.index("Bad")
        good_pos = msg.index("Good")
        assert bad_pos < good_pos


# ══════════════════════════════════════════════════════════════════════════════
# Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestRunTrendAnalysis:
    @patch("server.notify._tg", return_value=True)
    def test_full_pipeline(self, mock_tg):
        recent = [_make_video(f"r{i}", retention=30, engagement=1.0) for i in range(5)]
        older = [_make_video(f"o{i}", retention=55, engagement=6.0) for i in range(10)]
        insights = {"per_video_stats": recent + older}
        summary = run_trend_analysis(insights)
        assert summary["total_alerts"] > 0
        assert summary["telegram_sent"] is True
        assert "alerts" in summary

    def test_no_data_returns_empty_summary(self):
        summary = run_trend_analysis({"per_video_stats": []})
        assert summary["total_alerts"] == 0
        assert summary["alerts"] == []

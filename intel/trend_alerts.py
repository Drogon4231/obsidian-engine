"""
trend_alerts.py — Proactive content quality trend detection and alerting.

Analyzes per-video performance data from channel_insights.json to detect:
  - Declining retention, engagement, or views across recent videos
  - Hook retention dropping (first 30s audience loss)
  - Metrics falling below channel averages
  - Positive trends worth reinforcing

Sends actionable Telegram alerts so the creator knows what's happening
without waiting for the weekly report.

Called by the analytics agent after insights are computed.
"""

from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
PREFIX = "[Trends]"


# ══════════════════════════════════════════════════════════════════════════════
# Trend Detection — pure functions
# ══════════════════════════════════════════════════════════════════════════════

def detect_trends(insights: dict) -> list[dict]:
    """
    Analyze channel_insights to detect noteworthy trends.
    Returns list of alert dicts: {type, severity, title, detail, metric, values}.
    severity: "warning", "critical", "positive"
    """
    alerts = []
    per_video = insights.get("per_video_stats", [])
    if len(per_video) < 3:
        return alerts

    # Use most recent videos (already ordered by recency from analytics agent)
    recent = per_video[:5]
    older = per_video[5:15]

    # ── Retention trend ──────────────────────────────────────────────────────
    retention_alert = _check_declining_metric(
        recent, older, "avg_retention_pct",
        metric_name="Retention",
        unit="%",
        threshold_pct=10,
    )
    if retention_alert:
        alerts.append(retention_alert)

    # ── Engagement rate trend ────────────────────────────────────────────────
    engagement_alert = _check_declining_metric(
        recent, older, "engagement_rate",
        metric_name="Engagement Rate",
        unit="%",
        threshold_pct=15,
    )
    if engagement_alert:
        alerts.append(engagement_alert)

    # ── Views velocity trend ─────────────────────────────────────────────────
    views_alert = _check_declining_metric(
        recent, older, "views",
        metric_name="Views",
        unit="",
        threshold_pct=20,
    )
    if views_alert:
        alerts.append(views_alert)

    # ── Hook retention (from retention_curves) ───────────────────────────────
    hook_alert = _check_hook_retention(insights)
    if hook_alert:
        alerts.append(hook_alert)

    # ── Subscriber gain trend ────────────────────────────────────────────────
    subs_alert = _check_declining_metric(
        recent, older, "subscribers_gained",
        metric_name="Subscriber Gains",
        unit="",
        threshold_pct=25,
    )
    if subs_alert:
        alerts.append(subs_alert)

    # ── Positive trends (reinforcement) ──────────────────────────────────────
    positive = _check_positive_trends(recent, older)
    alerts.extend(positive)

    # ── Below-average detection ──────────────────────────────────────────────
    below_avg = _check_below_average(recent, per_video)
    alerts.extend(below_avg)

    return alerts


def _check_declining_metric(
    recent: list[dict],
    older: list[dict],
    key: str,
    metric_name: str,
    unit: str,
    threshold_pct: float,
) -> dict | None:
    """Check if a metric is declining across recent videos vs older ones."""
    recent_vals = [v.get(key, 0) for v in recent if v.get(key) is not None]
    older_vals = [v.get(key, 0) for v in older if v.get(key) is not None]

    if len(recent_vals) < 3 or len(older_vals) < 3:
        return None

    recent_avg = sum(recent_vals) / len(recent_vals)
    older_avg = sum(older_vals) / len(older_vals)

    if older_avg == 0:
        return None

    change_pct = ((recent_avg - older_avg) / older_avg) * 100

    if change_pct < -threshold_pct:
        severity = "critical" if change_pct < -threshold_pct * 2 else "warning"
        return {
            "type": "declining_metric",
            "severity": severity,
            "title": f"{metric_name} Declining",
            "detail": (
                f"Last {len(recent_vals)} videos avg: {recent_avg:.1f}{unit} "
                f"vs prior {len(older_vals)} videos: {older_avg:.1f}{unit} "
                f"({change_pct:+.1f}%)"
            ),
            "metric": key,
            "recent_avg": round(recent_avg, 2),
            "older_avg": round(older_avg, 2),
            "change_pct": round(change_pct, 1),
            "recent_values": [round(v, 2) for v in recent_vals],
        }
    return None


def _check_hook_retention(insights: dict) -> dict | None:
    """Check if hook retention (first 30s) is declining."""
    retention_data = insights.get("retention_curves", {})
    if not retention_data:
        return None

    per_video = retention_data.get("per_video", [])
    if not per_video:
        return None

    hook_values = [v.get("hook_retention_30s", 0) for v in per_video if v.get("hook_retention_30s")]
    if len(hook_values) < 4:
        return None

    recent_hooks = hook_values[:3]
    older_hooks = hook_values[3:]

    if not older_hooks:
        return None

    recent_avg = sum(recent_hooks) / len(recent_hooks)
    older_avg = sum(older_hooks) / len(older_hooks)

    if older_avg == 0:
        return None

    change_pct = ((recent_avg - older_avg) / older_avg) * 100

    if change_pct < -8:
        return {
            "type": "hook_retention_drop",
            "severity": "critical" if change_pct < -15 else "warning",
            "title": "Hook Retention Dropping",
            "detail": (
                f"First 30s retention: {recent_avg:.1f}% (last 3) "
                f"vs {older_avg:.1f}% (prior). "
                f"Viewers are leaving earlier — review your opening hooks."
            ),
            "metric": "hook_retention_30s",
            "recent_avg": round(recent_avg, 1),
            "older_avg": round(older_avg, 1),
            "change_pct": round(change_pct, 1),
        }
    return None


def _check_positive_trends(recent: list[dict], older: list[dict]) -> list[dict]:
    """Detect positive trends worth reinforcing."""
    alerts = []

    for key, name, unit, threshold in [
        ("avg_retention_pct", "Retention", "%", 10),
        ("engagement_rate", "Engagement", "%", 15),
        ("views", "Views", "", 20),
    ]:
        recent_vals = [v.get(key, 0) for v in recent if v.get(key) is not None]
        older_vals = [v.get(key, 0) for v in older if v.get(key) is not None]

        if len(recent_vals) < 3 or len(older_vals) < 3:
            continue

        recent_avg = sum(recent_vals) / len(recent_vals)
        older_avg = sum(older_vals) / len(older_vals)

        if older_avg == 0:
            continue

        change_pct = ((recent_avg - older_avg) / older_avg) * 100

        if change_pct > threshold:
            alerts.append({
                "type": "improving_metric",
                "severity": "positive",
                "title": f"{name} Improving",
                "detail": (
                    f"Last {len(recent_vals)} videos avg: {recent_avg:.1f}{unit} "
                    f"vs prior: {older_avg:.1f}{unit} ({change_pct:+.1f}%)"
                ),
                "metric": key,
                "recent_avg": round(recent_avg, 2),
                "older_avg": round(older_avg, 2),
                "change_pct": round(change_pct, 1),
            })

    return alerts


def _check_below_average(recent: list[dict], all_videos: list[dict]) -> list[dict]:
    """Check if recent videos are consistently below channel average."""
    alerts = []

    if len(all_videos) < 5 or len(recent) < 3:
        return alerts

    for key, name, unit in [
        ("avg_retention_pct", "Retention", "%"),
        ("engagement_rate", "Engagement Rate", "%"),
    ]:
        all_vals = [v.get(key, 0) for v in all_videos if v.get(key) is not None]
        if not all_vals:
            continue

        channel_avg = sum(all_vals) / len(all_vals)
        recent_vals = [v.get(key, 0) for v in recent if v.get(key) is not None]

        if not recent_vals:
            continue

        # Check if ALL recent videos are below average
        below_count = sum(1 for v in recent_vals if v < channel_avg)

        if below_count == len(recent_vals) and len(recent_vals) >= 3:
            recent_titles = [v.get("title", "?")[:40] for v in recent[:3]]
            alerts.append({
                "type": "below_average_streak",
                "severity": "warning",
                "title": f"{name}: {below_count} Videos Below Average",
                "detail": (
                    f"Channel avg: {channel_avg:.1f}{unit}. "
                    f"Last {below_count} videos all below. "
                    f"Videos: {', '.join(recent_titles)}"
                ),
                "metric": key,
                "channel_avg": round(channel_avg, 2),
                "recent_values": [round(v, 2) for v in recent_vals],
            })

    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# Telegram Alerting
# ══════════════════════════════════════════════════════════════════════════════

def send_trend_alerts(alerts: list[dict]) -> int:
    """
    Send trend alerts to Telegram. Returns count of alerts sent.
    Groups alerts into a single message to avoid spam.
    """
    if not alerts:
        return 0

    try:
        from server.notify import _tg
    except Exception:
        print(f"{PREFIX} Cannot import Telegram notifier")
        return 0

    severity_emoji = {
        "critical": "🔴",
        "warning": "🟡",
        "positive": "🟢",
    }

    lines = ["*Content Quality Trends*", ""]

    # Sort: critical first, then warning, then positive
    priority = {"critical": 0, "warning": 1, "positive": 2}
    sorted_alerts = sorted(alerts, key=lambda a: priority.get(a["severity"], 1))

    for alert in sorted_alerts:
        emoji = severity_emoji.get(alert["severity"], "⚪")
        lines.append(f"{emoji} *{alert['title']}*")
        lines.append(f"  {alert['detail']}")
        lines.append("")

    if any(a["severity"] in ("critical", "warning") for a in alerts):
        lines.append("_Review channel\\_insights.json or /optimizer status for details._")

    message = "\n".join(lines)
    ok = _tg(message)
    if ok:
        print(f"{PREFIX} Sent {len(alerts)} trend alerts to Telegram")
    return len(alerts) if ok else 0


# ══════════════════════════════════════════════════════════════════════════════
# Analytics Agent Integration
# ══════════════════════════════════════════════════════════════════════════════

def run_trend_analysis(insights: dict) -> dict:
    """
    Full trend analysis pipeline: detect → alert → return summary.
    Called by analytics agent after insights are built.
    """
    alerts = detect_trends(insights)

    if alerts:
        sent = send_trend_alerts(alerts)
        # Save alerts to insights for dashboard consumption
        summary = {
            "total_alerts": len(alerts),
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
            "warnings": sum(1 for a in alerts if a["severity"] == "warning"),
            "positive": sum(1 for a in alerts if a["severity"] == "positive"),
            "alerts": alerts,
            "telegram_sent": sent > 0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        summary = {
            "total_alerts": 0,
            "critical": 0,
            "warnings": 0,
            "positive": 0,
            "alerts": [],
            "telegram_sent": False,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    return summary

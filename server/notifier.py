"""
notifier.py — Discord webhook notifications for The Obsidian Archive pipeline.
"""

import requests
import os
from datetime import datetime, timezone

try:
    from core.pipeline_config import DISCORD_WEBHOOK_URL
except Exception:
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Color constants
PURPLE = 0x8B5CF6
GREEN  = 0x10B981
RED    = 0xEF4444
CYAN   = 0x06B6D4


def notify(title: str, message: str, color: int = PURPLE, fields: list = None):
    """Send a Discord embed via webhook. Never crashes the caller."""
    try:
        if not DISCORD_WEBHOOK_URL:
            print(f"[notifier] (no webhook) {title}: {message}")
            return

        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": color,
                "fields": fields or [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        }

        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code >= 400:
            print(f"[notifier] Discord webhook returned {resp.status_code}")
    except Exception as e:
        print(f"[notifier] Warning: failed to send notification: {e}")


def notify_pipeline_start(topic: str):
    """Purple embed when a pipeline run begins."""
    notify(
        title="Pipeline Started",
        message=f"Topic: **{topic}**",
        color=PURPLE,
    )


def notify_pipeline_complete(topic: str, elapsed_minutes: float, video_url: str = ""):
    """Green embed when a pipeline run finishes successfully."""
    fields = [
        {"name": "Elapsed", "value": f"{elapsed_minutes:.1f} min", "inline": True},
    ]
    if video_url:
        fields.append({"name": "Video", "value": video_url, "inline": False})

    notify(
        title="Pipeline Complete",
        message=f"Topic: **{topic}**",
        color=GREEN,
        fields=fields,
    )


def notify_pipeline_failed(topic: str, error: str, stage: str = ""):
    """Red embed when a pipeline run fails."""
    fields = [
        {"name": "Error", "value": error[:1024], "inline": False},
    ]
    if stage:
        fields.append({"name": "Stage", "value": stage, "inline": True})

    notify(
        title="Pipeline Failed",
        message=f"Topic: **{topic}**",
        color=RED,
        fields=fields,
    )


def notify_trend_alert(topic: str, score: float, sources: list):
    """Cyan embed when a trending topic is detected."""
    fields = [
        {"name": "Score", "value": f"{score:.2f}", "inline": True},
        {"name": "Sources", "value": ", ".join(sources or []), "inline": True},
    ]

    notify(
        title="Trend Alert",
        message=f"Trending topic: **{topic}**",
        color=CYAN,
        fields=fields,
    )

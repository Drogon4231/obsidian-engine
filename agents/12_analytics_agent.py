"""
Agent 12 — Analytics Agent
YouTube Analytics feedback loop: pulls data, writes to Supabase, generates channel_insights.json.
Run manually or via scheduler daily at 06:00.
"""
from __future__ import annotations

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

LESSONS_FILE  = Path(__file__).resolve().parent.parent / "lessons_learned.json"
INSIGHTS_FILE = Path(__file__).resolve().parent.parent / "channel_insights.json"


from core.utils import atomic_write_json as _atomic_write_json, persist_json_to_supabase


# ── YouTube Analytics client ──────────────────────────────────────────────────

def get_youtube_analytics_client():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    TOKEN_FILE = Path(__file__).resolve().parent.parent / "youtube_token.json"

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    elif os.getenv("YOUTUBE_TOKEN_JSON"):
        TOKEN_FILE.write_text(os.getenv("YOUTUBE_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            raise Exception(
                "No valid YouTube credentials. Run 11_youtube_uploader.py first to authenticate, "
                "or set YOUTUBE_TOKEN_JSON env var on Railway."
            )

    return build("youtubeAnalytics", "v2", credentials=creds)


def fetch_video_analytics(youtube_analytics, video_id: str) -> dict:
    """Fetch views, watch time, retention, subscribers, shares for one video."""
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        # Note: "impressions" is NOT a valid metric with dimensions=video.
        # Query without dimensions — filter by single video returns one row of metrics.
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewPercentage,subscribersGained,shares",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if rows:
            row = rows[0]
            # No dimensions → row is pure metrics: views, watchTime, retention, subs, shares
            views = int(row[0]) if len(row) > 0 else 0
            shares = int(row[4]) if len(row) > 4 else 0

            # Fetch likes & comments from Data API v3
            engagement = fetch_engagement_metrics(video_id)
            likes = engagement.get("likes", 0)
            comments = engagement.get("comments", 0)
            total_engagement = likes + comments + shares
            engagement_rate = round(total_engagement / max(views, 1) * 100, 3)
            like_ratio = round(likes / max(views, 1) * 100, 3)

            return {
                "views":               views,
                "watch_time_minutes":  float(row[1]) if len(row) > 1 else 0.0,
                "avg_view_percentage": float(row[2]) if len(row) > 2 else 0.0,
                "subscribers_gained":  int(float(row[3])) if len(row) > 3 else 0,
                "ctr_pct":             0.0,
                "impressions":         0,
                "likes":               likes,
                "comments":            comments,
                "shares":              shares,
                "engagement_rate":     engagement_rate,
                "like_ratio":          like_ratio,
            }
        else:
            print(f"  [Analytics] No data rows for {video_id} (video may be < 48h old)")
    except Exception as e:
        print(f"  [Analytics] Could not fetch data for {video_id}: {e}")
    return {"views": 0, "watch_time_minutes": 0.0, "avg_view_percentage": 0.0,
            "subscribers_gained": 0, "ctr_pct": 0.0, "impressions": 0,
            "likes": 0, "comments": 0, "shares": 0, "engagement_rate": 0.0, "like_ratio": 0.0}


# ── YouTube Data API v3 client (for likes, comments, etc.) ───────────────────

def _get_youtube_data_client():
    """Get a YouTube Data API v3 client using the same auth as analytics."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    TOKEN_FILE = Path(__file__).resolve().parent.parent / "youtube_token.json"
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    elif os.getenv("YOUTUBE_TOKEN_JSON"):
        TOKEN_FILE.write_text(os.getenv("YOUTUBE_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            return None
    return build("youtube", "v3", credentials=creds)


# ── Traffic Sources ──────────────────────────────────────────────────────────

def fetch_traffic_sources(youtube_analytics, video_id: str) -> dict:
    """Fetch traffic source breakdown for a video."""
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    default = {
        "browse": {"views": 0, "watch_min": 0},
        "search": {"views": 0, "watch_min": 0},
        "suggested": {"views": 0, "watch_min": 0},
        "external": {"views": 0, "watch_min": 0},
        "other": {"views": 0, "watch_min": 0},
        "primary_traffic_source": "unknown",
        "search_dependency_pct": 0.0,
    }
    try:
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="insightTrafficSourceType",
            metrics="views,estimatedMinutesWatched",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if not rows:
            return default

        SOURCE_MAP = {
            "SUBSCRIBER": "browse",
            "YT_CHANNEL": "browse",
            "NOTIFICATION": "browse",
            "BROWSE_FEATURES": "browse",
            "YT_SEARCH": "search",
            "SUGGESTED": "suggested",
            "EXT_URL": "external",
            "NO_LINK_EMBEDDED": "external",
            "PLAYLIST": "browse",
        }

        buckets = {k: {"views": 0, "watch_min": 0.0} for k in ["browse", "search", "suggested", "external", "other"]}
        total_views = 0
        for row in rows:
            source_type = row[0]
            views = int(row[1])
            watch_min = float(row[2])
            total_views += views
            bucket = SOURCE_MAP.get(source_type, "other")
            buckets[bucket]["views"] += views
            buckets[bucket]["watch_min"] += round(watch_min, 1)

        # Determine primary source
        primary = max(buckets, key=lambda k: buckets[k]["views"])
        search_pct = round(buckets["search"]["views"] / max(total_views, 1) * 100, 1)

        result = dict(buckets)
        result["primary_traffic_source"] = primary
        result["search_dependency_pct"] = search_pct
        return result
    except Exception as e:
        print(f"  [Analytics] Traffic sources failed for {video_id}: {e}")
        return default


# ── First 48h Performance ────────────────────────────────────────────────────

def fetch_first_48h_performance(youtube_analytics, video_id: str, upload_date: str) -> dict:
    """Fetch views, watch time, subs in first 48h after upload."""
    default = {
        "first_48h_views": 0,
        "first_48h_watch_min": 0.0,
        "first_48h_subs": 0,
        "first_48h_velocity": 0.0,
    }
    try:
        # Parse upload date
        if "T" in upload_date:
            upload_dt = datetime.fromisoformat(upload_date.replace("Z", "+00:00"))
        else:
            upload_dt = datetime.strptime(upload_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        start_date = upload_dt.strftime("%Y-%m-%d")
        end_dt = upload_dt + timedelta(days=2)
        end_date = end_dt.strftime("%Y-%m-%d")

        # Don't query future dates
        now = datetime.now(timezone.utc)
        if upload_dt > now:
            return default
        if end_dt > now:
            end_date = now.strftime("%Y-%m-%d")

        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,subscribersGained",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if rows:
            row = rows[0]
            views = int(row[0]) if len(row) > 0 else 0
            watch_min = float(row[1]) if len(row) > 1 else 0.0
            subs = int(float(row[2])) if len(row) > 2 else 0
            velocity = round(views / 48.0, 2)
            return {
                "first_48h_views": views,
                "first_48h_watch_min": round(watch_min, 1),
                "first_48h_subs": subs,
                "first_48h_velocity": velocity,
            }
        return default
    except Exception as e:
        print(f"  [Analytics] First 48h fetch failed for {video_id}: {e}")
        return default


# ── Audience Retention Curve ─────────────────────────────────────────────────

def fetch_retention_curve(youtube_analytics, video_id: str, duration_seconds: float = 0) -> dict:
    """Fetch audience retention curve (0-100% of video duration)."""
    default = {
        "retention_curve": [],
        "hook_retention_30s": 0.0,
        "midpoint_retention": 0.0,
        "end_retention": 0.0,
        "biggest_drop_timestamp": 0,
        "re_hook_points": [],
    }
    try:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if not rows or len(rows) < 5:
            return default

        # Build retention array: list of (pct_position, retention_ratio)
        curve = []
        for row in rows:
            _pct = float(row[0])  # 0.0 to 1.0 (position, not used directly)  # noqa: F841
            ratio = float(row[1])
            curve.append(ratio)

        # Normalize: YouTube returns audienceWatchRatio relative to views
        # curve[i] represents retention at i% of video
        # Compute actual 30-second index from video duration when available
        if duration_seconds > 0 and len(curve) > 0:
            hook_30s_idx = min(int(30 / duration_seconds * len(curve)), len(curve) - 1)
        else:
            hook_30s_idx = min(5, len(curve) - 1)  # fallback: ~5% for ~10-min video
        mid_idx = len(curve) // 2
        end_idx = max(0, len(curve) - 3)

        hook_retention = round(curve[hook_30s_idx] * 100, 1) if len(curve) > hook_30s_idx else 0.0
        midpoint = round(curve[mid_idx] * 100, 1) if len(curve) > mid_idx else 0.0
        end_ret = round(curve[end_idx] * 100, 1) if len(curve) > end_idx else 0.0

        # Find biggest drop
        biggest_drop = 0
        biggest_drop_idx = 0
        for i in range(1, len(curve)):
            drop = curve[i - 1] - curve[i]
            if drop > biggest_drop:
                biggest_drop = drop
                biggest_drop_idx = i

        # Find re-hook points (where retention increases after dropping)
        re_hooks = []
        for i in range(2, len(curve)):
            if curve[i] > curve[i - 1] and curve[i - 1] < curve[i - 2]:
                re_hooks.append(i)

        return {
            "retention_curve": [round(v * 100, 1) for v in curve],
            "hook_retention_30s": hook_retention,
            "midpoint_retention": midpoint,
            "end_retention": end_ret,
            "biggest_drop_timestamp": biggest_drop_idx,
            "re_hook_points": re_hooks[:5],
        }
    except Exception as e:
        print(f"  [Analytics] Retention curve failed for {video_id}: {e}")
        return default


# ── Search Terms ─────────────────────────────────────────────────────────────

def fetch_search_terms(youtube_analytics, video_id: str) -> list:
    """Fetch top search terms that brought viewers to this video."""
    try:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="insightTrafficSourceDetail",
            metrics="views",
            filters=f"video=={video_id};insightTrafficSourceType==YT_SEARCH",
            maxResults=20,
            sort="-views",
        ).execute()
        rows = response.get("rows", [])
        return [{"term": row[0], "views": int(row[1])} for row in rows]
    except Exception as e:
        print(f"  [Analytics] Search terms failed for {video_id}: {e}")
        return []


# ── Engagement Metrics (Data API v3) ─────────────────────────────────────────

def fetch_engagement_metrics(video_id: str) -> dict:
    """Fetch likes, comments, shares from YouTube Data API v3."""
    default = {"likes": 0, "comments": 0, "engagement_rate": 0.0, "like_ratio": 0.0}
    try:
        yt = _get_youtube_data_client()
        if not yt:
            return default
        response = yt.videos().list(
            part="statistics",
            id=video_id,
        ).execute()
        items = response.get("items", [])
        if not items:
            return default
        stats = items[0].get("statistics", {})
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        views = int(stats.get("viewCount", 0))
        return {
            "likes": likes,
            "comments": comments,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 3),
            "like_ratio": round(likes / max(views, 1) * 100, 3),
        }
    except Exception as e:
        print(f"  [Analytics] Engagement metrics failed for {video_id}: {e}")
        return default


def fetch_shares(youtube_analytics, video_id: str) -> int:
    """Fetch share count from YouTube Analytics API v2."""
    try:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            metrics="shares",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if rows and len(rows[0]) > 0:
            return int(rows[0][0])
        return 0
    except Exception as e:
        print(f"  [Analytics] Shares fetch failed for {video_id}: {e}")
        return 0


# ── End Screen & Card Performance ────────────────────────────────────────────

def fetch_endscreen_performance(youtube_analytics, video_id: str) -> dict:
    """Fetch end screen and card click-through rates."""
    default = {"endscreen_ctr": 0.0, "card_ctr": 0.0}
    try:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            metrics="cardClickRate,cardTeaserClickRate",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        card_ctr = 0.0
        if rows:
            card_ctr = round(float(rows[0][0]) * 100, 2) if len(rows[0]) > 0 else 0.0

        # Try endscreen metrics
        endscreen_ctr = 0.0
        try:
            es_response = youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate="2020-01-01",
                endDate=end_date,
                metrics="annotationClickThroughRate",
                filters=f"video=={video_id}",
            ).execute()
            es_rows = es_response.get("rows", [])
            if es_rows and len(es_rows[0]) > 0:
                endscreen_ctr = round(float(es_rows[0][0]) * 100, 2)
        except Exception:
            pass  # annotationClickThroughRate may not be available

        return {"endscreen_ctr": endscreen_ctr, "card_ctr": card_ctr}
    except Exception as e:
        print(f"  [Analytics] Endscreen/card metrics failed for {video_id}: {e}")
        return default


# ── Audience Demographics (channel-level) ────────────────────────────────────

def fetch_demographics(youtube_analytics) -> dict:
    """Fetch channel-level audience demographics: age, gender, country."""
    default = {
        "top_countries": [],
        "age_distribution": {},
        "gender_split": {},
    }
    try:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Country breakdown
        country_resp = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="country",
            metrics="views",
            sort="-views",
            maxResults=10,
        ).execute()
        country_rows = country_resp.get("rows", [])
        total_country_views = sum(int(r[1]) for r in country_rows) if country_rows else 1
        top_countries = [
            {"country": row[0], "views": int(row[1]),
             "pct": round(int(row[1]) / max(total_country_views, 1) * 100, 1)}
            for row in country_rows[:3]
        ]

        # Age group breakdown
        age_resp = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="ageGroup",
            metrics="viewerPercentage",
        ).execute()
        age_rows = age_resp.get("rows", [])
        age_distribution = {row[0]: round(float(row[1]), 1) for row in age_rows}

        # Gender breakdown
        gender_resp = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=end_date,
            dimensions="gender",
            metrics="viewerPercentage",
        ).execute()
        gender_rows = gender_resp.get("rows", [])
        gender_split = {row[0]: round(float(row[1]), 1) for row in gender_rows}

        return {
            "top_countries": top_countries,
            "age_distribution": age_distribution,
            "gender_split": gender_split,
        }
    except Exception as e:
        print(f"  [Analytics] Demographics fetch failed: {e}")
        return default


# ── Aggregate computation helpers ────────────────────────────────────────────

def _compute_channel_traffic_mix(all_traffic: list) -> dict:
    """Aggregate traffic source breakdown across all videos."""
    totals = {k: {"views": 0, "watch_min": 0.0} for k in ["browse", "search", "suggested", "external", "other"]}
    for t in all_traffic:
        for source in totals:
            totals[source]["views"] += t.get(source, {}).get("views", 0)
            totals[source]["watch_min"] += t.get(source, {}).get("watch_min", 0.0)
    grand_total = sum(totals[s]["views"] for s in totals) or 1
    mix = {}
    for source, data in totals.items():
        mix[source] = {
            "views": data["views"],
            "watch_min": round(data["watch_min"], 1),
            "pct": round(data["views"] / grand_total * 100, 1),
        }
    mix["primary_source"] = max(totals, key=lambda k: totals[k]["views"])
    return mix


def _compute_first_48h_benchmarks(all_48h: list) -> dict:
    """Compute average first-48h velocity and identify best/worst performers."""
    if not all_48h:
        return {}
    velocities = [d["first_48h_velocity"] for d in all_48h if d.get("first_48h_velocity", 0) > 0]
    if not velocities:
        return {"avg_velocity": 0, "best_performer": None, "worst_performer": None}
    avg_vel = round(sum(velocities) / len(velocities), 2)
    sorted_48h = sorted(all_48h, key=lambda x: x.get("first_48h_velocity", 0), reverse=True)
    best = sorted_48h[0] if sorted_48h else None
    worst = sorted_48h[-1] if sorted_48h else None
    return {
        "avg_velocity": avg_vel,
        "sample_count": len(velocities),
        "best_performer": {
            "youtube_id": best.get("youtube_id", ""),
            "title": best.get("title", ""),
            "velocity": best.get("first_48h_velocity", 0),
        } if best else None,
        "worst_performer": {
            "youtube_id": worst.get("youtube_id", ""),
            "title": worst.get("title", ""),
            "velocity": worst.get("first_48h_velocity", 0),
        } if worst else None,
    }


def _compute_retention_aggregate(all_retention: list) -> dict:
    """Compute average retention curve across all videos."""
    curves = [r["retention_curve"] for r in all_retention if r.get("retention_curve")]
    if not curves:
        return {}
    max_len = max(len(c) for c in curves)
    avg_curve = []
    for i in range(max_len):
        vals = [c[i] for c in curves if i < len(c)]
        avg_curve.append(round(sum(vals) / len(vals), 1) if vals else 0.0)

    hooks = [r["hook_retention_30s"] for r in all_retention if r.get("hook_retention_30s", 0) > 0]
    mids = [r["midpoint_retention"] for r in all_retention if r.get("midpoint_retention", 0) > 0]
    ends = [r["end_retention"] for r in all_retention if r.get("end_retention", 0) > 0]

    return {
        "avg_curve": avg_curve,
        "avg_hook_retention_30s": round(sum(hooks) / len(hooks), 1) if hooks else 0.0,
        "avg_midpoint_retention": round(sum(mids) / len(mids), 1) if mids else 0.0,
        "avg_end_retention": round(sum(ends) / len(ends), 1) if ends else 0.0,
        "sample_count": len(curves),
    }


def _compute_top_search_terms(all_search: list, limit: int = 30) -> list:
    """Aggregate search terms across all videos, ranked by total views."""
    term_views: dict = {}
    for terms_list in all_search:
        for entry in terms_list:
            term = entry.get("term", "").lower().strip()
            if term:
                term_views[term] = term_views.get(term, 0) + entry.get("views", 0)
    sorted_terms = sorted(term_views.items(), key=lambda x: x[1], reverse=True)
    return [{"term": t, "views": v} for t, v in sorted_terms[:limit]]


def _compute_avg_engagement(all_engagement: list) -> dict:
    """Compute channel-wide average engagement metrics."""
    if not all_engagement:
        return {}
    rates = [e["engagement_rate"] for e in all_engagement if e.get("engagement_rate", 0) > 0]
    like_ratios = [e["like_ratio"] for e in all_engagement if e.get("like_ratio", 0) > 0]
    total_likes = sum(e.get("likes", 0) for e in all_engagement)
    total_comments = sum(e.get("comments", 0) for e in all_engagement)
    total_shares = sum(e.get("shares", 0) for e in all_engagement)
    return {
        "avg_engagement_rate": round(sum(rates) / len(rates), 3) if rates else 0.0,
        "avg_like_ratio": round(sum(like_ratios) / len(like_ratios), 3) if like_ratios else 0.0,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "sample_count": len(all_engagement),
    }


def _compute_endscreen_aggregate(all_endscreen: list) -> dict:
    """Compute aggregate endscreen/card effectiveness."""
    card_ctrs = [e["card_ctr"] for e in all_endscreen if e.get("card_ctr", 0) > 0]
    es_ctrs = [e["endscreen_ctr"] for e in all_endscreen if e.get("endscreen_ctr", 0) > 0]
    return {
        "avg_card_ctr": round(sum(card_ctrs) / len(card_ctrs), 2) if card_ctrs else 0.0,
        "avg_endscreen_ctr": round(sum(es_ctrs) / len(es_ctrs), 2) if es_ctrs else 0.0,
        "videos_with_cards": len(card_ctrs),
        "videos_with_endscreens": len(es_ctrs),
    }


# ── Era classification ────────────────────────────────────────────────────────

from intel.era_classifier import ERA_KEYWORDS, classify_era


# ── Statistical summary ───────────────────────────────────────────────────────

def compute_stats_summary(rows: list) -> dict:
    """Pure-Python statistical summary — no Claude, no API calls."""
    if not rows:
        return {}

    n = len(rows)
    views_list     = [r["views"] for r in rows]
    retention_list = [r["avg_view_percentage"] for r in rows if r["avg_view_percentage"] > 0]
    ctr_list       = [r["ctr_pct"] for r in rows if r["ctr_pct"] > 0]
    subs_list      = [r["subscribers_gained"] for r in rows]

    avg_views     = sum(views_list) / n
    avg_retention = sum(retention_list) / len(retention_list) if retention_list else 0.0
    avg_ctr       = sum(ctr_list) / len(ctr_list) if ctr_list else 0.0
    avg_subs      = sum(subs_list) / n

    # Top quartile threshold
    sorted_views = sorted(views_list, reverse=True)
    top_q_idx    = max(1, n // 4)
    top_q_threshold = sorted_views[top_q_idx - 1] if sorted_views else 0

    # Era breakdown (avg views, avg ctr, avg retention, count)
    era_buckets: dict = {}
    for r in rows:
        era = classify_era(r.get("topic", ""))
        if era not in era_buckets:
            era_buckets[era] = {"views": [], "ctr": [], "retention": [], "subs": []}
        era_buckets[era]["views"].append(r["views"])
        era_buckets[era]["subs"].append(r["subscribers_gained"])
        if r["ctr_pct"] > 0:
            era_buckets[era]["ctr"].append(r["ctr_pct"])
        if r["avg_view_percentage"] > 0:
            era_buckets[era]["retention"].append(r["avg_view_percentage"])

    era_performance = {}
    for era, data in era_buckets.items():
        vl = data["views"]
        cl = data["ctr"]
        rl = data["retention"]
        sl = data["subs"]
        total_views = sum(vl)
        total_subs = sum(sl)
        era_performance[era] = {
            "avg_views":     round(sum(vl) / len(vl), 0) if vl else 0,
            "avg_ctr":       round(sum(cl) / len(cl), 2) if cl else 0,
            "avg_retention": round(sum(rl) / len(rl), 1) if rl else 0,
            "avg_subs":      round(sum(sl) / len(sl), 1) if sl else 0,
            "sub_conversion_rate": round(total_subs / total_views * 100, 3) if total_views > 0 else 0,
            "video_count":   len(vl),
        }

    # Retention by video length band
    length_bands = {
        "under_8min":  {"retention": [], "views": [], "threshold": (0, 8)},
        "8_to_12min":  {"retention": [], "views": [], "threshold": (8, 12)},
        "12_to_16min": {"retention": [], "views": [], "threshold": (12, 16)},
        "over_16min":  {"retention": [], "views": [], "threshold": (16, 999)},
    }
    for r in rows:
        dur_min = (r.get("duration_seconds") or 0) / 60.0
        for band, data in length_bands.items():
            lo, hi = data["threshold"]
            if lo <= dur_min < hi:
                if r["avg_view_percentage"] > 0:
                    data["retention"].append(r["avg_view_percentage"])
                data["views"].append(r["views"])
                break

    retention_by_length = {}
    for band, data in length_bands.items():
        rl = data["retention"]
        vl = data["views"]
        retention_by_length[band] = {
            "avg_retention": round(sum(rl) / len(rl), 1) if rl else None,
            "avg_views":     round(sum(vl) / len(vl), 0) if vl else None,
            "sample_count":  len(vl),
        }

    # Sort by views for top/bottom lists
    sorted_rows = sorted(rows, key=lambda x: x["views"], reverse=True)
    sorted_by_ctr = sorted([r for r in rows if r["ctr_pct"] > 0], key=lambda x: x["ctr_pct"], reverse=True)

    def row_summary(r):
        dur_min = round((r.get("duration_seconds") or 0) / 60.0, 1)
        title = r.get("title") or r.get("topic", "")
        words = title.split()
        return {
            "title":               title,
            "youtube_id":          r.get("youtube_id", ""),
            "views":               r["views"],
            "ctr_pct":             round(r["ctr_pct"], 2),
            "avg_retention_pct":   round(r["avg_view_percentage"], 1),
            "subscribers_gained":  r["subscribers_gained"],
            "era":                 classify_era(r.get("topic", "")),
            "video_length_minutes": dur_min,
            "title_word_count":    len(words),
        }

    return {
        "n_videos":              n,
        "n_with_ctr":            len(ctr_list),
        "n_with_retention":      len(retention_list),
        "avg_views":             round(avg_views, 1),
        "avg_ctr_pct":           round(avg_ctr, 2),
        "avg_retention_pct":     round(avg_retention, 1),
        "avg_subscribers_gained": round(avg_subs, 1),
        "top_quartile_threshold": top_q_threshold,
        "era_performance":        era_performance,
        "retention_by_length":    retention_by_length,
        "top_5_by_ctr":    [row_summary(r) for r in sorted_by_ctr[:5]],
        "bottom_5_by_ctr": [row_summary(r) for r in sorted_by_ctr[-5:]] if len(sorted_by_ctr) > 5 else [],
        "top_5_by_views":  [row_summary(r) for r in sorted_rows[:5]],
        "bottom_5_by_views": [row_summary(r) for r in sorted_rows[-5:]] if len(sorted_rows) > 5 else [],
    }


# ── Shorts intelligence ──────────────────────────────────────────────────────

def compute_shorts_intelligence(shorts_rows: list, long_rows: list) -> dict:
    """Compute actionable shorts analytics — era performance, top hooks, conversion."""
    if not shorts_rows:
        return {}

    # Per-era shorts performance
    era_buckets: dict = {}
    for r in shorts_rows:
        era = classify_era(r.get("topic", ""))
        if era not in era_buckets:
            era_buckets[era] = {"views": [], "subs": [], "titles": []}
        era_buckets[era]["views"].append(r["views"])
        era_buckets[era]["subs"].append(r["subscribers_gained"])
        era_buckets[era]["titles"].append(r.get("title", ""))

    era_performance = {}
    for era, data in era_buckets.items():
        v, s = data["views"], data["subs"]
        era_performance[era] = {
            "avg_views": round(sum(v) / len(v), 0) if v else 0,
            "total_subs": sum(s),
            "avg_subs_per_short": round(sum(s) / len(s), 1) if s else 0,
            "short_count": len(v),
            "sub_conversion_rate": round(sum(s) / max(sum(v), 1) * 100, 3),
        }

    # Top hooks (first ~10 words of best-performing short titles)
    sorted_by_views = sorted(shorts_rows, key=lambda x: x["views"], reverse=True)
    top_hooks = [
        {"hook": " ".join(r.get("title", "").split()[:10]),
         "views": r["views"], "subs": r["subscribers_gained"],
         "era": classify_era(r.get("topic", ""))}
        for r in sorted_by_views[:5]
    ]

    all_views = [r["views"] for r in shorts_rows]
    all_subs = [r["subscribers_gained"] for r in shorts_rows]
    return {
        "total_shorts": len(shorts_rows),
        "total_views": sum(all_views),
        "avg_views_per_short": round(sum(all_views) / len(all_views), 1),
        "total_subs_from_shorts": sum(all_subs),
        "avg_subs_per_short": round(sum(all_subs) / len(all_subs), 1),
        "sub_conversion_rate_pct": round(sum(all_subs) / max(sum(all_views), 1) * 100, 3),
        "era_performance": era_performance,
        "top_hooks": top_hooks,
    }


def compute_music_performance_correlation(videos: list, analytics_rows: list) -> dict:
    """Correlate music attributes with video performance.

    Reads music_mood, music_source, music_adapted, music_stems_used, music_bpm
    from Supabase videos table. Correlates against retention and views.
    """
    if not videos or not analytics_rows:
        return {}

    analytics_by_id = {}
    for row in analytics_rows:
        vid = row.get("supabase_video_id") or row.get("video_id", "")
        if vid:
            analytics_by_id[str(vid)] = row

    paired = []
    for v in videos:
        vid = str(v.get("id", ""))
        if vid not in analytics_by_id:
            continue
        mood = v.get("music_mood")
        if not mood:
            continue
        a = analytics_by_id[vid]
        paired.append({
            "mood": mood,
            "source": v.get("music_source", "unknown"),
            "adapted": v.get("music_adapted", False),
            "stems_used": v.get("music_stems_used", False),
            "bpm": v.get("music_bpm", 0),
            "views": a.get("views", 0),
            "retention": a.get("avg_view_percentage", 0),
        })

    if len(paired) < 3:
        return {"sample_size": len(paired), "note": "Insufficient data"}

    # Mood performance
    mood_perf = {}
    for p in paired:
        m = p["mood"]
        if m not in mood_perf:
            mood_perf[m] = {"views": [], "retention": [], "count": 0}
        mood_perf[m]["views"].append(p["views"])
        mood_perf[m]["retention"].append(p["retention"])
        mood_perf[m]["count"] += 1
    mood_performance = {
        m: {
            "avg_views": round(sum(d["views"]) / len(d["views"])),
            "avg_retention": round(sum(d["retention"]) / len(d["retention"]), 1),
            "video_count": d["count"],
        }
        for m, d in mood_perf.items() if d["count"] >= 1
    }

    # Source distribution
    source_dist = {}
    for p in paired:
        s = p["source"]
        source_dist[s] = source_dist.get(s, 0) + 1

    # Adaptation impact
    adapted = [p for p in paired if p["adapted"]]
    not_adapted = [p for p in paired if not p["adapted"]]
    adaptation_impact = {}
    if adapted and not_adapted:
        adaptation_impact = {
            "adapted_avg_retention": round(sum(p["retention"] for p in adapted) / len(adapted), 1),
            "looped_avg_retention": round(sum(p["retention"] for p in not_adapted) / len(not_adapted), 1),
            "adapted_count": len(adapted),
            "looped_count": len(not_adapted),
        }

    # Stems impact
    with_stems = [p for p in paired if p["stems_used"]]
    without_stems = [p for p in paired if not p["stems_used"]]
    stems_impact = {}
    if with_stems and without_stems:
        stems_impact = {
            "stems_avg_retention": round(sum(p["retention"] for p in with_stems) / len(with_stems), 1),
            "no_stems_avg_retention": round(sum(p["retention"] for p in without_stems) / len(without_stems), 1),
            "stems_count": len(with_stems),
            "no_stems_count": len(without_stems),
        }

    # BPM performance buckets
    bpm_buckets = {"60-80": [], "80-100": [], "100-120": [], "120+": []}
    for p in paired:
        bpm = p.get("bpm", 0) or 0
        if bpm < 80:
            bpm_buckets["60-80"].append(p)
        elif bpm < 100:
            bpm_buckets["80-100"].append(p)
        elif bpm < 120:
            bpm_buckets["100-120"].append(p)
        else:
            bpm_buckets["120+"].append(p)
    bpm_performance = {
        k: {
            "avg_retention": round(sum(p["retention"] for p in v) / len(v), 1),
            "count": len(v),
        }
        for k, v in bpm_buckets.items() if v
    }

    # Build recommendations
    recommendations = []
    if mood_performance:
        best_mood = max(mood_performance, key=lambda m: mood_performance[m]["avg_retention"])
        recommendations.append(
            f"Best mood: {best_mood} ({mood_performance[best_mood]['avg_retention']}% avg retention)"
        )
    if adaptation_impact:
        lift = adaptation_impact.get("adapted_avg_retention", 0) - adaptation_impact.get("looped_avg_retention", 0)
        if lift > 0:
            recommendations.append(f"Adapted tracks: +{lift:.1f}% retention vs looped")
    if bpm_performance:
        best_bpm = max(bpm_performance, key=lambda k: bpm_performance[k]["avg_retention"])
        recommendations.append(f"Best BPM range: {best_bpm}")

    return {
        "sample_size": len(paired),
        "mood_performance": mood_performance,
        "source_distribution": source_dist,
        "adaptation_impact": adaptation_impact,
        "stems_impact": stems_impact,
        "bpm_performance": bpm_performance,
        "recommendations": recommendations,
    }


def compute_shorts_long_correlation(shorts_rows: list, long_rows: list,
                                     all_videos: list) -> dict:
    """
    Compute whether posting a short boosts its parent long-form video's views.
    Matching: shorts and long-form are linked by the same topic string.
    """
    if not shorts_rows or not long_rows:
        return {}

    # Build topic lookup from shorts analytics
    short_topics = {}
    for s in shorts_rows:
        topic = s.get("topic", "").strip().lower()
        if topic:
            short_topics[topic] = s

    # Classify long-form: with_short vs without_short
    with_short, without_short = [], []
    for lr in long_rows:
        topic = lr.get("topic", "").strip().lower()
        if topic in short_topics:
            with_short.append(lr)
        else:
            without_short.append(lr)

    if not with_short:
        return {"note": "No topic-matched short/long pairs found yet."}

    avg_views_with = sum(r["views"] for r in with_short) / len(with_short)
    avg_views_without = sum(r["views"] for r in without_short) / len(without_short) if without_short else 0
    avg_subs_with = sum(r["subscribers_gained"] for r in with_short) / len(with_short)
    avg_subs_without = sum(r["subscribers_gained"] for r in without_short) / len(without_short) if without_short else 0

    # Per-era correlation
    era_correlation = {}
    for lr in with_short:
        era = classify_era(lr.get("topic", ""))
        topic = lr.get("topic", "").strip().lower()
        short_data = short_topics.get(topic, {})
        if era not in era_correlation:
            era_correlation[era] = {"long_views": [], "short_subs": []}
        era_correlation[era]["long_views"].append(lr["views"])
        era_correlation[era]["short_subs"].append(short_data.get("subscribers_gained", 0))

    era_summary = {
        era: {
            "paired_count": len(data["long_views"]),
            "avg_long_views": round(sum(data["long_views"]) / len(data["long_views"]), 0),
            "avg_short_subs": round(sum(data["short_subs"]) / len(data["short_subs"]), 1),
        }
        for era, data in era_correlation.items()
    }

    lift_pct = round((avg_views_with - avg_views_without) / max(avg_views_without, 1) * 100, 1) if avg_views_without else 0
    n_paired = len(with_short)

    return {
        "topics_with_shorts": n_paired,
        "topics_without_shorts": len(without_short),
        "avg_views_with_short": round(avg_views_with, 0),
        "avg_views_without_short": round(avg_views_without, 0),
        "view_lift_pct": lift_pct,
        "avg_subs_with_short": round(avg_subs_with, 1),
        "avg_subs_without_short": round(avg_subs_without, 1),
        "era_correlation": era_summary,
        "sample_size_note": f"{n_paired} paired, {len(without_short)} unpaired — "
                            f"{'directional only' if n_paired < 5 else 'moderate confidence'}",
    }


# ── Content quality correlation ───────────────────────────────────────────────

def _extract_structural_features(video: dict, analytics_row: dict) -> dict | None:
    """Extract structural features from a video's pipeline_state + analytics."""
    ps = video.get("pipeline_state") or {}
    if isinstance(ps, str):
        try:
            ps = json.loads(ps)
        except Exception:
            return None
    if not ps or not ps.get("stage_3"):
        return None

    stage_2 = ps.get("stage_2") or {}
    stage_3 = ps.get("stage_3") or {}
    stage_4 = ps.get("stage_4") or {}
    stage_6 = ps.get("stage_6") or {}
    stage_7 = ps.get("stage_7") or {}

    # Narrative structure
    structure_type = stage_3.get("structure_type", "unknown")
    estimated_length = stage_3.get("estimated_length_minutes", 0)

    # Hook classification
    full_script = stage_4.get("full_script", "")
    hook_type = "unknown"
    script_quality = {}
    if full_script:
        try:
            from intel.content_classifier import classify_hook, analyze_script_quality
            hook_info = classify_hook(full_script)
            hook_type = hook_info.get("hook_type", "unknown")
            script_quality = analyze_script_quality(full_script)
        except Exception:
            pass

    # Scene metrics
    scenes = stage_7.get("scenes", [])
    total_scenes = len(scenes) if scenes else stage_7.get("total_scenes", 0)
    reveal_count = sum(1 for s in scenes if s.get("is_reveal_moment"))
    mood_counts = {}
    for s in scenes:
        mood = s.get("mood", "unknown")
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
    dark_tense_ratio = round(
        (mood_counts.get("dark", 0) + mood_counts.get("tense", 0)) / max(total_scenes, 1), 2
    )
    retention_hooks_used = sum(1 for s in scenes if s.get("retention_hook"))

    # Angle features
    has_twist = bool(stage_2.get("twist_potential"))
    has_hook_moment = bool(stage_2.get("hook_moment"))

    # Performance metrics
    views = analytics_row.get("views", 0)
    retention = analytics_row.get("avg_view_percentage", 0)
    ctr = analytics_row.get("ctr_pct", 0)
    subs = analytics_row.get("subscribers_gained", 0)
    engagement = analytics_row.get("engagement_rate", 0)

    return {
        "title": video.get("title", ""),
        "topic": video.get("topic", ""),
        "structure_type": structure_type,
        "estimated_length": estimated_length,
        "hook_type": hook_type,
        "word_count": script_quality.get("word_count", stage_4.get("word_count", 0)),
        "avg_sentence_length": script_quality.get("avg_sentence_length", 0),
        "sentence_length_variance": script_quality.get("sentence_length_variance", 0),
        "short_sentence_pct": script_quality.get("short_sentence_pct", 0),
        "question_density": script_quality.get("questions_per_1000_words", 0),
        "emotional_word_density": script_quality.get("emotional_word_density", 0),
        "dialogue_pct": script_quality.get("dialogue_pct", 0),
        "transition_count": script_quality.get("transition_count", 0),
        "readability_grade": script_quality.get("readability_grade", 0),
        "total_scenes": total_scenes,
        "reveal_count": reveal_count,
        "dark_tense_ratio": dark_tense_ratio,
        "retention_hooks_used": retention_hooks_used,
        "has_twist": has_twist,
        "has_hook_moment": has_hook_moment,
        "tag_count": len(stage_6.get("tags", [])),
        # Performance
        "views": views,
        "retention": retention,
        "ctr": ctr,
        "subscribers_gained": subs,
        "engagement_rate": engagement,
        "has_full_pipeline": True,
    }


def _pearson(xs: list, ys: list) -> float | None:
    """Simple Pearson correlation coefficient. Returns None if insufficient data."""
    import math
    n = len(xs)
    if n < 3:
        return None
    if any(math.isnan(v) or math.isinf(v) for v in xs) or any(math.isnan(v) or math.isinf(v) for v in ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    denom = den_x * den_y
    if denom < 1e-9:
        return None
    return round(num / denom, 3)


def _compute_feature_correlations(rows: list) -> dict:
    """Compute correlations between structural features and performance metrics."""
    correlations = {}

    # Categorical correlations: group by category, compute avg performance
    def _categorical(key, metric="retention"):
        groups = {}
        view_groups = {}
        for r in rows:
            val = r.get(key, "unknown")
            if val and val != "unknown":
                groups.setdefault(val, []).append(r.get(metric, 0))
                view_groups.setdefault(val, []).append(r.get("views", 0))
        return {
            k: {"avg_retention": round(sum(v) / len(v), 1),
                "avg_views": round(sum(view_groups.get(k, [0])) / len(v), 0),
                "count": len(v)}
            for k, v in groups.items() if len(v) >= 1
        }

    correlations["structure_type_vs_retention"] = _categorical("structure_type")
    correlations["hook_type_vs_retention"] = _categorical("hook_type")

    # Numeric correlations against retention
    numeric_features = [
        "word_count", "avg_sentence_length", "sentence_length_variance",
        "short_sentence_pct", "question_density", "emotional_word_density",
        "dialogue_pct", "transition_count", "total_scenes", "reveal_count",
        "dark_tense_ratio", "retention_hooks_used", "readability_grade", "tag_count",
    ]
    script_corr = {}
    for feat in numeric_features:
        xs = [r.get(feat, 0) for r in rows]
        ys = [r.get("retention", 0) for r in rows]
        r_val = _pearson(xs, ys)
        if r_val is not None:
            script_corr[feat] = r_val
    correlations["script_quality_correlations"] = script_corr

    # Boolean correlations
    for bool_feat in ["has_twist", "has_hook_moment"]:
        with_feat = [r for r in rows if r.get(bool_feat)]
        without_feat = [r for r in rows if not r.get(bool_feat)]
        if with_feat and without_feat:
            correlations[f"{bool_feat}_impact"] = {
                "with": {
                    "avg_retention": round(sum(r["retention"] for r in with_feat) / len(with_feat), 1),
                    "avg_views": round(sum(r["views"] for r in with_feat) / len(with_feat), 0),
                    "count": len(with_feat),
                },
                "without": {
                    "avg_retention": round(sum(r["retention"] for r in without_feat) / len(without_feat), 1),
                    "avg_views": round(sum(r["views"] for r in without_feat) / len(without_feat), 0),
                    "count": len(without_feat),
                },
            }

    # Scene count bands
    bands = {"15-20": (15, 20), "20-25": (20, 25), "25-30": (25, 30), "30+": (30, 999)}
    scene_band_perf = {}
    for label, (lo, hi) in bands.items():
        band_rows = [r for r in rows if lo <= r.get("total_scenes", 0) <= hi]
        if band_rows:
            scene_band_perf[label] = {
                "avg_retention": round(sum(r["retention"] for r in band_rows) / len(band_rows), 1),
                "count": len(band_rows),
            }
    if scene_band_perf:
        correlations["scene_count_bands"] = scene_band_perf

    return correlations


def _analyze_content_correlations(correlations: dict, rows: list) -> dict:
    """Use Claude Opus to interpret content quality correlations."""
    from core.agent_wrapper import call_agent

    # Build a concise data summary for Claude
    summary_lines = [f"Sample size: {len(rows)} videos with full pipeline data.\n"]

    struct = correlations.get("structure_type_vs_retention", {})
    if struct:
        summary_lines.append("Narrative structure vs retention:")
        for k, v in sorted(struct.items(), key=lambda x: -x[1]["avg_retention"]):
            summary_lines.append(f"  {k}: {v['avg_retention']}% retention, {v['avg_views']} avg views ({v['count']}v)")

    hook = correlations.get("hook_type_vs_retention", {})
    if hook:
        summary_lines.append("\nHook type vs retention:")
        for k, v in sorted(hook.items(), key=lambda x: -x[1]["avg_retention"]):
            summary_lines.append(f"  {k}: {v['avg_retention']}% retention ({v['count']}v)")

    script_corr = correlations.get("script_quality_correlations", {})
    strong = [(k, v) for k, v in script_corr.items() if abs(v) > 0.15]
    if strong:
        summary_lines.append("\nScript features correlated with retention (Pearson r):")
        for k, v in sorted(strong, key=lambda x: -abs(x[1])):
            summary_lines.append(f"  {k}: r={v}")

    for bf in ["has_twist_impact", "has_hook_moment_impact"]:
        impact = correlations.get(bf, {})
        if impact:
            summary_lines.append(f"\n{bf}:")
            for group in ["with", "without"]:
                d = impact.get(group, {})
                summary_lines.append(f"  {group}: {d.get('avg_retention', 0)}% retention, {d.get('avg_views', 0)} views ({d.get('count', 0)}v)")

    bands = correlations.get("scene_count_bands", {})
    if bands:
        summary_lines.append("\nScene count bands vs retention:")
        for label, d in bands.items():
            summary_lines.append(f"  {label} scenes: {d['avg_retention']}% retention ({d['count']}v)")

    data_summary = "\n".join(summary_lines)

    system = """You are a YouTube content strategist analyzing how content STRUCTURE affects performance.
You're given correlation data between structural features (hook type, narrative structure, script metrics,
scene composition) and YouTube performance (retention %, views, CTR, subs).

Return JSON with:
{
  "strongest_signals": ["signal 1 — plain English finding", "signal 2", "signal 3"],
  "agent_recommendations": {
    "narrative_architect": "1-2 sentence recommendation on which narrative structures work best",
    "script_writer": "1-2 sentence recommendation on script style (sentence length, questions, emotion, pacing)",
    "scene_breakdown": "1-2 sentence recommendation on scene count, mood mix, reveal placement",
    "thumbnail": "1-2 sentence recommendation on what visual approaches correlate with CTR"
  },
  "surprising_findings": ["any counter-intuitive finding worth noting"],
  "confidence_note": "one sentence on sample size and confidence level"
}

Be specific with numbers. If data is sparse, say so. Return ONLY valid JSON."""

    try:
        result = call_agent(
            "12_analytics_agent",
            system_prompt=system,
            user_prompt=f"Analyze these content quality correlations:\n\n{data_summary}",
            max_tokens=2000,
            stage_num=12,
            expect_json=True,
        )
        if isinstance(result, str):
            import json
            result = json.loads(result)
        return result
    except Exception as e:
        print(f"[Analytics] Content correlation Claude analysis failed: {e}")
        return {"strongest_signals": [], "agent_recommendations": {},
                "surprising_findings": [], "confidence_note": "Analysis unavailable."}


def compute_content_quality_correlation(videos: list, analytics_rows: list) -> dict:
    """
    Extract structural features from each video's pipeline_state,
    correlate against YouTube performance, and use Claude for interpretation.
    """
    if not videos or not analytics_rows:
        return {}

    # Build youtube_id → analytics lookup
    analytics_by_id = {}
    for row in analytics_rows:
        yt_id = row.get("youtube_id", "")
        if yt_id:
            analytics_by_id[yt_id] = row

    # Extract features for each video that has both pipeline_state and analytics
    feature_rows = []
    for video in videos:
        yt_id = video.get("youtube_id", "")
        if not yt_id or yt_id not in analytics_by_id:
            continue
        features = _extract_structural_features(video, analytics_by_id[yt_id])
        if features:
            feature_rows.append(features)

    if len(feature_rows) < 2:
        print(f"[Analytics] Content quality: only {len(feature_rows)} videos with pipeline data, skipping")
        return {}

    print(f"[Analytics] Content quality: extracting features from {len(feature_rows)} videos")

    # Compute correlations
    correlations = _compute_feature_correlations(feature_rows)

    # Claude deep analysis
    claude_analysis = _analyze_content_correlations(correlations, feature_rows)

    return {
        "feature_correlations": correlations,
        "claude_analysis": claude_analysis,
        "sample_size": len(feature_rows),
        "videos_with_pipeline_data": len([r for r in feature_rows if r.get("has_full_pipeline")]),
    }


# ── Claude deep analysis ──────────────────────────────────────────────────────

def _safe_defaults():
    """Return safe default analysis when Claude fails or insufficient data."""
    return {
        "title_pattern_analysis": {"high_ctr_patterns": [], "low_ctr_patterns": [],
                                    "avg_ctr_by_title_length": {}, "best_opening_words": [], "worst_opening_words": []},
        "retention_analysis": {"optimal_length_minutes": 9.0, "retention_verdict": "neutral",
                                "retention_note": "Insufficient data for retention verdict."},
        "tag_performance": {"high_performing_tags": [], "low_performing_tags": [], "recommended_tag_mix": ""},
        "agent_intelligence": {"topic_discovery": "", "narrative_architect": "", "seo_agent": "", "script_writer": ""},
        "dna_confidence_updates": {"open_mid_action_hook": 0.3, "twist_reveal_ending": 0.3,
                                    "ancient_medieval_priority": 0.3, "10_15_min_standard_length": 0.3,
                                    "present_tense_narration": 0.3, "dark_thumbnail_aesthetic": 0.3},
        "experiment_recommendations": [],
    }


def _analyze_titles_and_retention(stats: dict) -> dict:
    """Opus pass 1: Deep title pattern analysis + retention intelligence."""
    from core.agent_wrapper import call_agent

    n_videos = stats.get("n_videos", 0)
    early_prefix = f"[EARLY DATA — {n_videos} videos] " if n_videos < 5 else ""

    prompt = f"""You are the title and retention intelligence engine for The Obsidian Archive, a dark history YouTube documentary channel targeting Indian audiences aged 18-35.

CHANNEL PERFORMANCE DATA:
{json.dumps(stats, indent=2)}

Analyze the TITLES and RETENTION data above. Look for non-obvious patterns — correlations between word choice and CTR, title length sweet spots, retention drop-off patterns that reveal pacing issues.

Return a JSON object with EXACTLY this structure:
{{
  "title_pattern_analysis": {{
    "high_ctr_patterns": ["describe 2-3 title STRUCTURES (not just examples) that correlate with high CTR — be specific about word order, punctuation, emotional triggers"],
    "low_ctr_patterns": ["describe 1-2 title structures from the bottom performers — what makes them fail"],
    "avg_ctr_by_title_length": {{
      "under_8_words": 0.0,
      "8_to_12_words": 0.0,
      "over_12_words": 0.0
    }},
    "best_opening_words": ["2-4 words that appear at the start of high-CTR titles — must come from actual data"],
    "worst_opening_words": ["1-2 words or phrases to avoid at title start — must come from actual data"]
  }},
  "retention_analysis": {{
    "optimal_length_minutes": 0.0,
    "retention_verdict": "shorter_wins OR longer_wins OR neutral",
    "retention_note": "one specific sentence with exact numbers about what length works best and why",
    "danger_zones": ["list 1-3 specific minute marks where retention typically drops, with hypotheses about why"],
    "hook_effectiveness": "assessment of first-30-second retention vs channel average, with specific numbers"
  }},
  "tag_performance": {{
    "high_performing_tags": ["5-8 specific tags based on top-performing eras and topics — not generic history tags"],
    "low_performing_tags": ["2-3 overused generic tags to de-emphasise"],
    "recommended_tag_mix": "one sentence instruction on tag strategy with specific ratio (e.g., 60% era-specific, 30% topic, 10% broad)"
  }}
}}

Rules:
- {early_prefix}Every insight must reference at least one specific number from the data
- If a pattern appears in only 1 video, say "early signal (1 video) — needs more data"
- Look for SECOND-ORDER patterns: e.g., "titles with numbers + questions outperform titles with just questions"
- Return ONLY valid JSON, no markdown"""

    try:
        result = call_agent(
            "12_analytics_agent",
            system_prompt="You are a YouTube analytics engine specializing in title optimization and retention analysis. Return only valid JSON.",
            user_prompt=prompt,
            max_tokens=2000,
            stage_num=12,
        )
        if isinstance(result, dict):
            return result
    except Exception as e:
        print(f"[Analytics] Title/retention analysis failed: {e}")
    return {}


def _analyze_agent_intelligence(stats: dict) -> dict:
    """Opus pass 2: Per-agent intelligence briefs."""
    from core.agent_wrapper import call_agent

    n_videos = stats.get("n_videos", 0)
    early_prefix = f"[EARLY DATA — {n_videos} videos] " if n_videos < 5 else ""

    prompt = f"""You are the agent intelligence briefing engine for The Obsidian Archive, a dark history YouTube documentary channel.

CHANNEL PERFORMANCE DATA:
{json.dumps(stats, indent=2)}

Generate targeted intelligence briefs for each creative agent in the pipeline. Each brief must be ACTIONABLE — tell the agent what to DO differently, backed by specific numbers.

Return a JSON object with EXACTLY this structure:
{{
  "agent_intelligence": {{
    "topic_discovery": "{early_prefix}3-4 specific sentences: which eras/topics have the highest views AND subs, which have high views but low subs (entertainment-only), which to avoid entirely. Include specific avg_views and sub_conversion numbers per era.",
    "narrative_architect": "{early_prefix}3-4 specific sentences: what video length maximizes retention, whether 3-act or 4-act structures perform better (if detectable from retention curves), where viewers drop off and what that implies for pacing. Include specific retention percentages.",
    "seo_agent": "{early_prefix}3-4 specific sentences: exact title patterns that drive CTR, optimal title length, which tags correlate with discovery traffic vs browse traffic. Include specific CTR numbers.",
    "script_writer": "{early_prefix}3-4 specific sentences: hook quality assessment (first 30s retention), whether longer claims or rapid-fire revelations retain better, pacing recommendations for the danger zone (40-60% of video). Include specific retention numbers.",
    "scene_breakdown": "{early_prefix}2-3 specific sentences: visual pacing recommendations based on where retention drops, whether text overlays or b-roll moments correlate with retention recovery.",
    "fact_checker": "{early_prefix}1-2 sentences: whether corrections/retractions have impacted viewer trust (comment sentiment if available), recommended verification depth."
  }}
}}

Rules:
- Every sentence must contain at least one specific number from the data
- If you cannot derive an insight, say "insufficient data — default to channel DNA"
- Be PRESCRIPTIVE, not descriptive: "increase hook density in first 30s" not "hook retention is 72%"
- Return ONLY valid JSON, no markdown"""

    try:
        result = call_agent(
            "12_analytics_agent",
            system_prompt="You are a YouTube channel strategist generating per-agent intelligence. Return only valid JSON.",
            user_prompt=prompt,
            max_tokens=2000,
            stage_num=12,
        )
        if isinstance(result, dict):
            return result
    except Exception as e:
        print(f"[Analytics] Agent intelligence analysis failed: {e}")
    return {}


def _analyze_dna_and_experiments(stats: dict) -> dict:
    """Opus pass 3: DNA confidence calibration + experiment recommendations."""
    from core.agent_wrapper import call_agent

    prompt = f"""You are the DNA confidence calibrator for The Obsidian Archive, a dark history YouTube documentary channel.

The channel has a "DNA" — core creative principles. Your job is to assess whether the actual performance data SUPPORTS or CONTRADICTS each DNA element, and recommend experiments to test uncertain areas.

CHANNEL PERFORMANCE DATA:
{json.dumps(stats, indent=2)}

DNA ELEMENTS TO ASSESS:
1. open_mid_action_hook — Videos should open mid-action (no context-setting). Assess: does first-30s retention support this?
2. twist_reveal_ending — Videos should end with a twist/reveal. Assess: does end-retention support this (viewers staying to the end)?
3. ancient_medieval_priority — Ancient/medieval eras should be prioritized. Assess: do era performance numbers support this?
4. 10_15_min_standard_length — Standard length should be 10-15 minutes. Assess: does retention-by-length data support this?
5. present_tense_narration — Scripts should use present tense. Assess: if detectable from engagement/retention, otherwise return 0.3
6. dark_thumbnail_aesthetic — Thumbnails should use dark, moody aesthetics. Assess: if CTR data shows patterns, otherwise return 0.3

Return a JSON object with EXACTLY this structure:
{{
  "dna_confidence_updates": {{
    "open_mid_action_hook": 0.0,
    "twist_reveal_ending": 0.0,
    "ancient_medieval_priority": 0.0,
    "10_15_min_standard_length": 0.0,
    "present_tense_narration": 0.30,
    "dark_thumbnail_aesthetic": 0.30
  }},
  "dna_reasoning": {{
    "open_mid_action_hook": "one sentence explaining why you assigned this score",
    "twist_reveal_ending": "one sentence",
    "ancient_medieval_priority": "one sentence",
    "10_15_min_standard_length": "one sentence",
    "present_tense_narration": "one sentence",
    "dark_thumbnail_aesthetic": "one sentence"
  }},
  "experiment_recommendations": [
    "3-4 specific experiment ideas: each must include WHAT to change, HOW to measure success, and EXPECTED impact. Focus on testing uncertain DNA elements."
  ]
}}

Scoring:
- 0.1 = strong evidence AGAINST this DNA element (data shows it hurts performance)
- 0.3 = no data / neutral / cannot assess
- 0.5 = mixed signals
- 0.7 = moderate evidence FOR
- 0.9 = strong evidence FOR (data clearly shows it helps)
- Return ONLY valid JSON, no markdown"""

    try:
        result = call_agent(
            "12_analytics_agent",
            system_prompt="You are a YouTube channel DNA calibrator. Assess creative principles against real data. Return only valid JSON.",
            user_prompt=prompt,
            max_tokens=2000,
            stage_num=12,
        )
        if isinstance(result, dict):
            return result
    except Exception as e:
        print(f"[Analytics] DNA/experiments analysis failed: {e}")
    return {}


def analyze_with_claude(stats: dict) -> dict:
    """
    Run 3 focused Opus analysis passes on channel performance data.
    Split into separate calls for higher quality vs the old single-prompt approach.
    """
    defaults = _safe_defaults()

    print("[Analytics] Running Opus deep analysis — pass 1/3: titles & retention...")
    titles = _analyze_titles_and_retention(stats)

    print("[Analytics] Running Opus deep analysis — pass 2/3: agent intelligence...")
    intel = _analyze_agent_intelligence(stats)

    print("[Analytics] Running Opus deep analysis — pass 3/3: DNA & experiments...")
    dna = _analyze_dna_and_experiments(stats)

    # Merge all three passes into a single result
    merged = dict(defaults)
    if titles:
        merged["title_pattern_analysis"] = titles.get("title_pattern_analysis", defaults["title_pattern_analysis"])
        merged["retention_analysis"] = titles.get("retention_analysis", defaults["retention_analysis"])
        merged["tag_performance"] = titles.get("tag_performance", defaults["tag_performance"])
    if intel:
        merged["agent_intelligence"] = intel.get("agent_intelligence", defaults["agent_intelligence"])
    if dna:
        merged["dna_confidence_updates"] = dna.get("dna_confidence_updates", defaults["dna_confidence_updates"])
        merged["experiment_recommendations"] = dna.get("experiment_recommendations", defaults["experiment_recommendations"])
        # Store reasoning for debugging/dashboard
        if dna.get("dna_reasoning"):
            merged["dna_reasoning"] = dna["dna_reasoning"]

    return merged


# ── DNA confidence merge ──────────────────────────────────────────────────────

def _merge_dna_confidence(new_scores: dict) -> dict:
    """
    Merge new DNA scores with existing channel_insights.json scores.
    0.3 means 'no data / neutral' — Claude's way of saying it can't assess this.
    Never overwrite a previously validated score with 0.3; keep the old value.
    When Claude has evidence (score != 0.3), blend with old score to smooth transitions
    and allow scores to decrease over time as evidence shifts.
    """
    NEUTRAL = 0.3
    BLEND_WEIGHT = 0.6  # how much weight new evidence gets vs old score
    try:
        existing = json.loads(INSIGHTS_FILE.read_text()) if INSIGHTS_FILE.exists() else {}
        old_scores = existing.get("dna_confidence_updates", {})
    except Exception:
        old_scores = {}

    merged = dict(old_scores)  # start from previous validated scores
    for key, value in new_scores.items():
        if value != NEUTRAL:  # Claude has evidence — blend with old score
            old = old_scores.get(key, NEUTRAL)
            merged[key] = round(old * (1 - BLEND_WEIGHT) + value * BLEND_WEIGHT, 2)
        elif key not in merged:  # no prior score either — use neutral as starting point
            merged[key] = NEUTRAL
        # else: Claude returned 0.3 but we have a prior score — keep the prior score
    return merged


# ── Build channel_insights.json ───────────────────────────────────────────────

def build_channel_insights(stats: dict, claude_analysis: dict, yt_available: bool) -> dict:
    """Assemble the full channel_insights.json structure."""
    n = stats.get("n_videos", 0)

    if not yt_available or n == 0:
        confidence_level = "none"
    elif n < 2:
        confidence_level = "none"
    elif n < 5:
        confidence_level = "low"
    else:
        confidence_level = "sufficient"

    sorted_all = sorted(
        [r for r in stats.get("top_5_by_views", []) + stats.get("bottom_5_by_views", [])],
        key=lambda x: x["views"], reverse=True
    )
    seen = set()
    deduped = []
    for r in sorted_all:
        k = r.get("youtube_id") or r.get("title", "")
        if k not in seen:
            seen.add(k)
            deduped.append(r)

    return {
        "schema_version": "1.1",
        "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_quality": {
            "videos_analyzed":    n,
            "videos_with_ctr":    stats.get("n_with_ctr", 0),
            "videos_with_retention": stats.get("n_with_retention", 0),
            "confidence_level":   confidence_level,
            "confidence_note":    "sufficient=5+ videos; low=2-4; none=0-1 or no API",
            "yt_api_available":   yt_available,
        },
        "channel_health": {
            "avg_views_per_video":           stats.get("avg_views", 0),
            "avg_ctr_pct":                   stats.get("avg_ctr_pct", 0),
            "avg_retention_pct":             stats.get("avg_retention_pct", 0),
            "avg_subscribers_gained_per_video": stats.get("avg_subscribers_gained", 0),
            "total_videos_published":        n,
            "top_quartile_view_threshold":   stats.get("top_quartile_threshold", 0),
        },
        "era_performance":         stats.get("era_performance", {}),
        "top_performing_videos":   deduped[:5],
        "bottom_performing_videos": stats.get("bottom_5_by_ctr", [])[-3:],
        "title_pattern_analysis":  claude_analysis.get("title_pattern_analysis", {}),
        "retention_analysis": {
            **claude_analysis.get("retention_analysis", {}),
            "retention_by_length_band": stats.get("retention_by_length", {}),
        },
        "tag_performance":         claude_analysis.get("tag_performance", {}),
        "agent_intelligence":      claude_analysis.get("agent_intelligence", {}),
        "dna_confidence_updates":  _merge_dna_confidence(claude_analysis.get("dna_confidence_updates", {})),
        "experiment_recommendations": claude_analysis.get("experiment_recommendations", []),
    }


# ── Legacy helpers (kept for lessons_learned.json backward compat) ────────────

def _legacy_generate_guidance(stats: dict, claude_analysis: dict) -> dict:
    """Generate agent guidance strings for lessons_learned.json backward compatibility."""
    intel = claude_analysis.get("agent_intelligence", {})
    return {
        "agent_00": intel.get("topic_discovery", ""),
        "agent_03": intel.get("narrative_architect", ""),
        "agent_04": intel.get("script_writer", ""),
        "agent_06": intel.get("seo_agent", ""),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

# ── Comment sentiment analysis ────────────────────────────────────────────

def _fetch_comments(video_id: str, max_results: int = 20) -> list:
    """Fetch top-level comments for a video using YouTube Data API v3."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        TOKEN_FILE = Path(__file__).resolve().parent.parent / "youtube_token.json"
        if not TOKEN_FILE.exists():
            return []
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance",
            textFormat="plainText",
        ).execute()
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet.get("textDisplay", ""),
                "likes": snippet.get("likeCount", 0),
            })
        return comments
    except Exception:
        return []


def _analyze_comments(video_rows: list) -> dict:
    """Analyze comment sentiment across all videos using Claude for deep NLP understanding."""
    all_comments = []
    for row in video_rows:
        yt_id = row.get("youtube_id", "")
        if not yt_id:
            continue
        comments = _fetch_comments(yt_id, max_results=15)
        for c in comments:
            c["video_id"] = yt_id
            c["video_title"] = row.get("title", "")
        all_comments.extend(comments)

    if not all_comments:
        return {}

    # Build comment digest for Claude (truncate to keep prompt manageable)
    comment_digest = []
    for c in all_comments[:100]:  # cap at 100 comments
        likes = c.get("likes", 0)
        like_tag = f" [{likes} likes]" if likes > 2 else ""
        comment_digest.append(f"[{c.get('video_title', '')[:40]}]{like_tag} {c['text'][:200]}")

    digest_text = "\n".join(comment_digest)

    try:
        from core.agent_wrapper import call_agent

        result = call_agent(
            "12_analytics_agent",
            system_prompt="You are a YouTube comment analyst for The Obsidian Archive, a dark history documentary channel. Analyze comments for actionable audience intelligence. Return only valid JSON.",
            user_prompt=f"""Analyze these {len(all_comments)} YouTube comments from a dark history documentary channel.

COMMENTS:
{digest_text}

Return a JSON object with EXACTLY this structure:
{{
  "total_comments": {len(all_comments)},
  "sentiment_breakdown": {{
    "positive_pct": 0.0,
    "negative_pct": 0.0,
    "neutral_pct": 0.0
  }},
  "audience_topic_requests": ["list of 3-8 specific historical topics/events viewers are requesting — extract even implicit requests like 'I wish someone would cover X' or 'what about Y?'. Clean up to proper topic names."],
  "recurring_praise": ["2-3 specific things viewers consistently praise — e.g., 'narration style', 'research depth', 'twist endings'"],
  "recurring_criticism": ["1-3 specific criticisms or suggestions for improvement — be honest, not generic"],
  "engagement_signals": {{
    "high_engagement_topics": ["1-3 video topics that generate the most passionate discussion"],
    "debate_topics": ["topics where viewers disagree with each other or the creator — these drive watch time"],
    "viewer_expertise_areas": ["areas where viewers show deep knowledge — these are your super-fans' interests"]
  }},
  "content_opportunities": ["2-3 specific content ideas derived from comment patterns — things viewers want but haven't explicitly asked for"]
}}

Rules:
- Extract topic requests even from informal language ("bro do the dancing plague" → "The Dancing Plague of 1518")
- Distinguish genuine criticism from trolling (ignore obvious trolls)
- Weight high-liked comments more heavily in your analysis
- If a topic is requested by multiple commenters, prioritize it
- Return ONLY valid JSON, no markdown""",
            max_tokens=1500,
            stage_num=12,
        )

        if isinstance(result, dict):
            # Ensure backward-compatible keys exist
            sentiment = result.get("sentiment_breakdown", {})
            result["positive_pct"] = sentiment.get("positive_pct", 0)
            result["negative_pct"] = sentiment.get("negative_pct", 0)
            result["request_pct"] = round(
                len(result.get("audience_topic_requests", [])) / max(len(all_comments), 1) * 100, 1
            )
            if "total_comments" not in result:
                result["total_comments"] = len(all_comments)
            return result

    except Exception as e:
        print(f"[Analytics] Claude comment analysis failed, falling back to keyword matching: {e}")

    # Fallback: basic keyword matching if Claude fails
    POSITIVE = ["amazing", "incredible", "love", "best", "awesome", "great", "brilliant",
                "fascinating", "excellent", "masterpiece", "underrated", "subscribe", "more"]
    NEGATIVE = ["boring", "bad", "worst", "hate", "waste", "wrong", "inaccurate",
                "clickbait", "misleading", "too long", "too short", "slow"]
    pos_count = neg_count = 0
    topic_requests = []
    for c in all_comments:
        text = c["text"].lower()
        if any(w in text for w in POSITIVE):
            pos_count += 1
        if any(w in text for w in NEGATIVE):
            neg_count += 1
        for phrase in ["make a video about", "cover ", "do a video on", "next video about"]:
            idx = text.find(phrase)
            if idx >= 0:
                request_text = text[idx + len(phrase):idx + len(phrase) + 60].strip()
                request_text = re.sub(r'[.!?,;].*', '', request_text).strip()
                if len(request_text) > 5:
                    topic_requests.append(request_text)

    total = len(all_comments)
    return {
        "total_comments": total,
        "positive_pct": round(pos_count / total * 100, 1) if total else 0,
        "negative_pct": round(neg_count / total * 100, 1) if total else 0,
        "request_pct": round(len(topic_requests) / max(total, 1) * 100, 1),
        "audience_topic_requests": topic_requests[:5],
    }


def run() -> dict:
    print(f"\n{'='*60}")
    print(f"  ANALYTICS AGENT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    from clients.supabase_client import get_client
    sb = get_client()

    # 1. Fetch all uploaded videos
    videos_result = sb.table("videos").select(
        "id, topic, title, youtube_id, duration_seconds, word_count, created_at, pipeline_state"
    ).order("created_at", desc=True).execute()
    videos = videos_result.data or []

    def _is_short(v):
        ps = v.get("pipeline_state") or {}
        if isinstance(ps, str):
            try:
                ps = json.loads(ps)
            except Exception:
                ps = {}
        if ps.get("is_short"):
            return True
        return (v.get("duration_seconds") or 999) < 90

    long_videos  = [v for v in videos if not _is_short(v)]
    short_videos = [v for v in videos if _is_short(v)]
    print(f"[Analytics] Found {len(long_videos)} long-form + {len(short_videos)} shorts in Supabase")

    if not videos:
        print("[Analytics] No videos to analyse. Exiting.")
        return {}

    # 2. Connect to YouTube Analytics
    try:
        yt_analytics = get_youtube_analytics_client()
        yt_available = True
    except Exception as e:
        print(f"[Analytics] YouTube Analytics unavailable: {e}")
        yt_available = False
        yt_analytics = None

    # 3. Fetch per-video analytics (long-form + shorts)
    video_analytics_rows = []
    shorts_analytics_rows = []
    # Collectors for new expanded metrics
    all_traffic_sources = []
    all_first_48h = []
    all_retention_curves = []
    all_search_terms = []
    all_engagement = []
    all_endscreen = []

    for video in videos:
        youtube_id = video.get("youtube_id", "")
        if not youtube_id:
            continue

        label = (video.get("title") or video.get("topic") or youtube_id)[:50]
        print(f"[Analytics] Fetching: {label}")

        stats_row = (
            fetch_video_analytics(yt_analytics, youtube_id)
            if yt_available
            else {"views": 0, "watch_time_minutes": 0.0, "avg_view_percentage": 0.0,
                  "subscribers_gained": 0, "ctr_pct": 0.0, "impressions": 0,
                  "likes": 0, "comments": 0, "shares": 0, "engagement_rate": 0.0, "like_ratio": 0.0}
        )

        row = {
            "topic":             video.get("topic", ""),
            "title":             video.get("title", ""),
            "youtube_id":        youtube_id,
            "supabase_video_id": video.get("id"),
            "duration_seconds":  video.get("duration_seconds", 0),
            **stats_row,
        }

        # Fetch expanded metrics (only when YT API available)
        if yt_available:
            # Traffic sources
            try:
                traffic = fetch_traffic_sources(yt_analytics, youtube_id)
                row["traffic_sources"] = traffic
                all_traffic_sources.append(traffic)
            except Exception as e:
                print(f"  [Analytics] Traffic sources skipped for {youtube_id}: {e}")

            # First 48h performance
            try:
                upload_date = video.get("created_at", "")
                if upload_date:
                    first_48h = fetch_first_48h_performance(yt_analytics, youtube_id, upload_date)
                    row["first_48h"] = first_48h
                    first_48h_entry = {**first_48h, "youtube_id": youtube_id,
                                       "title": video.get("title", "")}
                    all_first_48h.append(first_48h_entry)
            except Exception as e:
                print(f"  [Analytics] First 48h skipped for {youtube_id}: {e}")

            # Retention curve
            try:
                retention = fetch_retention_curve(yt_analytics, youtube_id, duration_seconds=video.get("duration_seconds", 0) or 0)
                row["retention_curve_data"] = retention
                all_retention_curves.append(retention)
            except Exception as e:
                print(f"  [Analytics] Retention curve skipped for {youtube_id}: {e}")

            # Search terms
            try:
                search_terms = fetch_search_terms(yt_analytics, youtube_id)
                row["search_terms"] = search_terms
                all_search_terms.append(search_terms)
            except Exception as e:
                print(f"  [Analytics] Search terms skipped for {youtube_id}: {e}")

            # Engagement (already fetched inside fetch_video_analytics, collect for aggregation)
            engagement_entry = {
                "likes": stats_row.get("likes", 0),
                "comments": stats_row.get("comments", 0),
                "shares": stats_row.get("shares", 0),
                "engagement_rate": stats_row.get("engagement_rate", 0.0),
                "like_ratio": stats_row.get("like_ratio", 0.0),
            }
            all_engagement.append(engagement_entry)

            # End screen & card performance
            try:
                endscreen = fetch_endscreen_performance(yt_analytics, youtube_id)
                row["endscreen_performance"] = endscreen
                all_endscreen.append(endscreen)
            except Exception as e:
                print(f"  [Analytics] Endscreen metrics skipped for {youtube_id}: {e}")

        if _is_short(video):
            shorts_analytics_rows.append(row)
        else:
            video_analytics_rows.append(row)

        # Write to Supabase analytics table
        analytics_row = {
            "video_id":            video.get("id"),
            "views":               stats_row["views"],
            "watch_time_hours":    round(stats_row["watch_time_minutes"] / 60, 4),
            "avg_view_percentage": round(stats_row.get("avg_view_percentage", 0), 2),
            "subscribers_gained":  stats_row["subscribers_gained"],
            "ctr_pct":             round(stats_row.get("ctr_pct", 0), 3),
            "impressions":         stats_row.get("impressions", 0),
            "recorded_at":         datetime.now(timezone.utc).isoformat(),
        }
        try:
            sb.table("analytics").upsert(analytics_row, on_conflict="video_id").execute()
        except Exception as e:
            err_str = str(e)
            if "column" in err_str and "schema cache" in err_str:
                # Column doesn't exist yet — try with minimal fields
                minimal_row = {
                    "video_id":           video.get("id"),
                    "views":              stats_row["views"],
                    "watch_time_hours":   round(stats_row["watch_time_minutes"] / 60, 4),
                    "subscribers_gained": stats_row["subscribers_gained"],
                    "recorded_at":        datetime.now(timezone.utc).isoformat(),
                }
                try:
                    sb.table("analytics").upsert(minimal_row, on_conflict="video_id").execute()
                    print("  [Analytics] Wrote with minimal fields (run schema migration to enable full analytics)")
                except Exception as e2:
                    print(f"  [Analytics] Could not write to analytics table: {e2}")
            else:
                print(f"  [Analytics] Could not write to analytics table: {e}")

    # 3.5. Fetch channel-level demographics (once per cycle, not per video)
    demographics = {}
    if yt_available:
        try:
            demographics = fetch_demographics(yt_analytics)
            if demographics.get("top_countries"):
                print(f"[Analytics] Demographics: top country={demographics['top_countries'][0]['country']}")
        except Exception as e:
            print(f"[Analytics] Demographics skipped: {e}")

    # 4. Compute statistical summary (pure Python, no API)
    stats = compute_stats_summary(video_analytics_rows)
    print(f"[Analytics] Avg views:     {stats.get('avg_views', 0):.0f}")
    print(f"[Analytics] Avg CTR:       {stats.get('avg_ctr_pct', 0):.1f}%")
    print(f"[Analytics] Avg retention: {stats.get('avg_retention_pct', 0):.1f}%")

    # 5. Claude deep analysis (only if enough data)
    n = len(video_analytics_rows)
    if n >= 2 and yt_available:
        print(f"[Analytics] Running Opus deep analysis on {n} videos (3 focused passes)...")
        claude_analysis = analyze_with_claude(stats)
        print("[Analytics] ✓ Opus deep analysis complete (titles/retention + agent intel + DNA/experiments)")
    else:
        print(f"[Analytics] Skipping deep analysis (n={n}, yt_available={yt_available})")
        claude_analysis = {
            "title_pattern_analysis": {}, "retention_analysis": {}, "tag_performance": {},
            "agent_intelligence": {}, "dna_confidence_updates": {}, "experiment_recommendations": [],
        }

    # 5.5. Shorts intelligence
    shorts_intel = compute_shorts_intelligence(shorts_analytics_rows, video_analytics_rows)
    if shorts_intel:
        print(f"[Analytics] Shorts intelligence: {shorts_intel['total_shorts']} shorts, "
              f"{shorts_intel['total_subs_from_shorts']} total subs, "
              f"{shorts_intel['sub_conversion_rate_pct']:.3f}% conversion")

    # 5.6. Build per_video_stats for content pattern intelligence
    per_video_stats = []
    for row in video_analytics_rows + shorts_analytics_rows:
        title = row.get("title", "") or row.get("topic", "")
        yt_id = row.get("youtube_id", "")
        views = row.get("views", 0)
        ctr = row.get("ctr_pct", 0.0)
        avg_ret = row.get("avg_view_percentage", 0.0)
        watch_min = row.get("watch_time_minutes", 0.0)
        vid_views = max(views, 1)
        avg_view_dur_s = round((watch_min * 60) / vid_views, 2) if watch_min else 0.0

        # Content classification (title-only at analytics time)
        try:
            from intel.content_classifier import classify_video_content
            classification = classify_video_content({"title": title})
        except Exception:
            classification = {}

        entry = {
            "title": title,
            "youtube_id": yt_id,
            "views": views,
            "ctr_pct": round(ctr, 2),
            "avg_retention_pct": round(avg_ret, 1),
            "avg_view_duration_seconds": avg_view_dur_s,
            "subscribers_gained": row.get("subscribers_gained", 0),
            "engagement_rate": row.get("engagement_rate", 0),
            "content_classification": classification,
        }
        per_video_stats.append(entry)

    if per_video_stats:
        print(f"[Analytics] Built per_video_stats for {len(per_video_stats)} videos")

    # 6. Build and write channel_insights.json
    insights = build_channel_insights(stats, claude_analysis, yt_available)
    # 6.0.1 Attach per_video_stats for content pattern intelligence
    if per_video_stats:
        insights["per_video_stats"] = per_video_stats

    if shorts_intel:
        insights["shorts_intelligence"] = shorts_intel
        # Backward-compat key
        insights["shorts_performance"] = {
            "total_shorts": shorts_intel["total_shorts"],
            "total_views": shorts_intel["total_views"],
            "avg_views_per_short": shorts_intel["avg_views_per_short"],
            "total_subs_from_shorts": shorts_intel["total_subs_from_shorts"],
        }

    # 6.1 Add expanded analytics aggregates to insights
    if yt_available:
        # Channel-level CTR from per-video analytics (impressions not available in Analytics API v2 reports)
        try:
            ctr_values = [r.get("ctr_pct", 0) for r in video_analytics_rows if r.get("ctr_pct")]
            if ctr_values:
                ch_ctr = round(sum(ctr_values) / len(ctr_values), 2)
                ch_views = sum(r.get("views", 0) for r in video_analytics_rows)
                insights["channel_ctr"] = {
                    "ctr_pct": ch_ctr,
                    "views": ch_views,
                    "sample_count": len(ctr_values),
                }
                if "channel_health" in insights:
                    insights["channel_health"]["avg_ctr_pct"] = ch_ctr
                print(f"[Analytics] Channel CTR: {ch_ctr:.2f}% (avg across {len(ctr_values)} videos)")
        except Exception as e:
            print(f"[Analytics] Channel CTR computation failed (non-fatal): {e}")

        # Traffic sources — channel-wide mix
        try:
            channel_traffic = _compute_channel_traffic_mix(all_traffic_sources)
            if channel_traffic:
                insights["traffic_sources"] = channel_traffic
                print(f"[Analytics] Traffic mix: primary={channel_traffic.get('primary_source', 'n/a')}")
        except Exception as e:
            print(f"[Analytics] Traffic aggregate failed: {e}")

        # First 48h benchmarks
        try:
            first_48h_bench = _compute_first_48h_benchmarks(all_first_48h)
            if first_48h_bench:
                insights["first_48h_benchmarks"] = first_48h_bench
                print(f"[Analytics] First 48h avg velocity: {first_48h_bench.get('avg_velocity', 0):.1f} views/hr")
        except Exception as e:
            print(f"[Analytics] First 48h benchmarks failed: {e}")

        # Retention curves — aggregate
        try:
            retention_agg = _compute_retention_aggregate(all_retention_curves)
            if retention_agg:
                insights["retention_curves"] = retention_agg
                print(f"[Analytics] Retention aggregate: hook={retention_agg.get('avg_hook_retention_30s', 0):.1f}%, "
                      f"mid={retention_agg.get('avg_midpoint_retention', 0):.1f}%, "
                      f"end={retention_agg.get('avg_end_retention', 0):.1f}%")
        except Exception as e:
            print(f"[Analytics] Retention aggregate failed: {e}")

        # Search intelligence — top terms across all videos
        try:
            top_terms = _compute_top_search_terms(all_search_terms, limit=30)
            total_browse_views = sum(t.get("browse", {}).get("views", 0) for t in all_traffic_sources)
            total_srch_views = sum(t.get("search", {}).get("views", 0) for t in all_traffic_sources)
            classification = "search-driven" if total_srch_views > total_browse_views else "browse-driven"
            insights["search_intelligence"] = {
                "top_search_terms": top_terms,
                "channel_classification": classification,
                "total_search_driven_views": total_srch_views,
                "total_browse_driven_views": total_browse_views,
            }
            if top_terms:
                print(f"[Analytics] Top search term: '{top_terms[0]['term']}' ({top_terms[0]['views']} views)")
        except Exception as e:
            print(f"[Analytics] Search intelligence failed: {e}")

        # Engagement metrics — channel-wide
        try:
            engagement_agg = _compute_avg_engagement(all_engagement)
            if engagement_agg:
                insights["engagement_metrics"] = engagement_agg
                print(f"[Analytics] Avg engagement rate: {engagement_agg.get('avg_engagement_rate', 0):.2f}%")
        except Exception as e:
            print(f"[Analytics] Engagement aggregate failed: {e}")

        # Endscreen/card performance
        try:
            endscreen_agg = _compute_endscreen_aggregate(all_endscreen)
            if endscreen_agg:
                insights["endscreen_performance"] = endscreen_agg
                print(f"[Analytics] Avg card CTR: {endscreen_agg.get('avg_card_ctr', 0):.2f}%")
        except Exception as e:
            print(f"[Analytics] Endscreen aggregate failed: {e}")

        # Audience demographics (also write short key for dashboard compatibility)
        if demographics:
            insights["audience_demographics"] = demographics
            insights["demographics"] = demographics

    # Comment sentiment (compute before write to avoid race condition)
    try:
        comment_sentiment = _analyze_comments(video_analytics_rows)
        if comment_sentiment:
            insights["comment_sentiment"] = comment_sentiment
            # Promote audience requests to top-level key for dashboard
            if comment_sentiment.get("audience_topic_requests"):
                insights["audience_requests"] = comment_sentiment["audience_topic_requests"]
            print(f"[Analytics] Comment sentiment: {comment_sentiment.get('total_comments', 0)} comments")
    except Exception as e:
        print(f"[Analytics] Comment sentiment skipped: {e}")
        comment_sentiment = None

    # ── Community engagement: 48h comment curation ────────────────────────────
    try:
        from intel.community_engagement import run_48h_curation
        from datetime import timedelta as _td
        cutoff_48h = (datetime.now(timezone.utc) - _td(hours=48)).isoformat()
        cutoff_96h = (datetime.now(timezone.utc) - _td(hours=96)).isoformat()
        # Find videos uploaded 48-96h ago (prime curation window)
        for v in long_videos:
            created = v.get("created_at", "")
            yt_id = v.get("youtube_id", "")
            if not yt_id or not created:
                continue
            if cutoff_96h <= created <= cutoff_48h:
                # Check if already curated
                curation_file = Path(__file__).resolve().parent.parent / "outputs" / f"comment_curation_{yt_id}.json"
                if curation_file.exists():
                    continue
                print(f"[Analytics] Running 48h comment curation for {yt_id}")
                curation_result = run_48h_curation(yt_id, v.get("title", ""))
                if curation_result.get("curation", {}).get("telegram_sent"):
                    print(f"[Analytics] Curation recommendations sent for {v.get('title', '')[:40]}")
    except Exception as e:
        print(f"[Analytics] Community curation skipped: {e}")

    # Shorts→Long correlation (compute before write)
    try:
        shorts_correlation = compute_shorts_long_correlation(
            shorts_analytics_rows, video_analytics_rows, videos
        )
        if shorts_correlation and shorts_correlation.get("topics_with_shorts", 0) > 0:
            insights["shorts_long_correlation"] = shorts_correlation
            lift = shorts_correlation.get("view_lift_pct", 0)
            print(f"[Analytics] Shorts→Long correlation: {lift:+.1f}% view lift when short exists "
                  f"({shorts_correlation.get('sample_size_note', '')})")
    except Exception as e:
        print(f"[Analytics] Shorts correlation skipped: {e}")
        shorts_correlation = None

    # Content quality correlation (compute before write)
    try:
        content_correlation = compute_content_quality_correlation(videos, video_analytics_rows)
        if content_correlation and content_correlation.get("sample_size", 0) >= 2:
            insights["content_quality_correlation"] = content_correlation
            print(f"[Analytics] Content quality correlation: {content_correlation['sample_size']} videos, "
                  f"{content_correlation.get('videos_with_pipeline_data', 0)} with full pipeline data")
    except Exception as e:
        print(f"[Analytics] Content quality correlation skipped: {e}")

    # Music-to-performance correlation
    try:
        music_correlation = compute_music_performance_correlation(videos, video_analytics_rows)
        if music_correlation and music_correlation.get("sample_size", 0) >= 3:
            insights["music_performance"] = music_correlation
            print(f"[Analytics] Music performance: {music_correlation['sample_size']} videos, "
                  f"recommendations: {len(music_correlation.get('recommendations', []))}")
    except Exception as e:
        print(f"[Analytics] Music correlation skipped: {e}")

    # Channel stats (compute before write)
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build as _gbuild
        TOKEN_FILE = Path(__file__).resolve().parent.parent / "youtube_token.json"
        if TOKEN_FILE.exists():
            _creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
            if _creds and _creds.expired and _creds.refresh_token:
                from google.auth.transport.requests import Request as _Req
                _creds.refresh(_Req())
                with open(TOKEN_FILE, "w") as _tf:
                    _tf.write(_creds.to_json())
            _yt = _gbuild("youtube", "v3", credentials=_creds)
            _channel = _yt.channels().list(part="statistics", mine=True).execute()
            _items = _channel.get("items", [])
            if _items:
                sub_count = int(_items[0]["statistics"].get("subscriberCount", 0))
                total_views = int(_items[0]["statistics"].get("viewCount", 0))
                insights["channel_stats"] = {
                    "subscriber_count": sub_count,
                    "total_views": total_views,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                # Check milestones
                MILESTONES = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
                milestone_file = Path(__file__).resolve().parent.parent / "outputs" / "last_milestone.txt"
                last_milestone = int(milestone_file.read_text().strip()) if milestone_file.exists() else 0
                for m in MILESTONES:
                    if sub_count >= m > last_milestone:
                        print(f"[Analytics] 🎉 MILESTONE: {m} subscribers!")
                        milestone_file.parent.mkdir(parents=True, exist_ok=True)
                        milestone_file.write_text(str(m))
                        try:
                            from server.notify import _tg
                            _tg(f"🎉 *Milestone Reached: {m:,} Subscribers!*\nTotal views: {total_views:,}")
                        except Exception:
                            pass
                        break
                print(f"[Analytics] Channel: {sub_count:,} subs, {total_views:,} views")
    except Exception as e:
        print(f"[Analytics] Channel stats skipped: {e}")

    # Single atomic write with all data
    _atomic_write_json(INSIGHTS_FILE, insights)
    persist_json_to_supabase(INSIGHTS_FILE, insights)
    print(f"[Analytics] ✓ Channel insights written to {INSIGHTS_FILE.name}")

    # ── Trend alerting: detect and notify on quality trends ───────────────────
    try:
        from intel.trend_alerts import run_trend_analysis
        trend_summary = run_trend_analysis(insights)
        insights["trend_alerts"] = trend_summary
        if trend_summary["total_alerts"] > 0:
            # Re-write insights with trend data included
            _atomic_write_json(INSIGHTS_FILE, insights)
            print(f"[Analytics] Trend alerts: {trend_summary['critical']} critical, "
                  f"{trend_summary['warnings']} warnings, {trend_summary['positive']} positive")
    except Exception as e:
        print(f"[Analytics] Trend alerting skipped: {e}")

    # 7. Write lessons_learned.json (backward compatibility)
    legacy_guidance = _legacy_generate_guidance(stats, claude_analysis)
    lessons = {
        "generated_at":           datetime.now(timezone.utc).isoformat(),
        "performance_summary":    stats,
        "agent_guidance":         legacy_guidance,
        "dna_confidence_updates": insights.get("dna_confidence_updates", {}),
        "raw_video_analytics":    video_analytics_rows,
    }
    # Preserve existing optimizer_runs and doctor_interventions
    if LESSONS_FILE.exists():
        try:
            existing = json.loads(LESSONS_FILE.read_text())
            lessons["optimizer_runs"]       = existing.get("optimizer_runs", [])
            lessons["doctor_interventions"] = existing.get("doctor_interventions", [])
        except Exception:
            pass
    _atomic_write_json(LESSONS_FILE, lessons)
    persist_json_to_supabase(LESSONS_FILE, lessons)
    print(f"[Analytics] Lessons written to {LESSONS_FILE.name}")

    # 8. Boost topic scores in Supabase for the best-performing era
    # Cap at 0.95 to prevent runaway boosting across multiple analytics runs
    era_perf = insights.get("era_performance", {})
    if era_perf:
        best_era = max(era_perf, key=lambda e: era_perf[e].get("avg_views", 0))
        keywords = ERA_KEYWORDS.get(best_era, [])
        if keywords:
            try:
                topics_result = sb.table("topics").select("id, topic, score").eq("status", "queued").execute()
                for t in (topics_result.data or []):
                    current_score = t.get("score") or 0.5
                    if current_score >= 0.95:
                        continue  # already at cap — don't keep boosting
                    if any(kw in t.get("topic", "").lower() for kw in keywords):
                        new_score = round(min(0.95, current_score + 0.10), 3)
                        sb.table("topics").update({"score": new_score}).eq("id", t["id"]).execute()
                        print(f"  [Analytics] Boosted: {t['topic'][:50]} → score {new_score:.2f}")
            except Exception as e:
                print(f"[Analytics] Could not update topic scores: {e}")

    # 9. Auto-queue audience topic requests from comment sentiment into Supabase
    if comment_sentiment:
        requests = comment_sentiment.get("audience_topic_requests", [])
        if requests:
            try:
                sb = get_client()
                existing = sb.table("topics").select("topic").execute()
                existing_lower = {t["topic"].lower() for t in (existing.data or [])}
                queued = 0
                for req in requests[:5]:
                    req_clean = req.strip().title()
                    if len(req_clean) < 8:
                        continue
                    if req_clean.lower() not in existing_lower:
                        sb.table("topics").insert({
                            "topic": req_clean,
                            "status": "queued",
                            "score": 0.4,
                            "source": "audience_request",
                        }).execute()
                        existing_lower.add(req_clean.lower())
                        queued += 1
                if queued:
                    print(f"[Analytics] ✓ Auto-queued {queued} audience-requested topics")
            except Exception as eq:
                print(f"[Analytics] Could not auto-queue audience topics: {eq}")

    # 10. Correlation engine: multi-layer analysis for parameter tuning
    try:
        from intel.correlation_engine import CorrelationEngine
        engine = CorrelationEngine()
        engine_output = engine.run(
            videos=video_analytics_rows,
            shorts=shorts_analytics_rows,
            analytics_rows=[],
            youtube_analytics=yt_analytics if yt_available else None,
        )
        correlation_file = Path(__file__).resolve().parent.parent / "outputs" / "correlation_results.json"
        correlation_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(correlation_file, engine_output)
        persist_json_to_supabase(correlation_file, engine_output)
        insights["correlation_engine"] = {
            "generated_at": engine_output.get("generated_at"),
            "maturity": engine_output.get("maturity"),
            "layer_statuses": {k: v.get("status") for k, v in engine_output.get("layers", {}).items()},
            "recommendation_count": len(engine_output.get("recommendations", [])),
        }
        print(f"[Analytics] Correlation engine: maturity={engine_output.get('maturity')}, "
              f"active layers={engine_output.get('active_layer_count', 0)}")
    except Exception as e:
        print(f"[Analytics] Correlation engine failed (non-critical): {e}")
        insights["correlation_engine"] = {"status": "error", "error": str(e)[:200]}

    # 11. Feedback loops: comment intelligence + content performance signals
    try:
        from core.feedback_loops import aggregate_comment_intelligence, extract_content_performance_signals
        insights["comment_intelligence"] = aggregate_comment_intelligence(insights)
        insights["content_performance_signals"] = extract_content_performance_signals(insights)
        print("[Analytics] ✓ Feedback loops processed")
    except Exception as fl_err:
        print(f"[Analytics] Feedback loops warning: {fl_err}")

    # 12. Parameter optimizer cycle
    try:
        from core.param_history import (
            attach_metrics, load_observations, load_optimizer_state,
            save_optimizer_state, log_optimizer_cycle, is_optimizer_enabled,
            save_pending_approvals, load_pending_approvals, save_override_batch,
        )

        if not is_optimizer_enabled():
            print("[Analytics] Optimizer disabled (kill switch)")
        else:
            # Step 1: Attach metrics to recent observations (48h+ mature)
            try:
                for vid_stat in per_video_stats:
                    yt_id = vid_stat.get("youtube_id", "")
                    if yt_id:
                        attach_metrics(yt_id, {
                            "retention_pct": vid_stat.get("avg_retention_pct", 0),
                            "views_velocity": vid_stat.get("views", 0),
                            "engagement_rate": vid_stat.get("engagement_rate", 0),
                            "sentiment_score": 0.5,
                            "hook_retention_pct": vid_stat.get("avg_retention_pct", 0),
                        })
            except Exception as am_err:
                print(f"[Analytics] Metric attachment warning: {am_err}")

            # Step 2: Run optimizer cycle if enough observations
            try:
                observations = load_observations(min_age_hours=48, limit=50)
                if observations and len(observations) >= 5:
                    from core.param_optimizer import ParamOptimizer, ObservationRecord, PerformanceMetrics, OptimizerState
                    from core.param_registry import get_active_params

                    current_params = get_active_params(format="both")

                    # Convert observations to ObservationRecord
                    obs_records = []
                    for obs in observations:
                        metrics_data = obs.get("metrics", {})
                        if not metrics_data:
                            continue
                        obs_records.append(ObservationRecord(
                            video_id=obs.get("video_id", ""),
                            youtube_id=obs.get("youtube_id", ""),
                            params=obs.get("params", {}),
                            metrics=PerformanceMetrics(
                                retention_pct=metrics_data.get("retention_pct", 0),
                                views_velocity_48h=metrics_data.get("views_velocity_48h", metrics_data.get("views_velocity", 0)),
                                engagement_rate=metrics_data.get("engagement_rate", 0),
                                comment_sentiment_score=metrics_data.get("comment_sentiment_score", metrics_data.get("sentiment_score", 0.5)),
                                hook_retention_30s=metrics_data.get("hook_retention_30s", metrics_data.get("hook_retention_pct", 0)),
                            ),
                            era=obs.get("era", "unknown"),
                            render_compliance=obs.get("render_compliance"),
                        ))

                    if len(obs_records) >= 5:
                        optimizer = ParamOptimizer()

                        # Load or create optimizer state
                        state_dict = load_optimizer_state()
                        if state_dict:
                            opt_state = OptimizerState.from_dict(state_dict)
                        else:
                            opt_state = OptimizerState.fresh(list(current_params.keys()))

                        # Determine confidence from data quality
                        dq = insights.get("data_quality", {})
                        confidence = dq.get("confidence_level", "low")
                        if confidence not in ("none", "low", "sufficient"):
                            confidence = "low"

                        result = optimizer.run_optimization_cycle(
                            obs_records, current_params, opt_state, confidence
                        )

                        # Auto-apply small changes
                        auto_applied = {}
                        pending_approval = []
                        for proposal in result.proposals:
                            if proposal.requires_approval:
                                pending_approval.append({
                                    "param_key": proposal.param_key,
                                    "current_value": proposal.current_value,
                                    "proposed_value": proposal.proposed_value,
                                    "delta": proposal.delta,
                                    "confidence": proposal.confidence,
                                })
                            else:
                                auto_applied[proposal.param_key] = proposal.proposed_value

                        if auto_applied:
                            save_override_batch(auto_applied, approved_by="optimizer")
                            print(f"[Analytics] Optimizer auto-applied: {list(auto_applied.keys())}")

                        if pending_approval:
                            existing = load_pending_approvals() or []
                            existing.extend(pending_approval)
                            save_pending_approvals(existing)
                            print(f"[Analytics] Optimizer: {len(pending_approval)} proposals pending approval")

                        # Save updated state
                        save_optimizer_state(result.state)

                        # Log cycle
                        log_optimizer_cycle({
                            "epoch": result.state.epoch,
                            "observations_used": len(obs_records),
                            "confidence_level": confidence,
                            "proposals": [{"param": p.param_key, "delta": p.delta} for p in result.proposals],
                            "auto_applied": auto_applied,
                            "pending_approval": pending_approval,
                            "rollback_triggered": result.rollback_triggered,
                            "diagnostics": result.diagnostics,
                        })

                        insights["optimizer"] = {
                            "epoch": result.state.epoch,
                            "proposals_count": len(result.proposals),
                            "auto_applied_count": len(auto_applied),
                            "rollback_triggered": result.rollback_triggered,
                            "exploration_rate": result.state.exploration_rate,
                        }
                        print(f"[Analytics] ✓ Optimizer epoch {result.state.epoch}")
                else:
                    print(f"[Analytics] Optimizer: {len(observations or [])} observations (need 5+)")
            except Exception as opt_err:
                print(f"[Analytics] Optimizer cycle warning: {opt_err}")
    except Exception as ph_err:
        print(f"[Analytics] Param history unavailable: {ph_err}")

    print("\n[Analytics] ✓ Complete")
    return insights


if __name__ == "__main__":
    run()

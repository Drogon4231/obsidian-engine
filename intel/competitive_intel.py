"""
competitive_intel.py — Competitive Intelligence Engine for The Obsidian Archive.

Tracks competitor channels in the dark history / documentary YouTube niche.
Crawls their recent uploads, identifies content gaps, trending topics,
and winning thumbnail patterns to inform our pipeline.

Results saved to outputs/competitive_intel.json.
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.append(str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
INTEL_FILE = OUTPUT_DIR / "competitive_intel.json"

# Shorts threshold: videos under this duration (seconds) are classified as Shorts
SHORTS_THRESHOLD = 60

# ── Competitor channel IDs ────────────────────────────────────────────────────
# Dark history / documentary niche channels.
# Format: { "channel_id": "Channel Name" }
COMPETITORS = {
    "UCGzfpg1YiBIlgcODQI4lDvQ": "Voices of the Past",
    "UCMmaBzfCCwZ2KqaBJjkj0fw": "Kings and Generals",
    "UCT6Y5JJPKe_JDMivpKgVXew": "Fall of Civilizations",
    "UCY2-GCz1VMEn94FkyOuRlHg": "Invicta",
    "UCNIuvl7V8zACPpTmmNIqP0A": "OverSimplified",
    "UCv_vLHiWVBh_ES9ww625JQ": "Historia Civilis",        # PLACEHOLDER — verify
    "UCFbxlp3NxEo0PuBOvITwXwA": "Forgotten History",      # PLACEHOLDER — verify
    "UCfdNM3NAhaBOXCafH7krzrA": "The Infographics Show",
    "UCUcyEsEjhPEDf69RRVhRh4A": "Weird History",
    "UCCODtTcd5M1JavPCOr_Uydg": "Extra History / Extra Credits",
}

# ── YouTube API helpers ───────────────────────────────────────────────────────

def _get_youtube_service():
    """Build a YouTube Data API v3 service object."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("[competitive_intel] google-api-python-client not installed — run: pip install google-api-python-client")
        return None

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("[competitive_intel] YOUTUBE_API_KEY not set in environment")
        return None

    try:
        return build("youtube", "v3", developerKey=api_key)
    except Exception as e:
        print(f"[competitive_intel] Failed to build YouTube service: {e}")
        return None


def _parse_duration(iso_duration: str) -> int:
    """Convert ISO 8601 duration (PT12M34S) to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s


def _load_existing_intel() -> dict:
    """Load existing intel file, or return empty structure."""
    if INTEL_FILE.exists():
        try:
            return json.loads(INTEL_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_intel(data: dict):
    """Write intel data with timestamp."""
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    INTEL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[competitive_intel] Saved to {INTEL_FILE}")


def load_competitive_intel() -> dict:
    """Load competitive intel, restoring from Supabase if local file missing."""
    if INTEL_FILE.exists():
        try:
            data = json.loads(INTEL_FILE.read_text())
            if data.get("competitors"):
                return data
        except Exception:
            pass
    try:
        from core.utils import restore_json_from_supabase
        if restore_json_from_supabase(INTEL_FILE):
            return json.loads(INTEL_FILE.read_text())
    except Exception:
        pass
    return {}


# ── Core functions ────────────────────────────────────────────────────────────

def crawl_competitors() -> dict:
    """
    Fetch last 20 videos for each competitor channel.
    Saves results to outputs/competitive_intel.json.
    Returns the full intel dict.
    """
    youtube = _get_youtube_service()
    if not youtube:
        print("[competitive_intel] Cannot crawl — YouTube API unavailable")
        return {}

    intel = _load_existing_intel()
    channels_data = {}

    for channel_id, channel_name in COMPETITORS.items():
        print(f"[competitive_intel] Crawling {channel_name} ({channel_id})...")
        try:
            # Get channel stats
            ch_resp = youtube.channels().list(
                part="statistics,snippet",
                id=channel_id,
            ).execute()

            ch_items = ch_resp.get("items", [])
            if not ch_items:
                print(f"[competitive_intel]   Channel not found: {channel_id}")
                continue

            ch_stats = ch_items[0].get("statistics", {})
            ch_items[0].get("snippet", {})

            # Search for recent uploads
            search_resp = youtube.search().list(
                part="id",
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=20,
            ).execute()

            video_ids = [
                item["id"]["videoId"]
                for item in search_resp.get("items", [])
                if item.get("id", {}).get("videoId")
            ]

            if not video_ids:
                print(f"[competitive_intel]   No videos found for {channel_name}")
                continue

            # Get full video details
            videos_resp = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids),
            ).execute()

            videos = []
            for v in videos_resp.get("items", []):
                snippet = v.get("snippet", {})
                stats = v.get("statistics", {})
                content = v.get("contentDetails", {})
                videos.append({
                    "video_id": v["id"],
                    "title": snippet.get("title", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "publish_date": snippet.get("publishedAt", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "duration_seconds": _parse_duration(content.get("duration", "")),
                })

            # Separate shorts from long-form
            shorts = [v for v in videos if 0 < v["duration_seconds"] < SHORTS_THRESHOLD]
            long_form = [v for v in videos if v["duration_seconds"] >= SHORTS_THRESHOLD or v["duration_seconds"] == 0]

            avg_views_long = (
                sum(v["views"] for v in long_form) / len(long_form)
                if long_form else 0
            )
            avg_views_shorts = (
                sum(v["views"] for v in shorts) / len(shorts)
                if shorts else 0
            )

            channels_data[channel_id] = {
                "name": channel_name,
                "subscriber_count": int(ch_stats.get("subscriberCount", 0)),
                "total_videos": int(ch_stats.get("videoCount", 0)),
                "avg_views_recent_20": round(avg_views_long),
                "avg_views_shorts": round(avg_views_shorts),
                "videos": long_form,
                "shorts": shorts,
                "long_form_count": len(long_form),
                "shorts_count": len(shorts),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }

            print(f"[competitive_intel]   Got {len(long_form)} long-form + {len(shorts)} shorts, avg views: {avg_views_long:,.0f}")

            # Respect API quota — small delay between channels
            time.sleep(0.5)

        except Exception as e:
            print(f"[competitive_intel]   Error crawling {channel_name}: {e}")
            continue

    intel["competitors"] = channels_data
    _save_intel(intel)

    # Persist to Supabase so Railway can use it across deployments
    try:
        from core.utils import persist_json_to_supabase
        persist_json_to_supabase(INTEL_FILE, intel)
        print("[competitive_intel] Persisted to Supabase")
    except Exception as e:
        print(f"[competitive_intel] Supabase persist warning: {e}")

    print(f"[competitive_intel] Crawled {len(channels_data)}/{len(COMPETITORS)} channels")
    return intel


def find_content_gaps(our_topics: list[str]) -> list[dict]:
    """
    Compare competitor topics against our published topics.
    Returns topics they covered that we haven't, ranked by view performance.
    """
    intel = _load_existing_intel()
    competitors = intel.get("competitors", {})
    if not competitors:
        print("[competitive_intel] No competitor data — run crawl_competitors() first")
        return []

    our_lower = {t.lower().strip() for t in our_topics}

    # Collect all competitor videos with a simple keyword-match dedup
    competitor_topics = []
    for ch_id, ch_data in competitors.items():
        for video in ch_data.get("videos", []):
            title = video.get("title", "")
            title_lower = title.lower()
            # Check if any of our topics appear as a substring in the competitor title
            already_covered = any(
                our_t in title_lower or title_lower in our_t
                for our_t in our_lower
                if len(our_t) > 5  # avoid trivially short matches
            )
            if not already_covered:
                competitor_topics.append({
                    "title": title,
                    "topic": title,  # backward compat for callers using "topic" key
                    "views": video.get("views", 0),
                    "likes": video.get("likes", 0),
                    "channel": ch_data.get("name", ""),
                    "publish_date": video.get("publish_date", ""),
                    "video_id": video.get("video_id", ""),
                })

    # Rank by views descending
    competitor_topics.sort(key=lambda x: x["views"], reverse=True)

    # Deduplicate similar titles (basic: skip if >60% word overlap with a higher-ranked entry)
    deduped = []
    seen_words = []
    for topic in competitor_topics:
        words = set(topic["title"].lower().split())
        is_dup = False
        for sw in seen_words:
            overlap = len(words & sw) / max(len(words | sw), 1)
            if overlap > 0.6:
                is_dup = True
                break
        if not is_dup:
            deduped.append(topic)
            seen_words.append(words)

    print(f"[competitive_intel] Found {len(deduped)} content gaps (topics we haven't covered)")
    return deduped[:50]  # top 50


def get_trending_competitor_topics(days: int = 7) -> list[dict]:
    """
    Find competitor videos from the last N days outperforming their channel average.
    These represent trending/viral topics in the niche.
    """
    intel = _load_existing_intel()
    competitors = intel.get("competitors", {})
    if not competitors:
        print("[competitive_intel] No competitor data — run crawl_competitors() first")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    trending = []

    for ch_id, ch_data in competitors.items():
        avg_views = ch_data.get("avg_views_recent_20", 0)
        if avg_views == 0:
            continue

        for video in ch_data.get("videos", []):
            pub_date_str = video.get("publish_date", "")
            if not pub_date_str:
                continue
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if pub_date < cutoff:
                continue

            views = video.get("views", 0)
            if views <= 0:
                continue

            # Calculate performance ratio vs channel average
            performance_ratio = views / avg_views if avg_views > 0 else 0

            # Only include videos outperforming channel average by 50%+
            if performance_ratio >= 1.5:
                trending.append({
                    "title": video.get("title", ""),
                    "views": views,
                    "channel": ch_data.get("name", ""),
                    "performance_ratio": round(performance_ratio, 2),
                    "publish_date": pub_date_str,
                    "video_id": video.get("video_id", ""),
                    "channel_avg_views": avg_views,
                })

    trending.sort(key=lambda x: x["performance_ratio"], reverse=True)
    print(f"[competitive_intel] Found {len(trending)} trending competitor videos (last {days} days)")
    return trending


def compute_gap_score(gap: dict, channel_avg_views: dict) -> float:
    """Score a gap 0.5-0.95 based on performance_ratio and recency."""
    views = gap.get("views", 0)
    channel = gap.get("channel", "")
    avg = channel_avg_views.get(channel, 1)
    ratio = views / max(avg, 1)

    # Base score from performance ratio (0.5-0.95)
    base = 0.5 + 0.45 * min(ratio / 5.0, 1.0)

    # Recency decay: videos older than 90 days get reduced score
    pub_date = gap.get("publish_date", "")
    if pub_date:
        try:
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(pub_date.replace("Z", "+00:00"))).days
            if age_days > 90:
                base *= max(0.7, 1.0 - (age_days - 90) / 365)
        except (ValueError, TypeError):
            pass

    return round(min(0.95, max(0.5, base)), 2)


def get_competitive_signals(our_topics: list = None) -> dict:
    """Return structured competitive data for the scoring engine."""
    intel = load_competitive_intel()
    competitors = intel.get("competitors", {})
    if not competitors:
        return {"data_available": False}

    # Build channel avg views lookup
    channel_avg = {}
    for ch_id, ch_data in competitors.items():
        channel_avg[ch_data.get("name", "")] = ch_data.get("avg_views_recent_20", 0)

    # Content gaps
    gaps = find_content_gaps(our_topics or []) if our_topics is not None else []

    # Trending
    trending = get_trending_competitor_topics(days=14)

    # Niche saturation: topics covered by 3+ competitors
    topic_coverage = {}  # tuple of sorted words -> set of channel names
    for ch_id, ch_data in competitors.items():
        ch_name = ch_data.get("name", "")
        for v in ch_data.get("videos", []):
            words = tuple(sorted(v.get("title", "").lower().split()))
            if len(words) >= 3:
                topic_coverage.setdefault(words, set()).add(ch_name)

    saturated_titles = []
    for words, channels in topic_coverage.items():
        if len(channels) >= 3:
            saturated_titles.append({
                "words": list(words),
                "channels": list(channels),
                "count": len(channels),
            })

    # Shorts insights (for prompt context, not scoring)
    total_shorts = sum(ch.get("shorts_count", 0) for ch in competitors.values())
    avg_shorts_views = 0
    all_shorts = []
    for ch in competitors.values():
        all_shorts.extend(ch.get("shorts", []))
    if all_shorts:
        avg_shorts_views = sum(s.get("views", 0) for s in all_shorts) / len(all_shorts)

    return {
        "data_available": True,
        "gaps": gaps,
        "trending": trending,
        "saturated": saturated_titles,
        "channel_avg_views": channel_avg,
        "shorts_insights": {
            "total_shorts": total_shorts,
            "avg_views": round(avg_shorts_views),
            "top_shorts": sorted(all_shorts, key=lambda x: x.get("views", 0), reverse=True)[:5],
        },
        "generated_at": intel.get("generated_at", ""),
    }


def get_competitor_summary(max_chars: int = 2000) -> str:
    """
    Return a formatted string summary for injection into topic discovery agent prompts.
    """
    intel = load_competitive_intel()
    competitors = intel.get("competitors", {})
    if not competitors:
        return ""

    generated_at = intel.get("generated_at", "unknown")

    lines = [
        "=== COMPETITIVE INTELLIGENCE ===",
        f"Data from {len(competitors)} competitor channels (as of {generated_at})",
        "",
    ]

    # Top performing competitor videos overall
    all_videos = []
    for ch_id, ch_data in competitors.items():
        for v in ch_data.get("videos", []):
            all_videos.append({
                **v,
                "channel": ch_data.get("name", ""),
            })
    all_videos.sort(key=lambda x: x.get("views", 0), reverse=True)

    if all_videos:
        lines.append("TOP PERFORMING COMPETITOR VIDEOS:")
        for v in all_videos[:10]:
            views = v.get("views", 0)
            lines.append(f"  - [{views:>10,} views] {v.get('channel', '')}: {v.get('title', '')}")
        lines.append("")

    # Trending topics
    trending = get_trending_competitor_topics(days=14)
    if trending:
        lines.append("TRENDING IN NICHE (outperforming channel avg):")
        for t in trending[:5]:
            lines.append(
                f"  - {t['title']} ({t['channel']}) — "
                f"{t['performance_ratio']:.1f}x avg, {t['views']:,} views"
            )
        lines.append("")

    # Shorts section
    total_shorts = sum(ch.get("shorts_count", 0) for ch in competitors.values())
    if total_shorts > 0:
        lines.append(f"COMPETITOR SHORTS: {total_shorts} shorts tracked across {len(competitors)} channels")
        top_shorts = []
        for ch_data in competitors.values():
            for s in ch_data.get("shorts", []):
                top_shorts.append({**s, "channel": ch_data.get("name", "")})
        top_shorts.sort(key=lambda x: x.get("views", 0), reverse=True)
        for s in top_shorts[:3]:
            lines.append(f"  - [{s.get('views',0):>10,} views] {s.get('channel','')}: {s.get('title','')}")
        lines.append("")

    # Channel overview
    lines.append("COMPETITOR OVERVIEW:")
    for ch_id, ch_data in sorted(
        competitors.items(),
        key=lambda x: x[1].get("subscriber_count", 0),
        reverse=True,
    ):
        lines.append(
            f"  - {ch_data['name']}: "
            f"{ch_data.get('subscriber_count', 0):,} subs, "
            f"~{ch_data.get('avg_views_recent_20', 0):,} avg views/video"
        )

    lines.append("===================================")
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars - 3] + "..."
    return result


def analyze_thumbnail_trends() -> list[dict]:
    """
    Analyze competitor thumbnail URLs using Claude Haiku vision
    to identify winning visual patterns.
    Returns top patterns found across high-performing thumbnails.
    """
    intel = _load_existing_intel()
    competitors = intel.get("competitors", {})
    if not competitors:
        print("[competitive_intel] No competitor data — run crawl_competitors() first")
        return []

    # Collect top-performing videos with thumbnails
    all_videos = []
    for ch_id, ch_data in competitors.items():
        for v in ch_data.get("videos", []):
            if v.get("thumbnail_url") and v.get("views", 0) > 0:
                all_videos.append({
                    **v,
                    "channel": ch_data.get("name", ""),
                    "channel_avg": ch_data.get("avg_views_recent_20", 1),
                })

    if not all_videos:
        print("[competitive_intel] No thumbnail data available")
        return []

    # Sort by performance ratio (views vs channel avg)
    for v in all_videos:
        v["perf_ratio"] = v["views"] / max(v["channel_avg"], 1)
    all_videos.sort(key=lambda x: x["perf_ratio"], reverse=True)

    # Take top 15 thumbnails for analysis
    top_thumbnails = all_videos[:15]

    # Download thumbnails and send to Claude Haiku vision
    try:
        import requests
        from clients.claude_client import call_claude, HAIKU  # noqa: F401
    except ImportError as e:
        print(f"[competitive_intel] Missing dependency for thumbnail analysis: {e}")
        return []

    # Build a batch analysis prompt with thumbnail URLs
    thumbnail_descriptions = []
    for i, v in enumerate(top_thumbnails):
        url = v.get("thumbnail_url", "")
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            import base64
            img_b64 = base64.b64encode(resp.content).decode("utf-8")
            content_type = resp.headers.get("content-type", "image/jpeg")

            thumbnail_descriptions.append({
                "index": i + 1,
                "title": v.get("title", ""),
                "views": v.get("views", 0),
                "perf_ratio": round(v["perf_ratio"], 2),
                "img_b64": img_b64,
                "content_type": content_type,
            })
        except Exception as e:
            print(f"[competitive_intel]   Failed to download thumbnail {i+1}: {e}")
            continue

        if len(thumbnail_descriptions) >= 8:
            break

    if not thumbnail_descriptions:
        print("[competitive_intel] Could not download any thumbnails for analysis")
        return []

    # Send thumbnails to Claude Haiku for visual pattern analysis
    try:
        from clients.claude_client import client, track_usage

        # Build message content with images
        user_content = [
            {"type": "text", "text": (
                "Analyze these high-performing history YouTube thumbnails. "
                "Identify the top visual patterns that make them effective:\n\n"
            )},
        ]
        for td in thumbnail_descriptions:
            user_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": td["content_type"],
                    "data": td["img_b64"],
                },
            })
            user_content.append({
                "type": "text",
                "text": f"Thumbnail {td['index']}: \"{td['title']}\" — {td['views']:,} views, {td['perf_ratio']}x channel avg\n",
            })

        user_content.append({
            "type": "text",
            "text": (
                "\nReturn JSON only: [{\"pattern\": \"description\", \"frequency\": \"how many thumbnails use it\", "
                "\"effectiveness\": \"high/medium/low\", \"recommendation\": \"how to apply this\"}]"
            ),
        })

        response = client.messages.create(
            model=HAIKU,
            max_tokens=1500,
            system="You are a YouTube thumbnail analyst specializing in history/documentary channels. Identify winning visual patterns.",
            messages=[{"role": "user", "content": user_content}],
        )

        try:
            track_usage(HAIKU, response.usage)
        except Exception:
            pass
        raw = response.content[0].text.strip()
        clean = re.sub(r"^```(?:json)?\s*", "", raw)
        clean = re.sub(r"\s*```$", "", clean).strip()
        patterns = json.loads(clean)

        if isinstance(patterns, list):
            # Store in intel
            intel["thumbnail_patterns"] = {
                "patterns": patterns,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "thumbnails_analyzed": len(thumbnail_descriptions),
            }
            _save_intel(intel)
            print(f"[competitive_intel] Identified {len(patterns)} thumbnail patterns")
            return patterns

    except Exception as e:
        print(f"[competitive_intel] Thumbnail analysis failed: {e}")

    return []


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    crawl_competitors()

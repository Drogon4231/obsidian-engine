"""
trend_detector.py — Real-time trend detection for The Obsidian Archive.

Checks Google Trends, Reddit, and YouTube for surging history topics.
Cross-references sources, scores each topic, and triggers emergency
pipeline runs for high-scoring trends.

Usage:
    python3 trend_detector.py
"""

from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.append(str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Niche keywords for filtering ──────────────────────────────────────────────
HISTORY_KEYWORDS = [
    "history", "ancient", "medieval", "empire", "dynasty", "war", "battle",
    "civilization", "pharaoh", "roman", "greek", "viking", "colonial",
    "conspiracy", "assassination", "betrayal", "forgotten", "lost",
    "suppressed", "dark", "secret", "mystery", "massacre", "plague",
    "revolution", "siege", "torture", "execution", "poison", "espionage",
    "cult", "ritual", "artifact", "archaeology", "tomb", "pyramid",
    "crusade", "inquisition", "slavery", "mughal", "ottoman", "mongol",
]


# ── Google Trends ─────────────────────────────────────────────────────────────

def check_google_trends(niche_keywords: list[str] | None = None) -> list[dict]:
    """
    Use pytrends to check trending searches related to history.
    Returns list of trending topics with relative search volume.
    """
    keywords = niche_keywords or ["dark history", "ancient mystery", "forgotten history", "historical conspiracy", "lost civilization"]

    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("[trend_detector] pytrends not installed — run: pip install pytrends")
        return []

    trends = []
    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))

        # Check related queries for each seed keyword
        for kw in keywords[:5]:  # limit to 5 to avoid rate limits
            try:
                pytrends.build_payload([kw], cat=0, timeframe="now 7-d")
                related = pytrends.related_queries()

                if kw in related:
                    # Rising queries indicate trend velocity
                    rising = related[kw].get("rising")
                    if rising is not None and not rising.empty:
                        for _, row in rising.head(5).iterrows():
                            query = row.get("query", "")
                            value = row.get("value", 0)
                            if _is_history_relevant(query):
                                trends.append({
                                    "topic": query,
                                    "source": "google_trends",
                                    "seed_keyword": kw,
                                    "trend_value": int(value) if value else 0,
                                    "type": "rising",
                                })

                    # Top queries indicate sustained interest
                    top = related[kw].get("top")
                    if top is not None and not top.empty:
                        for _, row in top.head(3).iterrows():
                            query = row.get("query", "")
                            value = row.get("value", 0)
                            if _is_history_relevant(query):
                                trends.append({
                                    "topic": query,
                                    "source": "google_trends",
                                    "seed_keyword": kw,
                                    "trend_value": int(value) if value else 0,
                                    "type": "top",
                                })

                time.sleep(1)  # respect rate limits

            except Exception as e:
                print(f"[trend_detector] Google Trends error for '{kw}': {e}")
                continue

    except Exception as e:
        print(f"[trend_detector] Google Trends init failed: {e}")

    # Deduplicate
    seen = set()
    deduped = []
    for t in trends:
        key = t["topic"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    print(f"[trend_detector] Google Trends: found {len(deduped)} history-related trends")
    return deduped


# ── Reddit Trends ─────────────────────────────────────────────────────────────

def check_reddit_trends() -> list[dict]:
    """
    Check hot posts on history-related subreddits via Reddit JSON API (no auth).
    Returns top 10 posts related to dark/forgotten history.
    """
    try:
        import requests
    except ImportError:
        print("[trend_detector] requests not installed")
        return []

    subreddits = [
        "history",
        "AskHistorians",
        "todayilearned",
    ]

    headers = {
        "User-Agent": "ObsidianArchiveBot/1.0 (trend detection for documentary research)",
    }

    all_posts = []

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 429:
                print(f"[trend_detector] Reddit rate limited on r/{sub} — skipping")
                time.sleep(2)
                continue
            if resp.status_code != 200:
                print(f"[trend_detector] Reddit r/{sub} returned {resp.status_code}")
                continue

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                pdata = post.get("data", {})
                title = pdata.get("title", "")
                score = pdata.get("score", 0)
                num_comments = pdata.get("num_comments", 0)
                permalink = pdata.get("permalink", "")
                created_utc = pdata.get("created_utc", 0)

                # Filter for history relevance
                if _is_history_relevant(title):
                    all_posts.append({
                        "title": title,
                        "score": score,
                        "num_comments": num_comments,
                        "subreddit": sub,
                        "url": f"https://reddit.com{permalink}" if permalink else "",
                        "source": "reddit",
                        "created_utc": created_utc,
                    })

            time.sleep(1)  # respect rate limits between subreddits

        except Exception as e:
            print(f"[trend_detector] Reddit r/{sub} error: {e}")
            continue

    # Sort by engagement (score + comments)
    all_posts.sort(key=lambda x: x["score"] + x["num_comments"] * 2, reverse=True)

    top_posts = all_posts[:10]
    print(f"[trend_detector] Reddit: found {len(top_posts)} relevant hot posts")
    return top_posts


# ── YouTube Trending ──────────────────────────────────────────────────────────

def check_youtube_trending(api_key: str | None = None) -> list[dict]:
    """
    Search YouTube for recently uploaded history videos with high early view velocity.
    """
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        print("[trend_detector] YOUTUBE_API_KEY not set — skipping YouTube trends")
        return []

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("[trend_detector] google-api-python-client not installed")
        return []

    try:
        youtube = build("youtube", "v3", developerKey=key)
    except Exception as e:
        print(f"[trend_detector] YouTube API init failed: {e}")
        return []

    # Search for recent history videos (last 3 days)
    published_after = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

    search_queries = [
        "dark history documentary",
        "forgotten history",
        "ancient mystery",
        "historical conspiracy",
        "untold history",
    ]

    all_videos = []

    for query in search_queries:
        try:
            search_resp = youtube.search().list(
                part="id,snippet",
                q=query,
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                maxResults=10,
                relevanceLanguage="en",
            ).execute()

            video_ids = [
                item["id"]["videoId"]
                for item in search_resp.get("items", [])
                if item.get("id", {}).get("videoId")
            ]

            if not video_ids:
                continue

            # Get video stats
            videos_resp = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids),
            ).execute()

            for v in videos_resp.get("items", []):
                snippet = v.get("snippet", {})
                stats = v.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                pub_date = snippet.get("publishedAt", "")

                # Calculate view velocity (views per hour since publish)
                velocity = 0
                if pub_date:
                    try:
                        pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        hours_since = max(
                            (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600,
                            1,
                        )
                        velocity = views / hours_since
                    except (ValueError, TypeError):
                        pass

                all_videos.append({
                    "title": snippet.get("title", ""),
                    "video_id": v["id"],
                    "channel": snippet.get("channelTitle", ""),
                    "views": views,
                    "likes": int(stats.get("likeCount", 0)),
                    "publish_date": pub_date,
                    "velocity_views_per_hour": round(velocity, 1),
                    "source": "youtube_trending",
                })

            time.sleep(0.5)

        except Exception as e:
            print(f"[trend_detector] YouTube search error for '{query}': {e}")
            continue

    # Sort by view velocity
    all_videos.sort(key=lambda x: x["velocity_views_per_hour"], reverse=True)

    # Deduplicate by video ID
    seen_ids = set()
    deduped = []
    for v in all_videos:
        if v["video_id"] not in seen_ids:
            seen_ids.add(v["video_id"])
            deduped.append(v)

    top = deduped[:15]
    print(f"[trend_detector] YouTube: found {len(top)} high-velocity history videos")
    return top


# ── Orchestration ─────────────────────────────────────────────────────────────

def detect_trending_topics() -> list[dict]:
    """
    Orchestrate all trend checks, cross-reference results, and score each topic.
    Score 0-1 based on: trend velocity, niche relevance, novelty.
    Returns sorted list of detected trends.
    """
    print("[trend_detector] Running full trend detection...")

    # Gather signals from all sources
    google_trends = check_google_trends()
    reddit_trends = check_reddit_trends()
    youtube_trends = check_youtube_trending()

    # Check novelty against our topic store
    our_topics = set()
    try:
        from server.topic_store import list_covered
        covered = list_covered(limit=100)
        our_topics = {t["topic"].lower() for t in covered if t.get("topic")}
    except Exception as e:
        print(f"[trend_detector] Could not load topic store: {e}")

    # Normalize all signals into a common format
    candidates = {}  # topic_key -> {topic, score_components, sources}

    # Google Trends signals
    for t in google_trends:
        key = t["topic"].lower().strip()
        if key not in candidates:
            candidates[key] = {"topic": t["topic"], "sources": [], "signals": {}}
        candidates[key]["sources"].append("google_trends")
        # Rising queries with high values indicate strong trend velocity
        velocity_score = min(t.get("trend_value", 0) / 500, 1.0) if t.get("type") == "rising" else 0.3
        candidates[key]["signals"]["google_velocity"] = velocity_score

    # Reddit signals
    for t in reddit_trends:
        title = t["title"]
        key = title.lower().strip()[:80]
        if key not in candidates:
            candidates[key] = {"topic": title, "sources": [], "signals": {}}
        candidates[key]["sources"].append("reddit")
        # Score based on engagement
        engagement = t.get("score", 0) + t.get("num_comments", 0) * 3
        candidates[key]["signals"]["reddit_engagement"] = min(engagement / 5000, 1.0)

    # YouTube signals
    for t in youtube_trends:
        title = t["title"]
        key = title.lower().strip()[:80]
        if key not in candidates:
            candidates[key] = {"topic": title, "sources": [], "signals": {}}
        candidates[key]["sources"].append("youtube_trending")
        velocity = t.get("velocity_views_per_hour", 0)
        candidates[key]["signals"]["youtube_velocity"] = min(velocity / 1000, 1.0)

    # Score each candidate
    scored = []
    for key, data in candidates.items():
        signals = data["signals"]
        sources = data["sources"]

        # Base score: average of available signals
        signal_values = list(signals.values())
        base_score = sum(signal_values) / len(signal_values) if signal_values else 0

        # Cross-source bonus: appearing in multiple sources is a strong signal
        cross_source_bonus = min(len(set(sources)) * 0.15, 0.3)

        # Niche relevance score
        relevance = _relevance_score(data["topic"])

        # Novelty penalty: if topic overlaps with our covered topics, reduce score
        novelty = 1.0
        topic_lower = data["topic"].lower()
        for our_t in our_topics:
            if our_t in topic_lower or topic_lower in our_t:
                novelty = 0.1
                break

        # Final composite score
        final_score = (
            base_score * 0.35
            + cross_source_bonus
            + relevance * 0.2
            + novelty * 0.15
        )
        final_score = round(min(max(final_score, 0), 1.0), 3)

        scored.append({
            "topic": data["topic"],
            "score": final_score,
            "sources": list(set(sources)),
            "signals": signals,
            "is_novel": novelty > 0.5,
            "relevance": round(relevance, 2),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    print(f"[trend_detector] Scored {len(scored)} trend candidates")
    return scored


def trigger_emergency_pipeline(topic: str) -> bool:
    """
    Queue a high-scoring trend topic in Supabase with emergency priority.
    Returns True if successfully queued.
    """
    print("\n[trend_detector] *** EMERGENCY TREND ALERT ***")
    print(f"[trend_detector] Topic: {topic}")
    print("[trend_detector] Queueing with score=0.95, source=trend_emergency")

    try:
        from clients.supabase_client import add_topic
        result = add_topic(topic, source="trend_emergency", score=0.95)
        if result:
            print(f"[trend_detector] Successfully queued emergency topic: {topic}")
            try:
                from server.notify import notify_trend_alert
                notify_trend_alert(topic, 0.95, ["trend_emergency"])
            except Exception:
                pass
            return True
        else:
            print(f"[trend_detector] Topic may already exist in queue: {topic}")
            return False
    except Exception as e:
        print(f"[trend_detector] Failed to queue emergency topic: {e}")
        return False


def run() -> list[dict]:
    """
    Main entry point. Run all checks, detect trends, trigger emergency if needed.
    Returns list of detected trends.
    """
    print(f"[trend_detector] Starting trend detection at {datetime.now(timezone.utc).isoformat()}")

    trends = detect_trending_topics()

    # Persist results to disk so the /trends endpoint can read them
    results_file = BASE_DIR / "outputs" / "trend_results.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    trend_data = {
        "trends": [{"topic": t["topic"], "score": t["score"], "sources": t["sources"], "is_novel": t.get("is_novel", False)} for t in trends],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(trends),
    }
    results_file.write_text(json.dumps(trend_data, indent=2))
    try:
        from core.utils import persist_json_to_supabase
        persist_json_to_supabase(results_file, trend_data)
    except Exception:
        pass

    if not trends:
        print("[trend_detector] No trends detected")
        return []

    # Print top results
    print("\n[trend_detector] === TOP TRENDS ===")
    for i, t in enumerate(trends[:10], 1):
        sources_str = ", ".join(t["sources"])
        print(f"  {i}. [{t['score']:.2f}] {t['topic']} ({sources_str})")

    # Trigger emergency pipeline for high-scoring trends
    emergency_count = 0
    for t in trends:
        if t["score"] > 0.8 and t.get("is_novel", False):
            triggered = trigger_emergency_pipeline(t["topic"])
            if triggered:
                emergency_count += 1
            if emergency_count >= 2:
                print("[trend_detector] Capped emergency triggers at 2 per run")
                break

    print(f"\n[trend_detector] Done. {len(trends)} trends found, {emergency_count} emergency triggers.")
    return trends


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_history_relevant(text: str) -> bool:
    """Check if text is related to history topics."""
    text_lower = text.lower()
    matches = sum(1 for kw in HISTORY_KEYWORDS if kw in text_lower)
    return matches >= 1


def _relevance_score(text: str) -> float:
    """Score 0-1 how relevant a topic is to our dark history niche."""
    text_lower = text.lower()
    matches = sum(1 for kw in HISTORY_KEYWORDS if kw in text_lower)
    # More keyword matches = higher relevance, capped at 1.0
    return min(matches / 3.0, 1.0)


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run()
